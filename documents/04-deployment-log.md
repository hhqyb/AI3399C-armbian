# 部署与实测记录

## 2026-10-10 ~ 10-11 最终结果：✅ 适配成功

**Armbian（trixie，vendor 4.19.172 内核）已在 AI3399-C 上从 eMMC 自主启动并稳定运行。**

| 项目 | 状态 | 证据 |
|---|---|---|
| 系统 | ✅ Armbian trixie (arm64) | `uname -a`: Linux **ai3399c** 4.19.172 aarch64 |
| 设备树 | ✅ 原厂 GM8775C 变体 | `/proc/device-tree/model` = Rockchip RK3399 AI3399-C Lvds(GM8775C) |
| 有线网 | ✅ DHCP 正常 | end0 = 192.168.100.122，SSH 可达 |
| WiFi | ✅ RTL8723DS | wlan0 + p2p0（8723ds.ko 开机自动加载） |
| GPU | ✅ Mali | /dev/mali0、/dev/dri/renderD128 |
| 显示 | ✅ LVDS 1920x1080 | fb0: U:1920x1080p-0 |
| 音频 | ✅ ES8388 + HDMI | /proc/asound: rockchipes8388c、hdmisound |
| 存储 | ✅ rootfs 26 GB（24 GB 可用） | /dev/mmcblk2p15（userdata 分区，resize2fs 已扩容） |
| 重启持久 | ✅ | 重启后全部服务/驱动自动恢复 |

## 启动链（最终形态）

```
BootROM → eMMC idbloader(0x40) → uboot.img(0x4000) + trust.img(0x6000)
  → U-Boot boot_android → eMMC boot 分区 Android boot.img
      ├─ kernel:  vendor 4.19.172（原厂）
      ├─ ramdisk: gadget 调试 initramfs（USB 串口/telnet 应急通道）
      └─ second:  RSCE（GM8775C DTB）
  → initramfs 挂载 userdata(ext4) → switch_root → systemd (Armbian trixie)
```

## 关键经验（踩坑记录）

1. **串口**：板子调试串口是 Type-C（USB），PC 的 COM1 是主板 16550（≤115200），
   原厂 fiq-debugger 波特率 1500000——曾导致长期"串口无输出"假象；
   DTB 内 `rockchip,baudrate` 可 patch 为 115200。
2. **uboot.img 不可修改**：LOADER 封装带校验，改一个字节加载器即拒绝
   （表现为回落 rockusb 或 eMMC Android）。
3. **BootROM 降级**：SD 引导链无效时自动回落 eMMC；SD 有效时优先 SD。
4. **boot.img 格式**：与原厂逐字节同构（v5 做法：仅换 ramdisk）即可被
   boot_android 接受；initramfs 提供应急调试通道。
5. **Armbian 首次登录初始化**会锁定 root 密码登录（需 console 初始化后放行）。
6. **Windows ssh askpass 密码认证时好时坏**，paramiko 稳定。

## 维护入口

- SSH：`root@192.168.100.122`（密码见会话记录；管理公钥 `ai3399c-admin` 已装）
- 救砖：RECOVERY 键进 loader，RKDevTool 重刷官方固件
  `AI3399C_RK3399_Android10_A_20241031.162147.img`；或 SD 卡启动
  `vendor-boot` release 的完整镜像
- 构建：GitHub Actions `build-vendor-image.yml` 一键产出完整刷机镜像
