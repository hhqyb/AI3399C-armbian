# serial-log.ps1 — capture COM1 traffic to a log file (raw bytes as text/hex)
param(
    [string]$Port = 'COM1',
    [int]$Baud = 115200,
    [int]$Seconds = 300,
    [string]$LogFile = 'E:\AI3399-C\armbian-build\serial-capture.log'
)
$sp = New-Object System.IO.Ports.SerialPort $Port, $Baud, 'None', 8, 'One'
$sp.ReadTimeout = 1000
$sp.Open()
$sp.DiscardInBuffer()
$t0 = Get-Date
Set-Content -Path $LogFile -Value "=== capture start $(Get-Date -Format o) @ $Baud ===" -Encoding UTF8
$sb = New-Object System.Text.StringBuilder
while (((Get-Date) - $t0).TotalSeconds -lt $Seconds) {
    try {
        $chunk = $sp.ReadExisting()
        if ($chunk -and $chunk.Length -gt 0) {
            $bytes = [System.Text.Encoding]::GetEncoding(28591).GetBytes($chunk)
            foreach ($b in $bytes) {
                if ($b -ge 32 -and $b -lt 127) { [void]$sb.Append([char]$b) }
                elseif ($b -eq 10) { [void]$sb.AppendLine() }
                elseif ($b -eq 13) { }
                else { [void]$sb.Append(('[{0:X2}]' -f $b)) }
            }
            Add-Content -Path $LogFile -Value $sb.ToString() -Encoding UTF8
            [void]$sb.Clear()
        }
        else { Start-Sleep -Milliseconds 100 }
    } catch { Start-Sleep -Milliseconds 100 }
}
$sp.Close()
if ($sb.Length -gt 0) { Add-Content -Path $LogFile -Value $sb.ToString() -Encoding UTF8 }
Add-Content -Path $LogFile -Value "=== capture end $(Get-Date -Format o) ===" -Encoding UTF8
Write-Host "log written: $LogFile"
