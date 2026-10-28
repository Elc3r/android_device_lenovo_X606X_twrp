# TWRP 3.7.1 / Android 12.1 — Lenovo TB-X606X LTE

Unofficial recovery based on Yahoo-Mike's `recovery_device_lenovo_X606FA`,
`android-12.1-fbe`, commit `9a49e442790139f6aa9b1f58f4fcb727718364a0`.
Existing history, authors and copyright headers are retained. X606F/FA and
X606X kernels are not interchangeable.

## Tested status

- Actual recovery flash boots; display, touch and normal ADB work.
- FBE decryption with and without PIN works with the matching hardware-Beanpod
  LineageOS 19.1 build. Stock FDE userdata needs a different recovery.
- Internal-storage ZIP installation works and Android boots afterward.
- Runtime device/system/build identifiers are `achilles6_row_data`, matching
  the ROM assertion. Build/lunch/source name remains X606X; model is TB-X606X.

`fastboot boot` reported success but returned to Android on the tested tablet.
ADB sideload hangs in FunctionFS binding; use normal ADB push plus Install.
Recovery is engineering/permissive. Platform metadata `2025-03-05` matches the
tested ROM, vendor SPL is `2022-05-05`; this does not update old binaries/kernel.

## Build

Use integration `docs/BUILD_TWRP.md` and its pinned TWRP manifest. Put this tree
at `device/lenovo/X606X`, then:

```bash
bash device/lenovo/X606X/tools/build.sh
```

The published pinned manifest supplies the exact LTE kernel from the companion
device repository. The helper verifies its SHA256 before any preparation:
`fb039df774989a7ca083b63ff77ef2b59c8e6f2352166777c5c82c0e8bd29bdc`.
The imported `prebuilt/x606x_Image.gz` is gitignored. For a manual checkout,
set `KERNEL_SOURCE=/path/to/Image.gz`, or `LINEAGE_ROOT=/path/to/lineageos-19.1`
to import the kernel from that tree. An already valid local kernel needs neither.
The helper applies the
matching vold patch if needed and builds, but never flashes.
Output: `out/target/product/X606X/recovery.img`.

The tested recovery partition is 32 MiB. Packed-image validation checks bounds,
properties, fstab, dependency names and kernel identity, not complete runtime
symbol/linker compatibility. Publication cleanup has not been rebuilt yet.

Inherited X606F/FA kernel/vendor artifacts retain original provenance. The new
LTE kernel is imported locally rather than added to Git. Complete corresponding
kernel source and proprietary redistribution grants are not supplied here.
See integration `docs/PROVENANCE.md`.
