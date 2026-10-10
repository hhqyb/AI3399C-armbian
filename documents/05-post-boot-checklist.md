# 启动成功后的验收清单（route B）

## 判定标志（任一即可确认内核起来了）

1. 局域网出现新主机，SSH `root/1234` 可登录（Armbian 默认凭据）；
2. COM1@115200 出现内核日志（boot.img v3 已配置全 UART console + earlycon）；
3. LVDS 屏 / HDMI 出现内核日志或登录提示（console=tty1）。

## 登录后执行（远程自动化）

```bash
uname -a                       # 期望: Linux ... 4.19.172 ... aarch64
cat /proc/device-tree/model    # 期望: Rockchip RK3399 AI3399-C Lvds(GM8775C)
ip addr                        # eth0 应有 DHCP 地址

# 1. 安装 vendor 内核模块（8723ds WiFi、mali 等）与固件
#    tarball 已备好: vendor-modules-4.19.172.tar.xz / vendor-firmware.tar.xz
sudo mkdir -p /lib/modules/4.19.172
sudo tar -xJf vendor-modules-4.19.172.tar.xz -C /tmp && sudo cp /tmp/vendor-modules/*.ko /lib/modules/4.19.172/
sudo depmod -a 4.19.172
sudo tar -xJf vendor-firmware.tar.xz -C /tmp && sudo cp -a /tmp/vendor-firmware/. /lib/firmware/

# 2. 验证
lsmod; modprobe 8723ds && ip link        # WiFi
modprobe mali_kbase                       # GPU
aplay -l                                  # ES8388 声卡
cat /sys/class/graphics/fb0/modes         # 显示（LVDS/HDMI）
```

## 后续

- rootfs 扩容（rootfs 分区 1636 MiB，SD/eMMC 剩余空间可扩展）
- 安装 armbian-config / 配置 WiFi、显示
- 若 SD 验证通过 → 安装进 eMMC（RKDevTool 整包 update.img 或 dd）
