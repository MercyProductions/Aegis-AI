param(
    [string]$Root = "",
    [string]$EvidenceDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = Split-Path -Parent $PSScriptRoot
}

$Root = (Resolve-Path -LiteralPath $Root).Path

function Join-ProjectPath {
    param([string]$Path)
    return Join-Path $Root $Path
}

function ConvertTo-ProjectRelativePath {
    param([string]$Path)

    $resolved = if (Test-Path -LiteralPath $Path) {
        (Resolve-Path -LiteralPath $Path).Path
    } else {
        $full = [System.IO.Path]::GetFullPath($Path)
        $full
    }

    $rootWithSlash = $Root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    if ($resolved.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $resolved.Substring($rootWithSlash.Length)
    }

    throw "Path is outside project root: $resolved"
}

function Test-UnderRoot {
    param([string]$Path)

    $full = [System.IO.Path]::GetFullPath($Path)
    $rootWithSlash = $Root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    if (-not ($full.Equals($Root, [System.StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase))) {
        throw "Refusing to write outside project root: $full"
    }

    return $full
}

function Read-JsonFile {
    param([string]$Path)
    return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
}

function Add-Check {
    param(
        [System.Collections.Generic.List[object]]$Checks,
        [string]$Id,
        [bool]$Passed,
        [string]$Message,
        [object]$Details = $null
    )

    $Checks.Add([pscustomobject]@{
        id = $Id
        passed = $Passed
        message = $Message
        details = $Details
    }) | Out-Null
}

function Invoke-CapturedCommand {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$WorkingDirectory,
        [string]$LogPath
    )

    $output = & $Executable @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    Set-Content -LiteralPath $LogPath -Value $text -Encoding UTF8

    return [pscustomobject]@{
        exit_code = $exitCode
        output = $text
    }
}

function Get-ManifestComponent {
    param(
        [object]$Manifest,
        [string]$Id
    )

    if ($null -eq $Manifest -or $null -eq $Manifest.components) {
        return $null
    }

    $property = $Manifest.components.PSObject.Properties[$Id]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $EvidenceDir = Join-Path $Root ".aegis\release-package-dry-run\$stamp"
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
    $EvidenceDir = Join-Path $Root $EvidenceDir
}

$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$contractPath = Join-ProjectPath "evals\phase19-release-package-dry-run-contract.json"
$contract = Read-JsonFile $contractPath
$checks = [System.Collections.Generic.List[object]]::new()
$failures = [System.Collections.Generic.List[string]]::new()

$requiredFiles = @($contract.required_contract_files)
foreach ($file in $requiredFiles) {
    $path = Join-ProjectPath ($file -replace '/', '\')
    $exists = Test-Path -LiteralPath $path
    Add-Check $checks "contract_file:$file" $exists "Required contract file is present: $file"
    if (-not $exists) {
        $failures.Add("Missing required contract file: $file") | Out-Null
    }
}

$validationScript = Get-Content -LiteralPath (Join-ProjectPath "scripts\validate-ecosystem.ps1") -Raw
$validationWired = $validationScript -match "test-release-package-dry-run\.ps1" -and $validationScript -match "release-package-dry-run-contract"
Add-Check $checks "validate_ecosystem_wiring" $validationWired "validate-ecosystem.ps1 includes the release package dry-run gate."
if (-not $validationWired) {
    $failures.Add("validate-ecosystem.ps1 is missing release-package-dry-run-contract wiring.") | Out-Null
}

$docsToCheck = @{
    "docs\RELEASE_PACKAGE_DRY_RUN.md" = @("test-release-package-dry-run.ps1", ".aegis/release-package-dry-run", "version-manifest.json")
    "docs\RELEASE_PACKAGING_AND_UPDATES.md" = @("test-release-package-dry-run.ps1", "release-package-dry-run")
    "docs\RELEASE_ARTIFACT_PREFLIGHT.md" = @("release-package-dry-run")
    "docs\EVIDENCE_LEDGER.md" = @("release-package-dry-run")
    "docs\EXTERNAL_ALPHA_RELEASE_REPORT.md" = @("release-package-dry-run-contract")
    "docs\VALIDATION_MATRIX.md" = @("release-package-dry-run-contract")
}

foreach ($docEntry in $docsToCheck.GetEnumerator()) {
    $docPath = Join-ProjectPath $docEntry.Key
    $content = if (Test-Path -LiteralPath $docPath) { Get-Content -LiteralPath $docPath -Raw } else { "" }
    foreach ($needle in $docEntry.Value) {
        $found = $content -like "*$needle*"
        Add-Check $checks "doc:$($docEntry.Key):$needle" $found "Documentation contains '$needle' in $($docEntry.Key)."
        if (-not $found) {
            $failures.Add("Documentation drift: $($docEntry.Key) does not mention $needle.") | Out-Null
        }
    }
}

$releaseOutputDir = Join-Path $EvidenceDir "release"
$releaseOutputRelative = ConvertTo-ProjectRelativePath $releaseOutputDir
$buildLogPath = Join-Path $EvidenceDir "build-release.log"
$buildArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    (Join-ProjectPath "scripts\build-release.ps1"),
    "-SkipBuild",
    "-OutputDir",
    $releaseOutputRelative
)

$buildResult = Invoke-CapturedCommand -Executable "powershell" -Arguments $buildArgs -WorkingDirectory $Root -LogPath $buildLogPath
$buildPassed = $buildResult.exit_code -eq 0
Add-Check $checks "build_release_skip_build" $buildPassed "build-release.ps1 -SkipBuild completed successfully." @{
    exit_code = $buildResult.exit_code
    log = ConvertTo-ProjectRelativePath $buildLogPath
}
if (-not $buildPassed) {
    $failures.Add("build-release.ps1 -SkipBuild failed. See $buildLogPath") | Out-Null
}

$manifestPath = Join-Path $releaseOutputDir "version-manifest.json"
$manifestExists = Test-Path -LiteralPath $manifestPath
Add-Check $checks "version_manifest_generated" $manifestExists "Dry-run version manifest was generated." @{
    path = if ($manifestExists) { ConvertTo-ProjectRelativePath $manifestPath } else { ConvertTo-ProjectRelativePath $releaseOutputDir }
}
if (-not $manifestExists) {
    $failures.Add("Dry-run version manifest was not generated.") | Out-Null
}

$manifest = $null
if ($manifestExists) {
    $manifest = Read-JsonFile $manifestPath
}

$artifactResults = [System.Collections.Generic.List[object]]::new()
if ($manifest -ne $null) {
    foreach ($componentId in @($contract.components)) {
        $component = Get-ManifestComponent -Manifest $manifest -Id $componentId
        $componentExists = $null -ne $component
        Add-Check $checks "manifest_component:$componentId" $componentExists "Manifest includes component $componentId."
        if (-not $componentExists) {
            $failures.Add("Manifest is missing component: $componentId") | Out-Null
            continue
        }

        $package = $component.package
        $packageHasFields = $null -ne $package -and
            -not [string]::IsNullOrWhiteSpace([string]$package.artifact) -and
            -not [string]::IsNullOrWhiteSpace([string]$package.path) -and
            [string]$package.sha256 -match '^[a-fA-F0-9]{64}$' -and
            [int64]$package.size_bytes -gt 0

        Add-Check $checks "manifest_package_fields:$componentId" $packageHasFields "Manifest package metadata is complete for $componentId."
        if (-not $packageHasFields) {
            $failures.Add("Manifest package metadata is incomplete for component: $componentId") | Out-Null
            continue
        }

        $packagePath = Join-ProjectPath (([string]$package.path) -replace '/', '\')
        $fileExists = Test-Path -LiteralPath $packagePath
        Add-Check $checks "artifact_file_present:$componentId" $fileExists "Package file exists for $componentId."
        if (-not $fileExists) {
            $failures.Add("Package file is missing for component $componentId at $($package.path)") | Out-Null
            continue
        }

        $file = Get-Item -LiteralPath $packagePath
        $hash = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $expectedHash = ([string]$package.sha256).ToLowerInvariant()
        $sizeMatches = [int64]$package.size_bytes -eq [int64]$file.Length
        $hashMatches = $hash -eq $expectedHash

        Add-Check $checks "artifact_size_stamped:$componentId" $sizeMatches "Manifest size matches package file for $componentId." @{
            expected = [int64]$package.size_bytes
            actual = [int64]$file.Length
        }
        Add-Check $checks "artifact_hash_stamped:$componentId" $hashMatches "Manifest SHA-256 matches package file for $componentId." @{
            expected = $expectedHash
            actual = $hash
        }

        if (-not $sizeMatches) {
            $failures.Add("Package size mismatch for component: $componentId") | Out-Null
        }
        if (-not $hashMatches) {
            $failures.Add("Package hash mismatch for component: $componentId") | Out-Null
        }

        $artifactResults.Add([pscustomobject]@{
            component = $componentId
            artifact = [string]$package.artifact
            path = ConvertTo-ProjectRelativePath $packagePath
            size_bytes = [int64]$file.Length
            sha256 = $hash
        }) | Out-Null
    }
}

foreach ($artifact in @($contract.required_artifacts)) {
    $artifactPath = Join-Path $releaseOutputDir $artifact
    $artifactExists = Test-Path -LiteralPath $artifactPath
    Add-Check $checks "required_artifact:$artifact" $artifactExists "Required dry-run artifact exists: $artifact"
    if (-not $artifactExists) {
        $failures.Add("Missing required dry-run artifact: $artifact") | Out-Null
    }
}

$copiedTools = @("aegis-update.ps1", "build-release.ps1")
foreach ($tool in $copiedTools) {
    $toolPath = Join-Path $releaseOutputDir $tool
    $toolExists = Test-Path -LiteralPath $toolPath
    Add-Check $checks "release_tool_copied:$tool" $toolExists "Release helper copied into dry-run output: $tool"
    if (-not $toolExists) {
        $failures.Add("Release helper was not copied into dry-run output: $tool") | Out-Null
    }
}

$updatePlans = [System.Collections.Generic.List[object]]::new()
if ($manifestExists) {
    foreach ($componentId in @($contract.components)) {
        $planPath = Join-Path $EvidenceDir "update-plan-$componentId.json"
        $planLogPath = Join-Path $EvidenceDir "update-plan-$componentId.log"
        $updateArgs = @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            (Join-ProjectPath "scripts\aegis-update.ps1"),
            "-Manifest",
            $manifestPath,
            "-Component",
            $componentId,
            "-InstallRoot",
            $Root
        )

        $planResult = Invoke-CapturedCommand -Executable "powershell" -Arguments $updateArgs -WorkingDirectory $Root -LogPath $planLogPath
        $planJson = $null
        $planParseFailed = $false
        if ($planResult.exit_code -eq 0 -and -not [string]::IsNullOrWhiteSpace($planResult.output)) {
            try {
                $planJson = $planResult.output | ConvertFrom-Json
                $planResult.output | Set-Content -LiteralPath $planPath -Encoding UTF8
            } catch {
                $planParseFailed = $true
            }
        }

        $planned = $planResult.exit_code -eq 0 -and
            -not $planParseFailed -and
            $null -ne $planJson -and
            [string]$planJson.state -eq "planned" -and
            [bool]$planJson.checksum_required -eq $true -and
            -not [string]::IsNullOrWhiteSpace([string]$planJson.target_version)

        Add-Check $checks "update_plan_dry_run:$componentId" $planned "Updater dry-run produced a planned state for $componentId." @{
            exit_code = $planResult.exit_code
            plan = if (Test-Path -LiteralPath $planPath) { ConvertTo-ProjectRelativePath $planPath } else { $null }
            log = ConvertTo-ProjectRelativePath $planLogPath
        }

        if (-not $planned) {
            $failures.Add("Updater dry-run did not produce planned state for component: $componentId") | Out-Null
        } else {
            $updatePlans.Add([pscustomobject]@{
                component = $componentId
                state = [string]$planJson.state
                target_version = [string]$planJson.target_version
                package_path = [string]$planJson.package
                checksum_required = [bool]$planJson.checksum_required
                plan_file = ConvertTo-ProjectRelativePath $planPath
            }) | Out-Null
        }
    }
}

$requiredCheckIds = @($contract.required_checks)
$requiredCheckPrefixes = @{
    artifact_files_present = "artifact_file_present"
    artifact_hashes_stamped = "artifact_hash_stamped"
    artifact_sizes_stamped = "artifact_size_stamped"
    release_tools_copied = "release_tool_copied"
    update_plan_dry_runs = "update_plan_dry_run"
}
foreach ($requiredCheck in $requiredCheckIds) {
    $checkPrefix = if ($requiredCheckPrefixes.ContainsKey($requiredCheck)) { [string]$requiredCheckPrefixes[$requiredCheck] } else { [string]$requiredCheck }
    $matchingChecks = @($checks | Where-Object {
        $_.id -eq $requiredCheck -or $_.id -eq $checkPrefix -or $_.id -like "$checkPrefix`:*" -or $_.id -like "$checkPrefix*"
    })
    $passed = $matchingChecks.Count -gt 0 -and -not (@($matchingChecks | Where-Object { -not $_.passed }).Count -gt 0)
    Add-Check $checks "required_check:$requiredCheck" $passed "Required check group passed: $requiredCheck"
    if (-not $passed) {
        $failures.Add("Required check group failed: $requiredCheck") | Out-Null
    }
}

$status = if ($failures.Count -eq 0) { "ready" } else { "blocked" }
$payload = [pscustomobject]@{
    schema_version = "2026.05.21"
    generated_at = (Get-Date).ToString("o")
    phase = 19
    status = $status
    evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
    release_dir = ConvertTo-ProjectRelativePath $releaseOutputDir
    contract = "evals/phase19-release-package-dry-run-contract.json"
    manifest = if ($manifestExists) { ConvertTo-ProjectRelativePath $manifestPath } else { $null }
    build_log = ConvertTo-ProjectRelativePath $buildLogPath
    artifacts = @($artifactResults)
    update_plans = @($updatePlans)
    failures = @($failures)
    checks = @($checks)
}

$jsonPath = Join-Path $EvidenceDir "release-package-dry-run.json"
$summaryPath = Join-Path $EvidenceDir "release-package-dry-run-summary.md"
$payload | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$summary = [System.Collections.Generic.List[string]]::new()
$summary.Add("# Release Package Dry-Run Evidence") | Out-Null
$summary.Add("") | Out-Null
$summary.Add("- Status: $status") | Out-Null
$summary.Add("- Generated: $($payload.generated_at)") | Out-Null
$summary.Add("- Evidence: $($payload.evidence_dir)") | Out-Null
$summary.Add("- Manifest: $($payload.manifest)") | Out-Null
$summary.Add("- Build log: $($payload.build_log)") | Out-Null
$summary.Add("") | Out-Null
$summary.Add("## Artifacts") | Out-Null
foreach ($artifact in @($artifactResults)) {
    $summary.Add("- $($artifact.component): $($artifact.artifact) ($($artifact.size_bytes) bytes)") | Out-Null
}
$summary.Add("") | Out-Null
$summary.Add("## Update Plans") | Out-Null
foreach ($plan in @($updatePlans)) {
    $summary.Add("- $($plan.component): $($plan.state) -> $($plan.target_version)") | Out-Null
}
if ($failures.Count -gt 0) {
    $summary.Add("") | Out-Null
    $summary.Add("## Failures") | Out-Null
    foreach ($failure in $failures) {
        $summary.Add("- $failure") | Out-Null
    }
}
Set-Content -LiteralPath $summaryPath -Value $summary -Encoding UTF8

$payload | ConvertTo-Json -Depth 10

if ($status -ne "ready") {
    exit 1
}
