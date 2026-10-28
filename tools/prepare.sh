#!/usr/bin/env bash
set -euo pipefail

device_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source_root=$(cd -- "$device_dir/../../.." && pwd)
lineage_root=${1:-"$source_root/../lineageos-19.1"}
kernel_source="$lineage_root/device/lenovo/achilles6_row_data/prebuilt/Image.gz"
kernel_source=${KERNEL_SOURCE:-$kernel_source}
kernel_target="$device_dir/prebuilt/x606x_Image.gz"
expected_kernel=fb039df774989a7ca083b63ff77ef2b59c8e6f2352166777c5c82c0e8bd29bdc
patch_file="$device_dir/patch/system/vold/0001-Remove-a12-kmblob-magic.patch"

if [[ -e "$kernel_target" ]]; then
    printf '%s  %s\n' "$expected_kernel" "$kernel_target" | sha256sum --check --status
else
    printf '%s  %s\n' "$expected_kernel" "$kernel_source" | sha256sum --check --status
fi
git -C "$device_dir" status --short
git -C "$source_root/system/vold" status --short
if git -C "$source_root/system/vold" apply --reverse --check "$patch_file" 2>/dev/null; then
    printf 'Keymaster patch already applied.\n'
else
    git -C "$source_root/system/vold" diff --quiet -- KeyStorage.cpp
    git -C "$source_root/system/vold" diff --cached --quiet -- KeyStorage.cpp
    git -C "$source_root/system/vold" apply --check "$patch_file"
    git -C "$source_root/system/vold" apply "$patch_file"
fi
if [[ ! -e "$kernel_target" ]]; then
    cp -- "$kernel_source" "$kernel_target"
fi
printf 'Prepared experimental TB-X606X sources; no device access performed.\n'
