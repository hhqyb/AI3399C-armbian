# flash-sd.ps1 — write the route-B image to the SD card (run as Administrator)
# Verifies the target disk by exact size before writing.
param(
    [int]$DiskNumber = 5,
    [string]$Image = 'E:\AI3399-C\armbian-build\Armbian_vendor419_AI3399C.img',
    [long]$ExpectedSize = 31370248192  # SD card size in bytes
)

$ErrorActionPreference = 'Stop'
Start-Transcript -Path 'E:\AI3399-C\armbian-build\flash-sd.log' -Force | Out-Null
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Must run as Administrator'
}

$target = "\\.\PhysicalDrive$DiskNumber"
Get-Disk | Format-Table Number, FriendlyName, @{n='SizeGB';e={$_.Size/1GB}} | Out-String | Write-Host
$disk = Get-Disk -Number $DiskNumber
$size = $disk.Size
if ($size -ne $ExpectedSize) {
    throw "Disk $DiskNumber size $size != expected $ExpectedSize — refusing to write"
}
Write-Host "Target $target size OK ($size bytes) — $($disk.FriendlyName)"

# sanity: first 4MB of the image must not be all zeros (loader area)
$check = New-Object byte[] 512
$in = [System.IO.File]::OpenRead($Image)
$in.Seek(32768, 'Begin') | Out-Null
[void]$in.Read($check, 0, 512)
$in.Close()
if (($check | Where-Object { $_ -ne 0 } | Measure-Object).Count -eq 0) {
    throw 'Image loader area is empty — aborting'
}
$fs = [System.IO.File]::Open($target, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::ReadWrite)

$bufSize = 16MB
$buf = New-Object byte[] $bufSize
$in = [System.IO.File]::OpenRead($Image)
$in.Seek(0, 'Begin') | Out-Null
$total = $in.Length
$written = 0
$sw = [System.Diagnostics.Stopwatch]::StartNew()
while ($written -lt $total) {
    $n = $in.Read($buf, 0, [Math]::Min($bufSize, $total - $written))
    if ($n -le 0) { break }
    $fs.Write($buf, 0, $n)
    $written += $n
    if ($written % 512MB -lt $bufSize) {
        $speed = [double]($written / 1MB) / [double]$sw.Elapsed.TotalSeconds
        $msg = 'written {0:N0} / {1:N0} MB  ({2:N1} MB/s)' -f [double]($written / 1MB), [double]($total / 1MB), $speed
        Write-Host $msg
    }
}
$fs.Flush()
$fs.Close()
$in.Close()
Write-Host "done: $written bytes written to $target in $($sw.Elapsed.TotalSeconds) s"
Stop-Transcript | Out-Null
