# 路线 B：原厂引导链 + Armbian rootfs（vendor 4.19 内核，全硬件支持）

本路线保留 MiniLoaderAll + uboot.img + trust.img 引导链，把 Armbian 的
用户空间与 vendor 4.19.172 内核组合进 Android boot.img 启动格式，
LVDS 屏（GM8775C）、RTL8723DS WiFi/BT、Mali、ES8388 全部可用。

## 1. 构建 boot 分区镜像

```bash
# 材料（tools/ 工具产出，路径见 documents/01）
#   kernel   = unpack/parsed/kernel-extracted.bin   (vendor 4.19.172 Image)
#   second   = unpack/parsed/second-dtb.bin         (RSCE: dtb[2] GM8775C)
#   ramdisk  = armbian-initrd.img                   (Armbian 镜像 boot 分区)
#   template = unpack/live-boot.img                 (原厂 boot.img 头)

python tools/pack_bootimg.py \
    --template live-boot.img \
    --kernel   kernel-extracted.bin \
    --ramdisk  armbian-initrd.img \
    --second   second-dtb.bin \
    --cmdline  "root=LABEL=armbian-root rootwait rw console=tty1" \
    --output   boot-armbian.img
```

## 2. rootfs

从官方 Armbian arm64 镜像（如 odroidn2 minimal）抽取 ext4 rootfs 分区，
设置 `LABEL=armbian-root`，并补充：

```bash
# 4.19.172 内核模块（已从实机 adb 拉取）
cp -a vendor-modules/*  rootfs/lib/modules/4.19.172/
cp -a vendor-firmware/* rootfs/lib/firmware/
# 关闭 ophub/armbian 的自动内核升级（保留 4.19）
```

## 3. 刷写（二选一）

### 3a. 无损试装（adb 直刷，Android 可随时救回）

```powershell
# boot 分区（44 MiB）写入 Armbian boot.img
adb push boot-armbian.img /data/local/tmp/
adb shell "dd if=/data/local/tmp/boot-armbian.img of=/dev/block/by-name/boot"
# rootfs 写入 userdata（约 25 GiB）
adb push rootfs.img.zst /data/local/tmp/   # 或 adb push 直推未压缩 img
adb shell "zstd -d -c /data/local/tmp/rootfs.img.zst | dd of=/dev/block/by-name/userdata"
adb shell "sync; reboot"
```

恢复 Android：RKDevTool 重刷官方固件即可（boot/userdata 都会被覆盖）。

### 3b. 正式安装（update.img 整包）

使用 `vendor/parameter-armbian.txt`（super/userdata 合并为 `rootfs:grow`）：

```text
package-file 列表：
  bootloader  Image/MiniLoaderAll.bin
  parameter   Image/parameter-armbian.txt
  trust       Image/trust.img
  uboot       Image/uboot.img
  boot        Image/boot-armbian.img
  rootfs      Image/rootfs.img
```

用 `AI3399-C固件烧录工具/RKDevTool_v3.28_for_window/RKDevTool_v3.28_for_window/bin/AFPTool.exe`
按上述 package-file 打包成 update.img（或 `RKImageMaker.exe` 包 RKFW 头），
随后 RKDevTool 进 loader 模式整包刷写，loader 会按 parameter 重建 GPT。

## 4. 引导参数说明

U-Boot `boot_android` 会前置自己的参数（含 `androidboot.dtb_idx`、
`androidboot.hwid` 等），boot.img 的 cmdline 追加其后，因此 root= 写在
boot.img cmdline 里即可生效。second 段 RSCE 中 dtb[2] 即当前实机使用的
GM8775C 变体（由 hwid/o_mipi2lvds 匹配）。

## 5. 已验证事实

* `/proc/device-tree/model` = `Rockchip RK3399 AI3399-C Lvds(GM8775C)`
* cmdline: `androidboot.hwid=AI3399C_V2_11.50.54`
  `androidboot.o_lvds=01,02,00,00,00,01,00` `androidboot.o_fb=01,00,b4,1920,1080`
* vendor 模块：8723ds.ko、mali_kbase.ko、8723cs/8821cs/8822bs、bcmdhd 等
* verifiedbootstate=orange：无 AVB 阻拦，可自由替换 boot/rootfs
