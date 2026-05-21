param(
  [string]$EvidenceRoot = ".aegis\release-evidence",
  [switch]$SkipSmoke,
  [switch]$IncludeDesktopSmoke,
  [switch]$IncludeVisualStudioPackage,
  [switch]$IncludeReleasePackaging,
  [switch]$AllowDirtyReleaseArtifacts,
  [switch]$Strict,
  [string]$UpdateComponent = "aegis-core"
)

$ErrorActionPreference = "Stop"

$ScriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $ScriptRoot))
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

if ([System.IO.Path]::IsPathRooted($EvidenceRoot)) {
  $EvidenceRootFull = [System.IO.Path]::GetFullPath($EvidenceRoot)
} else {
  $EvidenceRootFull = [System.IO.Path]::GetFullPath((Join-Path $Root $EvidenceRoot))
}

$EvidenceDir = Join-Path $EvidenceRootFull $Timestamp
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$script:Results = @()

function Resolve-WorkspacePath {
  param([Parameter(Mandatory = $true)][string]$Path)

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }

  return [System.IO.Path]::GetFullPath((Join-Path $Root $Path))
}

function Test-UnderRoot {
  param([Parameter(Mandatory = $true)][string]$Path)

  $full = [System.IO.Path]::GetFullPath($Path)
  $rootWithSlash = $Root.TrimEnd("\") + "\"
  return $full.Equals($Root, [System.StringComparison]::OrdinalIgnoreCase) -or
    $full.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-RelativePathFromRoot {
  param([Parameter(Mandatory = $true)][string]$Path)

  $rootUri = New-Object System.Uri (($Root.TrimEnd("\") + "\"))
  $pathUri = New-Object System.Uri ([System.IO.Path]::GetFullPath($Path))
  return ([System.Uri]::UnescapeDataString($rootUri.MakeRelativeUri($pathUri).ToString())).Replace("/", "\")
}

function Format-CommandLine {
  param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [string[]]$Arguments = @()
  )

  $parts = @($Executable) + $Arguments
  $quoted = @()
  foreach ($part in $parts) {
    $text = [string]$part
    if ($text -match '\s') {
      $quoted += '"' + ($text -replace '"', '\"') + '"'
    } else {
      $quoted += $text
    }
  }
  return ($quoted -join " ")
}

function Format-MarkdownCell {
  param([object]$Value)

  if ($null -eq $Value) {
    return ""
  }

  return ([string]$Value).Replace("|", "\|").Replace("`r", " ").Replace("`n", " ")
}

function Add-Result {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Status,
    [object]$ExitCode,
    [double]$DurationSeconds,
    [string]$Reason,
    [string]$Command,
    [string]$WorkingDirectory,
    [string]$LogPath
  )

  $script:Results += [pscustomobject]@{
    id = $Id
    name = $Name
    status = $Status
    exit_code = $ExitCode
    duration_seconds = $DurationSeconds
    reason = $Reason
    command = $Command
    working_directory = $WorkingDirectory
    log = $LogPath
  }
}

function Add-SkippedGate {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Reason,
    [string]$Command = "",
    [string]$WorkingDirectory = $Root
  )

  $logPath = Join-Path $EvidenceDir "$Id.log"
  @(
    "Gate: $Name",
    "Status: skipped",
    "Reason: $Reason",
    "Command: $Command",
    "Working directory: $WorkingDirectory"
  ) | Set-Content -LiteralPath $logPath -Encoding UTF8

  Add-Result -Id $Id -Name $Name -Status "skipped" -ExitCode $null -DurationSeconds 0 -Reason $Reason -Command $Command -WorkingDirectory $WorkingDirectory -LogPath $logPath
  Write-Host "[skipped] $Name - $Reason"
}

function Invoke-Gate {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$Executable,
    [string[]]$Arguments = @(),
    [scriptblock]$FailureClassifier = $null
  )

  $resolvedWorkingDirectory = Resolve-WorkspacePath $WorkingDirectory
  $commandLine = Format-CommandLine -Executable $Executable -Arguments $Arguments
  $logPath = Join-Path $EvidenceDir "$Id.log"

  if (-not (Test-Path -LiteralPath $resolvedWorkingDirectory -PathType Container)) {
    Add-SkippedGate -Id $Id -Name $Name -Reason "Working directory does not exist." -Command $commandLine -WorkingDirectory $resolvedWorkingDirectory
    return
  }

  $started = Get-Date
  $status = "passed"
  $reason = ""
  $exitCode = $null

  @(
    "Gate: $Name",
    "Started: $($started.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))",
    "Command: $commandLine",
    "Working directory: $resolvedWorkingDirectory",
    ""
  ) | Set-Content -LiteralPath $logPath -Encoding UTF8

  Write-Host "[running] $Name"

  try {
    Push-Location $resolvedWorkingDirectory
    $global:LASTEXITCODE = 0
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Executable @Arguments *>> $logPath
    $ErrorActionPreference = $previousErrorActionPreference
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
      $exitCode = 0
    }
    if ($exitCode -ne 0) {
      $status = "failed"
      $reason = "Exited with code $exitCode."
    }
  } catch {
    if ($null -ne (Get-Variable -Name previousErrorActionPreference -Scope Local -ErrorAction SilentlyContinue)) {
      $ErrorActionPreference = $previousErrorActionPreference
    }
    $status = "failed"
    $reason = $_.Exception.Message
    if ($null -eq $exitCode) {
      $exitCode = 1
    }
    "" | Add-Content -LiteralPath $logPath -Encoding UTF8
    "Exception:" | Add-Content -LiteralPath $logPath -Encoding UTF8
    ($_ | Out-String) | Add-Content -LiteralPath $logPath -Encoding UTF8
  } finally {
    Pop-Location
  }

  $ended = Get-Date
  $durationSeconds = [Math]::Round(($ended - $started).TotalSeconds, 2)

  if ($status -eq "failed" -and $null -ne $FailureClassifier) {
    $logText = ""
    if (Test-Path -LiteralPath $logPath) {
      $logText = Get-Content -Raw -LiteralPath $logPath
    }
    $classification = & $FailureClassifier $logText
    if ($null -ne $classification) {
      if ($classification.ContainsKey("status")) {
        $status = [string]$classification["status"]
      }
      if ($classification.ContainsKey("reason")) {
        $reason = [string]$classification["reason"]
      }
    }
  }

  @(
    "",
    "Ended: $($ended.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))",
    "Duration seconds: $durationSeconds",
    "Exit code: $exitCode",
    "Status: $status",
    "Reason: $reason"
  ) | Add-Content -LiteralPath $logPath -Encoding UTF8

  Add-Result -Id $Id -Name $Name -Status $status -ExitCode $exitCode -DurationSeconds $durationSeconds -Reason $reason -Command $commandLine -WorkingDirectory $resolvedWorkingDirectory -LogPath $logPath
  Write-Host "[$status] $Name"
}

function Classify-VsCodeSmokeFailure {
  param([string]$LogText)

  $normalizedLogText = $LogText -replace "`0", ""
  if ($normalizedLogText -match 'vscode-updating|mutex|updat(e|ing)|another instance') {
    return @{
      status = "retryable"
      reason = "VS Code extension-host smoke was blocked by the VS Code update mutex; rerun after the test instance finishes updating."
    }
  }

  return $null
}

function Invoke-VersionCommand {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$Executable,
    [string[]]$Arguments = @()
  )

  $commandLine = Format-CommandLine -Executable $Executable -Arguments $Arguments
  try {
    $global:LASTEXITCODE = 0
    $output = (& $Executable @Arguments 2>&1 | Out-String).Trim()
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
      $exitCode = 0
    }
    return [pscustomobject]@{
      id = $Id
      command = $commandLine
      exit_code = $exitCode
      output = $output
    }
  } catch {
    return [pscustomobject]@{
      id = $Id
      command = $commandLine
      exit_code = 1
      output = $_.Exception.Message
    }
  }
}

function Get-GitStatusForPaths {
  param([string[]]$Paths)

  try {
    $arguments = @("-C", $Root, "status", "--short", "--") + $Paths
    $output = & git @arguments 2>&1
    return @($output)
  } catch {
    return @("git status failed: $($_.Exception.Message)")
  }
}

function Write-EvidenceMetadata {
  $versionCommands = @(
    @{ Id = "powershell"; Executable = "powershell"; Arguments = @("-NoProfile", "-Command", '$PSVersionTable.PSVersion.ToString()') },
    @{ Id = "git"; Executable = "git"; Arguments = @("--version") },
    @{ Id = "python"; Executable = "python"; Arguments = @("--version") },
    @{ Id = "node"; Executable = "node"; Arguments = @("--version") },
    @{ Id = "npm"; Executable = "npm"; Arguments = @("--version") },
    @{ Id = "dotnet"; Executable = "dotnet"; Arguments = @("--version") }
  )

  $versions = @()
  foreach ($command in $versionCommands) {
    $versions += Invoke-VersionCommand -Id $command.Id -Executable $command.Executable -Arguments $command.Arguments
  }

  $versions | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $EvidenceDir "tool-versions.json") -Encoding UTF8
  $versionLines = @()
  foreach ($version in $versions) {
    $versionLines += "$($version.id): $($version.output)"
  }
  $versionLines | Set-Content -LiteralPath (Join-Path $EvidenceDir "tool-versions.txt") -Encoding UTF8

  try {
    & git -C $Root status --short 2>&1 | Set-Content -LiteralPath (Join-Path $EvidenceDir "git-status-short.txt") -Encoding UTF8
  } catch {
    "git status failed: $($_.Exception.Message)" | Set-Content -LiteralPath (Join-Path $EvidenceDir "git-status-short.txt") -Encoding UTF8
  }
}

function Write-MatrixSummary {
  $hardFailures = @($script:Results | Where-Object { $_.status -eq "failed" })
  $retryable = @($script:Results | Where-Object { $_.status -eq "retryable" })
  $skipped = @($script:Results | Where-Object { $_.status -eq "skipped" })

  if ($hardFailures.Count -gt 0) {
    $overall = "failed"
  } elseif ($retryable.Count -gt 0 -or $skipped.Count -gt 0) {
    $overall = "attention"
  } else {
    $overall = "passed"
  }

  $payload = [pscustomobject]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    root = $Root
    evidence_dir = $EvidenceDir
    overall_status = $overall
    strict = [bool]$Strict
    results = $script:Results
  }
  $payload | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $EvidenceDir "validation-matrix.json") -Encoding UTF8

  $summary = @()
  $summary += "# Aegis Ecosystem Validation"
  $summary += ""
  $summary += "Generated: $($payload.generated_at)"
  $summary += ""
  $summary += "Project root: ``$Root``"
  $summary += ""
  $summary += "Overall status: **$overall**"
  $summary += ""
  $summary += "| Gate | Status | Seconds | Reason | Log |"
  $summary += "| --- | --- | ---: | --- | --- |"
  foreach ($result in $script:Results) {
    $logName = ""
    if (-not [string]::IsNullOrWhiteSpace([string]$result.log)) {
      $logName = [System.IO.Path]::GetFileName([string]$result.log)
    }
    $summary += "| $(Format-MarkdownCell $result.name) | $(Format-MarkdownCell $result.status) | $($result.duration_seconds) | $(Format-MarkdownCell $result.reason) | $(Format-MarkdownCell $logName) |"
  }
  $summary += ""
  $summary += "Hard failures: $($hardFailures.Count)"
  $summary += "Retryable gates: $($retryable.Count)"
  $summary += "Skipped gates: $($skipped.Count)"
  $summary += ""
  $summary += "Run with ``-Strict`` if skipped or retryable gates should cause a non-zero exit."

  $summary | Set-Content -LiteralPath (Join-Path $EvidenceDir "validation-summary.md") -Encoding UTF8

  Write-Host ""
  Write-Host "Validation evidence: $EvidenceDir"
  Write-Host "Overall status: $overall"
  Write-Host "Hard failures: $($hardFailures.Count); retryable: $($retryable.Count); skipped: $($skipped.Count)"

  if ($hardFailures.Count -gt 0) {
    exit 1
  }

  if ($Strict -and ($retryable.Count -gt 0 -or $skipped.Count -gt 0)) {
    exit 1
  }

  exit 0
}

Write-EvidenceMetadata

$releaseTrackedPaths = @(
  "release",
  "vscode-plugins/aegis-local-autopilot/release",
  "visual-studio-extensions/aegis-local-agent-vs/release",
  "VERSION.json",
  "scripts/build-release.ps1",
  "scripts/aegis-update.ps1"
)
$releaseStatus = @(Get-GitStatusForPaths -Paths $releaseTrackedPaths)
$releaseStatus | Set-Content -LiteralPath (Join-Path $EvidenceDir "release-artifact-status.txt") -Encoding UTF8
$releaseArtifactsDirty = $releaseStatus.Count -gt 0

Invoke-Gate -Id "core-tests" -Name "Aegis Core tests" -WorkingDirectory "aegis-core" -Executable "python" -Arguments @("-m", "pytest", "tests", "-q")
Invoke-Gate -Id "website-backend-tests" -Name "Website backend tests" -WorkingDirectory "website\backend" -Executable "python" -Arguments @("-m", "pytest", "tests", "-q")
Invoke-Gate -Id "website-frontend-tests" -Name "Website frontend tests" -WorkingDirectory "website\frontend" -Executable "npm" -Arguments @("test")
Invoke-Gate -Id "website-frontend-build" -Name "Website frontend production build" -WorkingDirectory "website\frontend" -Executable "npm" -Arguments @("run", "build")
Invoke-Gate -Id "desktop-contract" -Name "Native desktop source contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-desktop-contract.ps1"), "-Root", $Root)
Invoke-Gate -Id "release-contract" -Name "Release/update contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-release-contract.ps1"), "-Root", $Root)
Invoke-Gate -Id "extension-package-candidates" -Name "Extension package candidates" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-extension-package-candidates.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "extension-package-candidates"))
Invoke-Gate -Id "release-package-dry-run-contract" -Name "Release package dry-run contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-release-package-dry-run.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "release-package-dry-run-contract"))
if ($IncludeReleasePackaging) {
  Invoke-Gate -Id "final-release-manifest-contract" -Name "Final release manifest contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-final-release-manifest.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "final-release-manifest-contract"))
} else {
  Add-SkippedGate -Id "final-release-manifest-contract" -Name "Final release manifest contract" -Reason "Mutates the root release folder. Re-run with -IncludeReleasePackaging after the release artifact decision is intentional." -Command "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-final-release-manifest.ps1"
}
Invoke-Gate -Id "release-artifact-preflight" -Name "Release artifact preflight" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-release-artifact-preflight.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "release-artifact-preflight"))
Invoke-Gate -Id "release-apply-rollback-contract" -Name "Release apply rollback contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-release-apply-rollback.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "release-apply-rollback-contract"))
Invoke-Gate -Id "quality-contract" -Name "Quality/eval evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-quality-contract.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "quality-contract"))
Invoke-Gate -Id "plugin-contract" -Name "Plugin/productization contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-plugin-contract.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "plugin-contract"))
Invoke-Gate -Id "alpha-contract" -Name "Alpha readiness and dogfooding contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-alpha-contract.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "alpha-contract"))
Invoke-Gate -Id "packaged-alpha-scenarios-contract" -Name "Packaged alpha scenario evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-packaged-alpha-scenarios.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "packaged-alpha-scenarios-contract"))
Invoke-Gate -Id "cross-client-parity-contract" -Name "Cross-client parity evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-cross-client-parity.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "cross-client-parity-contract"))
Invoke-Gate -Id "release-notes-limitations-contract" -Name "Release notes limitations evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-release-notes-limitations.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "release-notes-limitations-contract"))
Invoke-Gate -Id "core-website-ownership-contract" -Name "Core Website ownership evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-core-website-ownership.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "core-website-ownership-contract"))
Invoke-Gate -Id "backend-modularization-contract" -Name "Backend modularization evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-backend-modularization.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "backend-modularization-contract"))
Invoke-Gate -Id "frontend-extraction-contract" -Name "Frontend extraction evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-frontend-extraction.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "frontend-extraction-contract"))
Invoke-Gate -Id "desktop-shell-hardening-contract" -Name "Native desktop shell hardening evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-native-desktop-shell.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "desktop-shell-hardening-contract"))
Invoke-Gate -Id "editor-extension-modularization-contract" -Name "Editor extension modularization evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-editor-extension-modularization.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "editor-extension-modularization-contract"))
Invoke-Gate -Id "provider-secret-safety-contract" -Name "Provider secret safety evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-provider-secret-safety.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "provider-secret-safety-contract"))
Invoke-Gate -Id "memory-governance-contract" -Name "Memory governance evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-memory-governance.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "memory-governance-contract"))
Invoke-Gate -Id "plugin-lifecycle-contract" -Name "Plugin lifecycle productization evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-plugin-lifecycle.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "plugin-lifecycle-contract"))
Invoke-Gate -Id "observability-ci-contract" -Name "Observability evals and CI evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-observability-ci.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "observability-ci-contract"))
Invoke-Gate -Id "distribution-update-contract" -Name "Distribution installer signing and update evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-distribution-update.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "distribution-update-contract"))
Invoke-Gate -Id "alpha-readiness-polish-contract" -Name "Alpha readiness polish evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-alpha-readiness-polish.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "alpha-readiness-polish-contract"))
Invoke-Gate -Id "live-smoke-rc-contract" -Name "Live smoke and release candidate scoping evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-live-smoke-rc.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "live-smoke-rc-contract"))
Invoke-Gate -Id "commit-scoping-github-handoff-contract" -Name "Commit scoping and GitHub handoff evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-commit-scoping-github-handoff.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "commit-scoping-github-handoff-contract"))
Invoke-Gate -Id "desktop-smoke-package-gates-contract" -Name "Desktop smoke and package gate execution evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-desktop-smoke-package-gates.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "desktop-smoke-package-gates-contract"))
Invoke-Gate -Id "editor-smoke-release-package-decision-contract" -Name "Editor smoke and release package decision evidence contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-editor-smoke-release-package-decision.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "editor-smoke-release-package-decision-contract"))
Invoke-Gate -Id "external-alpha-contract" -Name "External alpha release report contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-external-alpha-contract.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "external-alpha-contract"))
Invoke-Gate -Id "evidence-ledger-contract" -Name "Evidence ledger contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-evidence-ledger-contract.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "evidence-ledger-contract"))
Invoke-Gate -Id "desktop-release-build" -Name "Native desktop Release x64 build" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "build.ps1"))

if ($IncludeDesktopSmoke) {
  Invoke-Gate -Id "desktop-smoke" -Name "Native desktop smoke" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\smoke-desktop.ps1"))
} else {
  Add-SkippedGate -Id "desktop-smoke" -Name "Native desktop smoke" -Reason "Optional slow/runtime gate. Re-run with -IncludeDesktopSmoke to execute it." -Command "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\smoke-desktop.ps1"
}

Invoke-Gate -Id "vscode-unit" -Name "VS Code extension helper tests" -WorkingDirectory "vscode-plugins\aegis-local-autopilot" -Executable "npm" -Arguments @("run", "test:unit")
Invoke-Gate -Id "vscode-lint" -Name "VS Code extension lint/package guards" -WorkingDirectory "vscode-plugins\aegis-local-autopilot" -Executable "npm" -Arguments @("run", "lint")
Invoke-Gate -Id "editor-parity" -Name "Editor client parity contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-editor-parity.ps1"), "-Root", $Root)

if ($SkipSmoke) {
  Add-SkippedGate -Id "vscode-smoke" -Name "VS Code extension-host smoke" -Reason "Skipped by -SkipSmoke." -Command "npm run test:smoke" -WorkingDirectory (Resolve-WorkspacePath "vscode-plugins\aegis-local-autopilot")
} else {
  Invoke-Gate -Id "vscode-smoke" -Name "VS Code extension-host smoke" -WorkingDirectory "vscode-plugins\aegis-local-autopilot" -Executable "npm" -Arguments @("run", "test:smoke") -FailureClassifier ${function:Classify-VsCodeSmokeFailure}
}

Invoke-Gate -Id "visual-studio-validate" -Name "Visual Studio extension validation guards" -WorkingDirectory "visual-studio-extensions\aegis-local-agent-vs" -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "visual-studio-extensions\aegis-local-agent-vs\build.ps1"), "-ValidateOnly")

if ($IncludeVisualStudioPackage) {
  if ($releaseArtifactsDirty -and -not $AllowDirtyReleaseArtifacts) {
    Add-SkippedGate -Id "visual-studio-package" -Name "Visual Studio extension package" -Reason "Release artifacts are dirty. Re-run with -AllowDirtyReleaseArtifacts only after the release-folder decision is intentional." -Command "powershell -NoProfile -ExecutionPolicy Bypass -File visual-studio-extensions\aegis-local-agent-vs\build.ps1"
  } else {
    Invoke-Gate -Id "visual-studio-package" -Name "Visual Studio extension package" -WorkingDirectory "visual-studio-extensions\aegis-local-agent-vs" -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "visual-studio-extensions\aegis-local-agent-vs\build.ps1"))
  }
} else {
  Add-SkippedGate -Id "visual-studio-package" -Name "Visual Studio extension package" -Reason "Mutates the extension release folder. Re-run with -IncludeVisualStudioPackage after Phase 0 release decisions are settled." -Command "powershell -NoProfile -ExecutionPolicy Bypass -File visual-studio-extensions\aegis-local-agent-vs\build.ps1"
}

$releaseDryRunOutput = Join-Path $EvidenceDir "release-dry-run"
$releaseManifestFromDryRun = Join-Path $releaseDryRunOutput "version-manifest.json"

if ($IncludeReleasePackaging) {
  if (-not (Test-UnderRoot $releaseDryRunOutput)) {
    Add-SkippedGate -Id "release-package-dry-run" -Name "Release packaging dry run" -Reason "Release dry-run output must live under the workspace root." -Command "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build-release.ps1 -SkipBuild"
  } elseif ($releaseArtifactsDirty -and -not $AllowDirtyReleaseArtifacts) {
    Add-SkippedGate -Id "release-package-dry-run" -Name "Release packaging dry run" -Reason "Release artifacts are dirty. Re-run with -AllowDirtyReleaseArtifacts only after the release-folder decision is intentional." -Command "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build-release.ps1 -SkipBuild"
  } else {
    $releaseOutputRelative = Get-RelativePathFromRoot $releaseDryRunOutput
    Invoke-Gate -Id "release-package-dry-run" -Name "Release packaging dry run" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\build-release.ps1"), "-SkipBuild", "-OutputDir", $releaseOutputRelative)
  }
} else {
  Add-SkippedGate -Id "release-package-dry-run" -Name "Release packaging dry run" -Reason "Skipped by default while extension release artifacts are dirty. Re-run with -IncludeReleasePackaging after release decisions are settled." -Command "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build-release.ps1 -SkipBuild"
}

$updateManifest = $null
if (Test-Path -LiteralPath $releaseManifestFromDryRun -PathType Leaf) {
  $updateManifest = $releaseManifestFromDryRun
} elseif (Test-Path -LiteralPath (Join-Path $Root "release\version-manifest.json") -PathType Leaf) {
  $updateManifest = Join-Path $Root "release\version-manifest.json"
}

if ($null -eq $updateManifest) {
  Add-SkippedGate -Id "update-plan-dry-run" -Name "Update planner dry run" -Reason "No release manifest is available. Generate one with -IncludeReleasePackaging after release decisions are settled." -Command "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aegis-update.ps1 -Component $UpdateComponent"
} else {
  Invoke-Gate -Id "update-plan-dry-run" -Name "Update planner dry run" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\aegis-update.ps1"), "-Manifest", $updateManifest, "-Component", $UpdateComponent, "-InstallRoot", $Root)
}

Write-MatrixSummary
