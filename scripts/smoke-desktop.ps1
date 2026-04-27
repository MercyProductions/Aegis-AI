param(
    [string]$ExePath = "",
    [string]$OutputDir = "",
    [int]$LoginWaitSeconds = 2,
    [int]$SetupWaitSeconds = 2,
    [int]$DashboardWaitSeconds = 8,
    [double]$MinimumNonBlackRatio = 0.02,
    [switch]$SkipDashboard
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:NativeLoaded = $false

function Resolve-ProjectPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $Path))
}

function Ensure-NativeTypes {
    if ($script:NativeLoaded) {
        return
    }

    Add-Type -AssemblyName System.Drawing
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class AegisSmokeNative
{
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int x, int y);

    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
}
"@
    $script:NativeLoaded = $true
}

function Wait-ForMainWindow {
    param(
        [int]$ProcessId,
        [int]$TimeoutSeconds = 15
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        if ($process.MainWindowHandle -ne [IntPtr]::Zero) {
            return $process.MainWindowHandle
        }
        Start-Sleep -Milliseconds 200
    } while ((Get-Date) -lt $deadline)

    throw "Timed out waiting for the Aegis desktop main window."
}

function Get-WindowRectInfo {
    param([IntPtr]$Handle)

    $rect = New-Object AegisSmokeNative+RECT
    if (-not [AegisSmokeNative]::GetWindowRect($Handle, [ref]$rect)) {
        throw "Could not read the Aegis window rectangle."
    }

    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -lt 320 -or $height -lt 240) {
        throw "Aegis window is unexpectedly small: ${width}x${height}."
    }

    [pscustomobject]@{
        Left = $rect.Left
        Top = $rect.Top
        Right = $rect.Right
        Bottom = $rect.Bottom
        Width = $width
        Height = $height
    }
}

function Capture-Window {
    param(
        [IntPtr]$Handle,
        [string]$Path
    )

    $rect = Get-WindowRectInfo -Handle $Handle
    $bitmap = New-Object System.Drawing.Bitmap $rect.Width, $rect.Height, ([System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
        return [pscustomobject]@{
            Path = $Path
            Width = $rect.Width
            Height = $rect.Height
            Metrics = Measure-ImagePixels -Bitmap $bitmap
        }
    } finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

function Measure-ImagePixels {
    param([System.Drawing.Bitmap]$Bitmap)

    $sampleStep = [Math]::Max(1, [Math]::Floor([Math]::Max($Bitmap.Width, $Bitmap.Height) / 420))
    $total = 0
    $nonBlack = 0
    $accent = 0
    $bright = 0

    for ($y = 0; $y -lt $Bitmap.Height; $y += $sampleStep) {
        for ($x = 0; $x -lt $Bitmap.Width; $x += $sampleStep) {
            $pixel = $Bitmap.GetPixel($x, $y)
            $max = [Math]::Max($pixel.R, [Math]::Max($pixel.G, $pixel.B))
            $min = [Math]::Min($pixel.R, [Math]::Min($pixel.G, $pixel.B))
            $total++
            if ($max -gt 6) {
                $nonBlack++
            }
            if ($max -gt 48) {
                $bright++
            }
            if (($max - $min) -gt 24 -and $max -gt 32) {
                $accent++
            }
        }
    }

    [pscustomobject]@{
        SampledPixels = $total
        NonBlackRatio = if ($total -gt 0) { $nonBlack / $total } else { 0.0 }
        BrightRatio = if ($total -gt 0) { $bright / $total } else { 0.0 }
        AccentRatio = if ($total -gt 0) { $accent / $total } else { 0.0 }
    }
}

function Assert-VisibleCapture {
    param(
        [object]$Capture,
        [double]$MinimumRatio
    )

    $ratio = [double]$Capture.Metrics.NonBlackRatio
    if ($ratio -lt $MinimumRatio) {
        throw "Smoke capture appears blank: $($Capture.Path) non-black ratio $([Math]::Round($ratio, 4)) is below $MinimumRatio."
    }
}

function Invoke-MouseClick {
    param(
        [int]$X,
        [int]$Y
    )

    [AegisSmokeNative]::SetCursorPos($X, $Y) | Out-Null
    Start-Sleep -Milliseconds 80
    [AegisSmokeNative]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 50
    [AegisSmokeNative]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
}

function Invoke-SmokeLogin {
    param([IntPtr]$Handle)

    $rect = Get-WindowRectInfo -Handle $Handle
    [AegisSmokeNative]::ShowWindow($Handle, 5) | Out-Null
    [AegisSmokeNative]::SetForegroundWindow($Handle) | Out-Null
    Start-Sleep -Milliseconds 200

    $passwordX = [int]($rect.Left + ($rect.Width * 0.74))
    $passwordY = [int]($rect.Top + ($rect.Height * 0.82))
    Invoke-MouseClick -X $passwordX -Y $passwordY
    Start-Sleep -Milliseconds 120
    [System.Windows.Forms.SendKeys]::SendWait("SmokePassword123{ENTER}")
    Start-Sleep -Milliseconds 600

    $demoCandidateY = if ($rect.Height -lt 760) {
        [int]($rect.Top + ($rect.Height * 0.97))
    } else {
        [int]($rect.Top + ($rect.Height * 0.60))
    }
    Invoke-MouseClick -X ([int]($rect.Left + ($rect.Width * 0.74))) -Y $demoCandidateY
    Start-Sleep -Milliseconds 500
}

Ensure-NativeTypes

if ([string]::IsNullOrWhiteSpace($ExePath)) {
    $ExePath = Resolve-ProjectPath "..\x64\Release\AegisChatBotDesktop.exe"
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Resolve-ProjectPath "..\smoke-artifacts"
}

if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Aegis desktop exe was not found: $ExePath. Run build.ps1 first."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$runStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $OutputDir $runStamp
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$process = $null
$captures = @()
$previousAutoLogin = $env:AEGIS_CHATBOT_SMOKE_AUTO_LOGIN
$previousAutoLoginDelay = $env:AEGIS_CHATBOT_SMOKE_AUTO_LOGIN_DELAY_MS
try {
    $workingDirectory = Split-Path -Parent $ExePath
    if (-not $SkipDashboard) {
        $env:AEGIS_CHATBOT_SMOKE_AUTO_LOGIN = "1"
        $env:AEGIS_CHATBOT_SMOKE_AUTO_LOGIN_DELAY_MS = [string]([Math]::Max(($LoginWaitSeconds * 1000) + 700, 1500))
    }
    $process = Start-Process -FilePath $ExePath -WorkingDirectory $workingDirectory -PassThru
    $handle = Wait-ForMainWindow -ProcessId $process.Id

    Start-Sleep -Seconds $LoginWaitSeconds
    $login = Capture-Window -Handle $handle -Path (Join-Path $runDir "01-login.png")
    Assert-VisibleCapture -Capture $login -MinimumRatio $MinimumNonBlackRatio
    $captures += $login

    if (-not $SkipDashboard) {
        Start-Sleep -Seconds $SetupWaitSeconds
        $setup = Capture-Window -Handle $handle -Path (Join-Path $runDir "02-setup.png")
        Assert-VisibleCapture -Capture $setup -MinimumRatio $MinimumNonBlackRatio
        $captures += $setup

        Start-Sleep -Seconds $DashboardWaitSeconds
        $dashboard = Capture-Window -Handle $handle -Path (Join-Path $runDir "03-dashboard.png")
        Assert-VisibleCapture -Capture $dashboard -MinimumRatio $MinimumNonBlackRatio
        $captures += $dashboard
    }

    $summary = [pscustomobject]@{
        ExePath = $ExePath
        OutputDir = $runDir
        MinimumNonBlackRatio = $MinimumNonBlackRatio
        Captures = $captures | ForEach-Object {
            [pscustomobject]@{
                Path = $_.Path
                Width = $_.Width
                Height = $_.Height
                NonBlackRatio = [Math]::Round([double]$_.Metrics.NonBlackRatio, 4)
                BrightRatio = [Math]::Round([double]$_.Metrics.BrightRatio, 4)
                AccentRatio = [Math]::Round([double]$_.Metrics.AccentRatio, 4)
            }
        }
    }
    $summary | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $runDir "summary.json") -Encoding UTF8
    $summary | ConvertTo-Json -Depth 5
} finally {
    $env:AEGIS_CHATBOT_SMOKE_AUTO_LOGIN = $previousAutoLogin
    $env:AEGIS_CHATBOT_SMOKE_AUTO_LOGIN_DELAY_MS = $previousAutoLoginDelay
    if ($process -ne $null -and -not $process.HasExited) {
        $process.CloseMainWindow() | Out-Null
        Start-Sleep -Milliseconds 600
        if (-not $process.HasExited) {
            $process.Kill()
        }
    }
}
