# patch-sd-boot-via-adb.ps1 — push boot.img v2 to the SD card through Android adb
param(
    [string]$BootImg = 'E:\AI3399-C\armbian-build\boot-armbian-vendor-v2.img',
    [int]$SeekSector = 59904   # 0xE800 = start of "boot" partition per parameter-armbian.txt
)
$ErrorActionPreference = 'Stop'

# 1. SD card present?
$parts = adb shell "cat /proc/partitions" | Out-String
if ($parts -notmatch 'mmcblk1\s') { throw 'SD card (mmcblk1) not visible on the board' }
Write-Host 'SD card (mmcblk1) detected'

# 2. GPT sanity on SD
$gpt = adb shell "dd if=/dev/block/mmcblk1 bs=512 skip=1 count=1 2>/dev/null | head -c 8" | Out-String
if ($gpt -notmatch 'EFI PART') { throw "SD card has no GPT: $gpt" }
Write-Host 'GPT signature OK'

# 3. push and write
adb push $BootImg /data/local/tmp/boot-v2.img
adb shell "dd if=/data/local/tmp/boot-v2.img of=/dev/block/mmcblk1 bs=512 seek=$SeekSector conv=notrunc && sync"
Write-Host 'boot.img written to SD boot partition'

# 4. verify
$md5_local = (Get-FileHash $BootImg -Algorithm MD5).Hash.ToLower()
$md5_dev = (adb shell "md5sum /data/local/tmp/boot-v2.img").Split(' ')[0].ToLower()
if ($md5_local -ne $md5_dev) { throw "md5 mismatch: local=$md5_local dev=$md5_dev" }
Write-Host "md5 verified: $md5_local"
$head = adb shell "dd if=/dev/block/mmcblk1 bs=1 skip=$(59904 * 512) count=8 2>/dev/null" | Out-String
if ($head -notmatch 'ANDROID!') { throw "boot partition magic missing: $head" }
Write-Host 'ANDROID! magic verified at boot partition'
Write-Host 'ALL DONE - power cycle with the SD card inserted'
