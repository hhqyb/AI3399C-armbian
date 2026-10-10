# 部署与实测记录

## 2026-10-10

| 时间 | 动作 | 结果 |
|---|---|---|
| 21:00 | GitHub Actions 构建（ophub 流水线，board=aio-3399c，kernel 6.18.55，resolute） | ✅ 产出 `Armbian_26.8.1_rockchip_aio-3399c_resolute_6.18.55_server_2026.10.10.img.gz` |
| 21:09 | 镜像经 adb 写入 SD 卡（mmcblk1，3.4 GB） | ✅ GPT 校验通过；镜像自带 idbloader@0x40 + u-boot FIT@0x4000 + ext4 boot/rootfs |
| 21:12 | 备份 eMMC loader 区（0x40–0x4000）至 emmc-loader-backup.bin | ✅ md5 6856bdfabf571c83c86fd45d204d1cd8 |
| 21:13 | 清零 eMMC loader 区强制 SD 启动（RK3399 BootROM 顺序 SPI→eMMC→SD） | ⚠️ 读回仍见旧数据（疑似缓存），重启后 adb 消失、局域网无踪迹，板子状态未知 |
| 21:30 | 局域网扫描 + SSH root/1234 探测 | ❌ 未发现 Armbian 主机（网线已插，疑似 U-Boot/内核未起或 GMAC 未链路） |
| 21:36 | 定制镜像工作流 `customize-image.yml`：串口 console 改 115200、注入 SSH 公钥、root/1234 | ✅ [customized release](https://github.com/hhqyb/AI3399C-armbian/releases/tag/customized) |

## 硬件接入现状

* OTG 线 → 电脑（adb/rockusb）
* 串口 → 电脑 COM1（主板 16550，最高 115200；板端 U-Boot 为 1500000，
  故 U-Boot 阶段不可见，定制内核 console 已改为 115200）
* 网线已插路由器
* 板上有 RECOVERY / Reset 按键

## 下一步

1. 接 HDMI 观察上电输出（extlinux 已带 `video=HDMI-A-1:1920x1080@60e`）。
2. SD 卡换定制镜像（读卡器直写，或恢复 Android 后经 adb 远程写入）。
3. 若 U-Boot 阶段仍需可见：换 CH340/CP2102/FTDI USB-TTL（支持 1.5 Mbps）。
4. 需要时 RECOVERY 键进 loader，RKDevTool 重刷官方固件救砖。
