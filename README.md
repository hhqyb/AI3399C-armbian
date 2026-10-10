# AI3399C-armbian

瑞芯微 RK3399 **AI3399-C** 开发板（南昌新威视 / njxwst.com，hwid `AI3399C_V2`）
的 Armbian 适配仓库，基于 [ophub/amlogic-s9xxx-armbian](https://github.com/ophub/amlogic-s9xxx-armbian)
的 arm64 镜像重建流水线与其设备 profile `aio-3399c`。

## 快速开始

1. 本仓库 **Actions** → `Build Armbian for AI3399-C` → **Run workflow**
   （默认 `armbian_board=aio-3399c`、`armbian_kernel=6.1.y`、server 版）。
2. 构建产物发布到 **Releases**，下载 `Armbian_*_aio-3399c_*.img.xz`。
3. 烧录到 SD 卡启动（或 `armbian-install` 装入 eMMC）。
   默认账号 `root`，密码 `1234`。

## 仓库内容

| 路径 | 说明 |
|---|---|
| `.github/workflows/build-armbian.yml` | GitHub Actions 构建流水线（适配自 ophub） |
| `documents/01-firmware-analysis.md` | 官方 Android 10 固件逆向分析（分区表/启动链/DTB/硬件清单） |
| `documents/02-armbian-adaptation.md` | 适配方案（三条启动路线对比） |
| `tools/` | 固件解析工具（RKAF 解包、boot.img/RSCE/DTB 解析） |
| `vendor/` | 原厂 parameter.txt、分区元数据 |

## 板卡概况

* SoC：RK3399（双核 A72 + 四核 A53），32 GB eMMC + SD 卡槽
* 显示：DSI → GM8775C → 1920×1080 LVDS（另支持 HDMI / eDP）
* 网络：RTL8211 千兆以太网（`rockchip,rk3399-gmac`）
* 无线：RTL8723DS SDIO WiFi + BT
* 音频：ES8388；USB3 ×2、Type-C（FUSB302）、PCIe、4G 模块接口

详细硬件与固件分析见 [documents/01-firmware-analysis.md](documents/01-firmware-analysis.md)。

## 免责与恢复

刷写 eMMC 有变砖风险，优先从 SD 卡启动验证。救砖：板载 OTG 口进 MaskRom/loader
模式（`adb reboot loader`），用 `AI3399-C固件烧录工具/RKDevTool_v3.28`
重刷官方固件 `AI3399C_RK3399_Android10_A_20241031.162147.img`。
