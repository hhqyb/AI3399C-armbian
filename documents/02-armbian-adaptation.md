# Armbian 适配方案（结合 ophub/amlogic-s9xxx-armbian）

## 1. 为什么可以直接复用 ophub 项目

[ophub/amlogic-s9xxx-armbian](https://github.com/ophub/amlogic-s9xxx-armbian)
虽然面向 Amlogic 盒子，但其 **arm64 Armbian 镜像重建流水线**与内核仓库
[ophub/kernel](https://github.com/ophub/kernel) 已经支持大量 **RK3399** 设备，
其设备列表中就包含 **`aio-3399c` / `aio-3399c-ai`**（Firefly AIO-3399C）。
本板 AI3399-C 与 Firefly AIO-3399C 同源（DTB 中同样使用
GM8775C / TC358775 MIPI→LVDS 桥），因此适配主线为：

* 设备 profile：`aio-3399c`
* 内核：ophub/kernel 的 rockchip 系列（5.10 / 5.15 / 6.1 / 6.6 / 6.12）
* 组装方式：`ophub/amlogic-s9xxx-armbian` action（build_target=armbian）
  从官方 Armbian 镜像抽取 rootfs，替换内核 / boot 文件 / u-boot 后重新打包

## 2. 三条启动路线

| 路线 | 引导链 | 内核 | 硬件支持 | 状态 |
|---|---|---|---|---|
| A. ophub 标准（默认） | ophub u-boot-aio-3399c + extlinux | ophub 6.x/5.x | 网口/USB/eMMC/WiFi(8723ds 视内核配置) | **CI 构建中** |
| B. 原厂引导链 + Armbian rootfs | MiniLoaderAll + uboot.img + trust.img + Android boot.img 包装 | vendor 4.19.172 + /vendor/lib/modules | 全硬件（含 LVDS 屏、8723ds、Mali） | 见 documents/03 |
| C. armbian/build 定制板级 | mainline u-boot + armbian/build | mainline + 移植 DTS | 需移植 GM8775C/8723ds | 后续 |

路线 A 由本仓库 `.github/workflows/build-armbian.yml` 一键构建：
GitHub Actions（arm64 runner）下载官方 Armbian 镜像 → 调用
`ophub/amlogic-s9xxx-armbian@main` 重建 → 发布到 Releases。

## 3. 路线 A 使用方法

1. GitHub 仓库页 → Actions → `Build Armbian for AI3399-C` → Run workflow：
   * `armbian_board = aio-3399c`（默认）
   * `armbian_kernel = 6.1.y`（默认；WiFi/兼容性优先可选 5.15.y）
   * `armbian_edition = server`
2. 构建完成后到 Releases 下载 `Armbian_*_aio-3399c_*.img.xz`。
3. 烧录：
   * **SD 卡启动（推荐首试）**：`dd`/balenaEtcher 写入 SD 卡，插卡上电；
   * **eMMC 安装**：SD 启动进系统后执行 `armbian-install`，
     按提示选择 aio-3399c 写入 eMMC；
   * **RKDevTool 整包刷写**：见 documents/03 的 update.img 流程
     （工具在 `AI3399-C固件烧录工具/RKDevTool_v3.28_for_window`）。
4. 首次登录：`root / 1234`，按提示改密码、建用户。

## 4. 路线 B（原厂引导链）设计

目标：LVDS 屏、RTL8723DS WiFi/BT、Mali GPU、ES8388 全部开箱即用。

```
boot 分区 = Android boot.img:
    kernel  = vendor 4.19.172 Image（从 stock boot.img 提取）
    ramdisk = Armbian initrd（从 Armbian 官方镜像 boot 分区提取）
    second  = RSCE（dtb[2] GM8775C 变体）
    cmdline = root=LABEL=armbian-root rootwait rw console=ttyFIQ0,1500000 ...
rootfs 分区 = Armbian rootfs ext4（LABEL=armbian-root）
    + /lib/modules/4.19.172/（vendor 模块，adb 拉取自实机）
    + /vendor/etc/firmware（RTL/BT 固件）
```

刷写到 eMMC 的两种方式：

* **无损试装（可 adb 直接操作）**：把 boot.img dd 到 `by-name/boot`，
  rootfs dd 到 `by-name/userdata`，cmdline 用
  `root=/dev/disk/by-partlabel/userdata`。Android 随时可救回（重刷官方固件）。
* **正式安装**：新 parameter.txt（super/userdata 合并为 `rootfs:grow`），
  afptool 打成 update.img，RKDevTool 整包刷写。

## 5. 已知差异 / 待办

* GM8775C（及 TC358775）MIPI→LVDS 桥在主线内核无驱动，路线 A 下
  LVDS 屏暂无输出（HDMI 可用）；LVDS 需路线 B（vendor 内核）或移植驱动。
* RTL8723DS：主线可用 `rtl8723ds`/`rtw88` 视内核配置；vendor 内核自带
  `8723ds.ko`（已拉取备份）。
* 千兆网、eMMC、USB、Type-C（FUSB302）、ES8388 声卡在路线 A 内核均有
  主线驱动。
* 实机验证：见 documents/04（刷写记录与测试结果）。
