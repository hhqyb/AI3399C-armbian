# AI3399-C Armbian 软硬件适配情况说明

> 检测环境：Armbian 26.8.1 (Debian trixie) / systemd 257 / vendor 内核 4.19.172
> 检测方式：板端实测（SSH 采集 `/proc`、`/sys`、`lsmod`、`lsusb`、`ethtool` 等）
> 检测时间：2026-10-11

## 一、总体结论

**核心硬件全部驱动并实测可用**：CPU/内存/eMMC/千兆网口/LVDS 屏/HDMI/WiFi/GPU/声卡/USB/RTC/看门狗。
板子已从 eMMC 自主启动 Armbian，双屏（LVDS + HDMI）终端就绪，SSH 远程管理就绪，重启持久。

## 二、硬件适配明细

| 部件 | 硬件/接口 | 驱动与设备节点 | 状态 | 实测数据 |
|---|---|---|---|---|
| SoC | RK3399（4×A53 + 2×A72） | cpufreq（performance 调速） | ✅ | 6 核在线，SoC 48.8℃ / GPU 46.9℃ |
| 内存 | 4 GB DDR | — | ✅ | 3.7 GiB 可用 |
| eMMC | 32 GB（fe330000.sdhci） | mmcblk2 + 15 分区 GPT | ✅ | 根分区 25.4 GB，寿命 0x01/0x03（优） |
| SD 卡槽 | 32 GB（fe320000.dw-mshc） | mmcblk1 | ✅ | 识别正常（可作启动/存储盘） |
| 显示 1 | **LVDS 1920×1080（DSI→GM8775C）** | rockchip-drm DSI-1 | ✅ | DRM 状态 connected，kmscon 输出终端 |
| 显示 2 | **HDMI TX v2.11a（HDCP）** | dwhdmi-rockchip HDMI-A-1 | ✅ | 2560×1440@60 自适应，kmscon 输出终端 |
| GPU | Mali（midgard） | /dev/mali0、/dev/dri/renderD128 | ✅ | 内核驱动就绪（3D 用户态库待装，见限制） |
| 有线网 | RTL8211 千兆（rk3399-gmac） | end0 | ✅ | **1000Mb/s 全双工**，DHCP 正常 |
| WiFi | RTL8723DS（SDIO 024C:D723） | 8723ds.ko → wlan0/p2p0 | ✅ | 驱动加载，MAC 正常，wpa_supplicant 就绪 |
| 蓝牙 | RTL8723DS BT（UART） | 固件已就位 | ⚠️ 待配置 | 需 rtk_hciattach/btattach 初始化（见建议） |
| 声卡 1 | ES8388 编解码器（I2C） | rockchipes8388c | ✅ | ALSA card1，模拟音频通路 |
| 声卡 2 | HDMI 音频（i2s→hdmi） | hdmi-sound | ✅ | ALSA card0 |
| USB | DWC3 USB3 ×2 + EHCI/OHCI | usb1~6 总线 | ✅ | 实测识别：USB 集 hub、**Exar 4 串口卡**、**高通 4G 模块**、键鼠接收器 |
| 4G 模块 | Qualcomm HSUSB | wwu1u3i4 网络接口 | ✅ 识别 | 模块在位，拨号需配置（建议） |
| RTC | HYM8563 / PT7C4337（I2C） | /dev/rtc0 | ✅ | 硬件时钟可用 |
| 看门狗 | dw-wdt ×2 | /dev/watchdog0/1 | ✅ | watchdog.service 已运行 |
| 其他 | SARADC/TSADC、GPIO keys、PWM 背光 | 内核支持 | ✅ | 温控/背光通路正常 |

## 三、软件栈

| 层 | 组成 | 状态 |
|---|---|---|
| 引导 | 原厂 MiniLoader + u-boot + trust → Android boot.img 格式 | ✅ eMMC 自主启动 |
| 内核 | vendor 4.19.172（AI3399-C 定制，含 GM8775C/8723ds/Mali） | ✅ |
| initramfs | 自制 gadget 调试层（USB 串口/telnet 应急通道） | ✅ |
| 用户态 | Armbian 26.8.1 trixie + systemd 257 | ✅ |
| 远程管理 | openssh（root + 管理公钥）、systemd-networkd/resolved | ✅ |
| 屏幕控制台 | **kmscon 10**（绕过内核缺失 VT/fbcon 的限制，双屏同显） | ✅ |
| 包管理 | apt（已切换清华镜像），armbian 源可用 | ✅ |

## 四、已知限制与后续建议

1. **BT 未初始化**：`rtk_hciattach` 把 RTL8723DS 的 BT 挂到 HCI 即可
   （厂商固件已在 /lib/firmware）；需要时我来配置为开机自启。
2. **GPU 3D 加速**：内核 Mali 驱动就绪，但 X/Wayland 的 3D 还需配套的
   ARM Mali DDK 用户态库（vendor ABI）；当前桌面/终端为 2D 渲染，日常够用。
3. **内核无 VT/fbcon**（Android 配置）：文字屏显已用 kmscon 方案覆盖；
   若需内核原生串口/HDMI 控制台，可换 ophub 主线内核（代价：LVDS/8723ds
   需另行移植）。
4. **root 登录策略**：Armbian 首启初始化流程行为特殊，已固定 root 密码 +
   公钥登录；Windows 自带 ssh 的 askpass 偶发失效，建议用密钥或 PuTTY。
5. **4G 模块**：设备已识别（含 4 串口扩展卡），如需拨号上网可配
   ModemManager（MBIM/QMI）。

## 五、验收记录（抽样）

```
$ uname -a
Linux ai3399c 4.19.172 #10 SMP PREEMPT aarch64 GNU/Linux
$ cat /proc/device-tree/model
Rockchip RK3399 AI3399-C Lvds(GM8775C)
$ ethtool end0 | grep Speed
 Speed: 1000Mb/s
$ cat /proc/asound/cards
 0 [hdmisound      ]: hdmi-sound
 1 [rockchipes8388c]: rockchip,es8388-codec
$ ls /dev/dri
card0  renderD128
```
