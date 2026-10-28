#!/usr/bin/env bash
set -eo pipefail

device_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source_root=$(cd -- "$device_dir/../../.." && pwd)
bash "$device_dir/tools/prepare.sh" "${LINEAGE_ROOT:-$source_root/../lineageos-19.1}"
cd -- "$source_root"
source build/envsetup.sh
lunch twrp_X606X-eng
test "$(get_build_var PRODUCT_ENFORCE_VINTF_MANIFEST)" = true
m -j"${JOBS:-4}" recoveryimage
product_out=$(get_build_var PRODUCT_OUT)
audit_out="${OUT_DIR:-out}/tb-x606x-audit/recovery"
python3 "$device_dir/tools/validate_recovery.py" "$product_out/recovery.img" \
    --device-dir "$device_dir" --output-dir "$audit_out"
sha256sum "$product_out/recovery.img" | tee "$audit_out/recovery.img.sha256"
