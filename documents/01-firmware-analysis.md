# AI3399-C 官方 Android 10 固件分析报告

固件文件：`AI3399C_RK3399_Android10_A_20241031.162147.img`（1.66 GB）
分析工具：`tools/extract_rkaf.py`、`tools/inspect_boot_dtb.py`、`tools/extract_rsce.py`

## 1. 固件容器结构

外层为 Rockchip `RKFW` 容器，内含两段：

| 段 | 内容 | 大小 |
|---|---|---|
| BOOT | `MiniLoaderAll.bin`（RK3399 一级引导 + DDR 初始化） | 420,174 B |
| embedded-update.img | `RKAF` 打包的分区镜像（firmware.img） | 1,661,861,892 B |

`RKAF` 头部 2048 字节，13 个分区条目（每条 112 字节，见
[suyulin/afptool-rs](https://github.com/suyulin/afptool-rs) 的结构定义）。
分区清单（`vendor/partition-metadata.txt` 有完整字段）：

| 分区 | 文件 | 包内偏移 | 大小 |
|---|---|---|---|
| package-file | package-file | 0x800 | 686 B |
| bootloader | Image/MiniLoaderAll.bin | 0x1000 | 420,174 B |
| parameter | Image/parameter.txt | 0x68008 | 650 B |
| trust | Image/trust.img (ATF/OP-TEE) | 0x68800 | 4 MiB |
| uboot | Image/uboot.img | 0x468800 | 4 MiB |
| misc | Image/misc.img | 0x868800 | 48 KiB |
| baseparameter | Image/baseparameter.img | 0x874800 | 1 MiB |
| boot | Image/boot.img | 0x974800 | 29.9 MB |
| dtbo | Image/dtbo.img | 0x2604000 | 607 B（空 overlay） |
| vbmeta | Image/vbmeta.img | 0x2604800 | 4 KiB |
| recovery | Image/recovery.img | 0x2605800 | 47.4 MB |
| super | Image/super.img (system/vendor) | 0x556F000 | 1.5 GB |

## 2. GPT 分区布局（parameter.txt，TYPE: GPT）

`CMDLINE:mtdparts=rk29xxnand:...`，单位 512 B 扇区：

| 分区 | 起始扇区 | 扇区数 | 大小 | eMMC 节点 |
|---|---|---|---|---|
| uboot | 0x4000 (8 MiB) | 0x2000 | 4 MiB | mmcblk2p1 |
| trust | 0x6000 | 0x2000 | 4 MiB | mmcblk2p2 |
| misc | 0x8000 | 0x2000 | 4 MiB | mmcblk2p3 |
| dtb | 0xA000 | 0x2000 | 4 MiB | mmcblk2p4（实测全零，未使用） |
| dtbo | 0xC000 | 0x2000 | 4 MiB | mmcblk2p5 |
| vbmeta | 0xE000 | 0x800 | 1 MiB | mmcblk2p6 |
| boot | 0xE800 | 0x16000 | 44 MiB | mmcblk2p7 |
| security | 0x24800 | 0x2000 | 4 MiB | mmcblk2p8 |
| recovery | 0x26800 | 0x30000 | 96 MiB | mmcblk2p9 |
| backup | 0x56800 | 0x38000 | 112 MiB | mmcblk2p10 |
| cache | 0x8E800 | 0xC0000 | 384 MiB | mmcblk2p11 |
| metadata | 0x14E800 | 0x8000 | 16 MiB | mmcblk2p12 |
| frp | 0x156800 | 0x400 | 512 KiB | mmcblk2p13 |
| super | 0x156C00 | 0x614000 | ~3.07 GiB | mmcblk2p14 |
| userdata | 0x76AC00 | grow | 剩余（~25 GiB） | mmcblk2p15 |

引导区（GPT 之外）：扇区 0x40 起写入 `MiniLoaderAll.bin`，
`uboot.img` 写入 uboot 分区，`trust.img` 写入 trust 分区。
eMMC 总容量 ≈ 29.2 GiB（32 GB eMMC），另有 SD 卡槽（mmcblk1）。

## 3. 启动链

```
BootROM → MiniLoaderAll(idbloader@0x40, DDR init)
        → uboot.img(@0x4000) + trust.img(ATF/OP-TEE@0x6000)
        → U-Boot boot_android: 读取 boot 分区 Android boot.img
           ├─ kernel:  Linux 4.19.172 aarch64 (vendor BSP, gcc 6.3.1)
           ├─ ramdisk: vendor init
           └─ second:  RSCE 资源容器（内含 3 份 DTB + logo）
        → androidboot.dtb_idx 选 DTB → 内核 → Android 10
```

* `verifiedbootstate=orange`，无 AVB 校验拦截，可自由替换 boot/rootfs。
* U-Boot 会**前置**自己的参数（`storagemedia=emmc androidboot.dtb_idx=...`
  `androidboot.hwid=AI3399C_V2_11.50.54 androidboot.o_lvds=... androidboot.o_mipi2lvds=...`
  `androidboot.o_fb=01,00,b4,1920,1080...`），boot.img 内 cmdline 追加其后。

## 4. RSCE 资源容器（boot.img second 段，0x58200 B）

魔数 `RSCE`，内含 3 个 FDT：

* dtb[0] @0xC00、dtb[1] @0x1AE00：TC358775 MIPI→LVDS 变体（`signway,tc358775-i2c`）
* dtb[2] @0x35000：**GM8775C MIPI→LVDS 变体（`signway,gm8775c-i2c`）——当前实机使用**
  （`/proc/device-tree/model` = `Rockchip RK3399 AI3399-C Lvds(GM8775C)`）

## 5. 硬件清单（来自 DTB + 实机 adb 采集）

| 外设 | DTS 节点 / 依据 | 备注 |
|---|---|---|
| SoC | RK3399（4×A53 + 2×A72） | DDR 由 MiniLoaderAll 初始化 |
| eMMC | sdhci@fe330000 | 32 GB |
| SD 卡 | dwmmc@fe320000 | mmcblk1 |
| 千兆以太网 | ethernet@fe300000 `rockchip,rk3399-gmac` + external-gmac-clock | 实机 eth0 正常 |
| WiFi | SDIO `024C:D723` = **RTL8723DS** | 驱动 `8723ds.ko`（vendor 自带） |
| 蓝牙 | bluetooth-platdata（UART） | BCM/RTK 固件齐全 |
| 显示 | DSI@ff960000 → **GM8775C** MIPI→LVDS → 1920×1080 LVDS 屏 | 另有 HDMI、eDP |
| 背光 | pwm-backlight（PWM0/1/2/3 @ff420000） | |
| 音频 | ES8388 @I2C0 0x11（`everest,es8388`） | SPDIF、HDMI 音频 |
| RTC | HYM8563 @0x51 / PT7C4337 @0x68 | I2C4 |
| 传感器 | MMA8452 加速度计 @I2C5 0x1D | |
| Type-C | FUSB302 @I2C2 0x22 | USB3 + PD |
| USB | 2×DWC3 (USB3) + EHCI/OHCI | |
| PCIe | pcie@f8000000 | 未启用 |
| 4G 模块 | rk-modem（wwan0 已出现） | |
| 其他 | SARADC、TSADC、看门狗、GPIO keys、LED | |

## 6. Armbian 适配要点

1. **内核/驱动**：vendor 4.19.172 内核 + `/vendor/lib/modules`（8723ds.ko、
   mali_kbase.ko 等）保证全硬件可用；主线内核（5.10–6.18）由
   ophub/kernel 提供，含大量 RTL8723 系驱动，GM8775C 显示桥无主线驱动
   （LVDS 屏需 vendor 内核或自行移植 DSI-LVDS bridge 驱动）。
2. **引导**：保留 vendor 引导链（MiniLoaderAll + uboot.img + trust.img），
   Armbian 内核/initramfs 打包成 Android boot.img 格式（含 RSCE second 段
   传 DTB），U-Boot `boot_android` 直接拉起 —— 与原厂启动路径完全一致。
3. **分区**：复用 parameter.txt 布局，把 super/userdata 合并为
   `rootfs:grow` ext4 分区（构建时生成新 parameter）。
4. **刷写**：RKDevTool 刷 update.img（loader 自动生成 GPT），或 adb dd
   进现有分区做无损试装。
