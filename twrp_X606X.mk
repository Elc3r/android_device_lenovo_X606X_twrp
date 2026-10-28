ALLOW_MISSING_DEPENDENCIES := true

$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/base.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/gsi_keys.mk)
$(call inherit-product, vendor/twrp/config/common.mk)

PRODUCT_RELEASE_NAME := X606X
PRODUCT_NAME := twrp_X606X
PRODUCT_DEVICE := X606X
PRODUCT_SYSTEM_DEVICE := achilles6_row_data
PRODUCT_BUILD_PROP_OVERRIDES += TARGET_DEVICE=achilles6_row_data
PRODUCT_SYSTEM_PROPERTIES += ro.product.device=achilles6_row_data
PRODUCT_BRAND := Lenovo
PRODUCT_MODEL := Lenovo TB-X606X
PRODUCT_MANUFACTURER := LENOVO

PRODUCT_COPY_FILES += \
    device/lenovo/X606X/recovery/root/init.recovery.mt8768.rc:recovery/root/init.recovery.mt6765.rc \
    device/lenovo/X606X/recovery/root/ueventd.mt8768.rc:recovery/root/vendor/etc/ueventd.rc
