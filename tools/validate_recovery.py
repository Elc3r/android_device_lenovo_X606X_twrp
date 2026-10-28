#!/usr/bin/env python3
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zlib


def align(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_cpio(data):
    entries = {}
    offset = 0
    while offset + 110 <= len(data):
        require(data[offset:offset + 6] == b"070701", "Expected a newc ramdisk archive")
        fields = [int(data[offset + 6 + index * 8:offset + 14 + index * 8], 16)
                  for index in range(13)]
        mode, size, namesize = fields[1], fields[6], fields[11]
        name_start = offset + 110
        require(namesize > 0, "Invalid cpio name length")
        require(name_start + namesize <= len(data), "Truncated cpio filename")
        require(data[name_start + namesize - 1] == 0, "Unterminated cpio filename")
        require(b"\x00" not in data[name_start:name_start + namesize - 1],
                "Embedded NUL in cpio filename")
        name = data[name_start:name_start + namesize - 1].decode()
        offset = align(name_start + namesize, 4)
        require(offset + size <= len(data), f"Truncated ramdisk entry: {name}")
        if name == "TRAILER!!!":
            require(not any(data[offset + size:]), "Unexpected nonzero data after cpio trailer")
            return entries
        path = Path(name)
        require(not path.is_absolute() and ".." not in path.parts, f"Unsafe archive path: {name}")
        require(str(path) not in entries, f"Duplicate ramdisk entry: {name}")
        entries[str(path)] = (mode, data[offset:offset + size])
        offset = align(offset + size, 4)
    raise ValueError("Missing cpio trailer")


def inspect_elf_dependencies(entries):
    libraries = {}
    elf_files = {}
    trusted_apps = []
    for name, (_, content) in entries.items():
        if content.startswith(b"\x7fELF"):
            if name.startswith("vendor/thh/ta/") and name.endswith(".ta"):
                trusted_apps.append({"path": name, "sha256": hashlib.sha256(content).hexdigest()})
                continue
            elf_class = content[4]
            require(content[5] == 1, f"Unexpected ELF byte order: {name}")
            machine = struct.unpack_from("<H", content, 18)[0]
            require((elf_class, machine) in [(1, 40), (2, 183)],
                    f"Unexpected ELF target architecture: {name}")
            elf_files[name] = (elf_class, content)
            libraries.setdefault((elf_class, Path(name).name), []).append(name)
    missing = []
    with tempfile.TemporaryDirectory(prefix="twrp-elf-audit-") as temporary:
        elf_path = Path(temporary) / "elf"
        for name, (elf_class, content) in elf_files.items():
            elf_path.write_bytes(content)
            result = subprocess.run(
                ["readelf", "--dynamic", str(elf_path)], check=True,
                text=True, capture_output=True
            )
            dependencies = re.findall(r"\(NEEDED\).*?\[(.*?)\]", result.stdout)
            for dependency in dependencies:
                if (elf_class, dependency) not in libraries:
                    missing.append({"file": name, "missing": dependency, "elf_class": elf_class})
    return {
        "elf_count": len(elf_files),
        "secure_world_trusted_apps_not_android_linked": trusted_apps,
        "missing_dt_needed_by_class_and_basename": missing,
        "limitations": "Does not prove linker namespace/path, dlopen or symbol-version compatibility; trusted apps need secure-world libraries, not Android libraries",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--device-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data = args.image.read_bytes()
    require(data[:8] == b"ANDROID!", "Invalid Android image magic")
    values = struct.unpack_from("<10I", data, 8)
    kernel_size, kernel_address, ramdisk_size, ramdisk_address, second_size, _, tags, page, version, os_info = values
    require(version == 1, f"Expected experimental header v1, found {version}")
    require(page == 2048, f"Unexpected page size {page}")
    require((os_info >> 11) == (12 << 14), "Expected Android 12.0.0 boot metadata")
    require((os_info & 2047) == (((2025 - 2000) << 4) | 3),
            "Expected boot patch month matching LineageOS: 2025-03")
    require(kernel_address == 0x40080000, "Unexpected kernel load address")
    require(ramdisk_address == 0x51b00000, "Unexpected ramdisk load address")
    require(tags == 0x47880000, "Unexpected tags address")
    require(len(data) <= 33554432, "Recovery exceeds CONFIGURED 32 MiB limit")
    require(second_size == 0, "Unexpected second stage")
    require(struct.unpack_from("<I", data, 1632)[0] == 0, "Unexpected recovery DTBO")
    require(struct.unpack_from("<Q", data, 1636)[0] == 0, "Unexpected recovery DTBO offset")
    require(struct.unpack_from("<I", data, 1644)[0] == 1648, "Unexpected header size")
    kernel_offset = page
    ramdisk_offset = kernel_offset + align(kernel_size, page)
    end_offset = ramdisk_offset + align(ramdisk_size, page)
    require(end_offset <= len(data), "Image payload exceeds file size")
    kernel = data[kernel_offset:kernel_offset + kernel_size]
    ramdisk = data[ramdisk_offset:ramdisk_offset + ramdisk_size]
    expected_kernel = (args.device_dir / "prebuilt/x606x_Image.gz").read_bytes()
    require(kernel == expected_kernel, "Packed kernel differs from the selected X606X prebuilt")
    require(hashlib.sha256(kernel).hexdigest() ==
            "fb039df774989a7ca083b63ff77ef2b59c8e6f2352166777c5c82c0e8bd29bdc",
            "Selected prebuilt does not match the audited LTE kernel hash")
    digest = hashlib.sha1()
    for payload in [kernel, ramdisk, b"", b""]:
        digest.update(payload)
        digest.update(struct.pack("<I", len(payload)))
    require(data[576:608] == digest.digest().ljust(32, b"\x00"), "Boot image SHA-1 ID mismatch")
    decoder = zlib.decompressobj(31)
    decoder.decompress(kernel)
    require(decoder.eof, "Incomplete gzip kernel")
    dtb = decoder.unused_data
    require(dtb[:4] == b"\xd0\x0d\xfe\xed", "Missing appended DTB")
    require(struct.unpack_from(">I", dtb, 4)[0] == len(dtb), "Invalid appended DTB size")
    require(not any(data[end_offset:]), "Unexpected image trailer (AVB/signature needs separate audit)")
    entries = parse_cpio(gzip.decompress(ramdisk))
    for filename in ["system/bin/recovery", "system/bin/init", "system/bin/adbd",
                     "system/bin/linker64", "system/bin/resetprop", "system/bin/logcat",
                     "system/bin/logd", "init.recovery.logd.rc",
                     "init.recovery.mt6765.rc", "vendor/etc/ueventd.rc"]:
        require(filename in entries, f"Missing required ramdisk entry: {filename}")
    resetprop_mode, resetprop_content = entries["system/bin/resetprop"]
    require(resetprop_mode & 0o170000 == 0o100000 and resetprop_mode & 0o111,
            "resetprop must be an executable regular file")
    require(resetprop_content.startswith(b"\x7fELF"), "resetprop must be an ELF executable")
    for filename in ["system/bin/logcat", "system/bin/logd"]:
        executable_mode, executable_content = entries[filename]
        require(executable_mode & 0o170000 == 0o100000 and executable_mode & 0o111
                and executable_content.startswith(b"\x7fELF"),
                f"Diagnostic tool must be an executable ELF: {filename}")
    require(b"import /init.recovery.logd.rc"
            in entries.get("system/etc/init/hw/init.rc", (0, b""))[1],
            "Recovery init must import the logd service")
    require(b"service logd /system/bin/logd" in entries["init.recovery.logd.rc"][1]
            and b"start logd" in entries["init.recovery.logd.rc"][1],
            "Recovery logd service must be configured to start")
    etc_mode, etc_target = entries.get("etc", (0, b""))
    require(etc_mode & 0o170000 == 0o120000 and etc_target == b"/system/etc",
            "Expected /etc to be the Android /system/etc symlink")
    for filename in ["system/etc/twrp.fstab", "system/etc/recovery.fstab"]:
        require(filename in entries, f"Missing {filename}")
        expected = (args.device_dir / "recovery/root" / filename).read_bytes()
        require(entries[filename][1] == expected, f"Packed {filename} differs from the audited source")
    for source, destination in [("init.recovery.mt8768.rc", "init.recovery.mt6765.rc"),
                                ("ueventd.mt8768.rc", "vendor/etc/ueventd.rc")]:
        expected = (args.device_dir / "recovery/root" / source).read_bytes()
        require(entries[destination][1] == expected, f"Packed {destination} differs from source")
    cmdline = data[64:576].split(b"\x00", 1)[0] + data[608:1632].split(b"\x00", 1)[0]
    require(b"androidboot.hardware=mt6765" in cmdline, "Missing hardware selector")
    require(b"androidboot.selinux=permissive" in cmdline, "Unexpected SELinux mode")
    properties = entries.get("prop.default", (0, b""))[1].decode()
    require("ro.product.system.model=Lenovo TB-X606X" in properties,
            "Unexpected recovery product model")
    property_values = dict(line.split("=", 1) for line in properties.splitlines()
                           if line and not line.startswith("#") and "=" in line)
    for property_name in ["ro.product.device", "ro.product.system.device", "ro.build.product"]:
        require(property_values.get(property_name) == "achilles6_row_data",
                f"Unexpected OTA device identifier: {property_name}")
    require("ro.build.version.sdk=32" in properties, "Unexpected recovery SDK")
    require(property_values.get("ro.build.version.security_patch") == "2025-03-05",
            "Recovery platform patch level must match the target LineageOS build")
    require(property_values.get("ro.vendor.build.security_patch") == "2022-05-05",
            "Unexpected vendor patch level")
    elf_report = inspect_elf_dependencies(entries)
    report = {
        "image": str(args.image.resolve()),
        "image_bytes": len(data),
        "configured_partition_limit_bytes": 33554432,
        "physical_partition_limit_verified": False,
        "image_sha256": hashlib.sha256(data).hexdigest(),
        "header_version": version,
        "page_bytes": page,
        "kernel_bytes": kernel_size,
        "ramdisk_gzip_bytes": ramdisk_size,
        "appended_dtb_bytes": len(dtb),
        "appended_dtb_sha256": hashlib.sha256(dtb).hexdigest(),
        "boot_image_id_valid": True,
        "cmdline": cmdline.decode(),
        "os_version": f"{os_info >> 25}.{(os_info >> 18) & 127}.{(os_info >> 11) & 127}",
        "os_patch_month": f"{2000 + ((os_info & 2047) >> 4):04d}-{os_info & 15:02d}",
        "ramdisk_entry_count": len(entries),
        "elf_dependencies": elf_report,
        "hardware_boot_decryption_verified": False,
        "resetprop_executable_present": True,
        "ota_device_identifier": "achilles6_row_data",
        "android_logging_tools_and_init_present": True,
        "safe_to_flash": "NOT ESTABLISHED; live partition sizes and hardware boot/decryption unverified",
    }
    (args.output_dir / "recovery.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output_dir / "ramdisk-files.txt").write_text("\n".join(sorted(entries)) + "\n")
    (args.output_dir / "prop.default").write_text(properties)
    (args.output_dir / "kernel").write_bytes(kernel)
    (args.output_dir / "ramdisk.gz").write_bytes(ramdisk)
    print(json.dumps(report, indent=2))
    require(not elf_report["missing_dt_needed_by_class_and_basename"], "Unresolved ELF DT_NEEDED entries")


if __name__ == "__main__":
    main()
