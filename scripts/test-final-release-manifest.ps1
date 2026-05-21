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
        [System.IO.Path]::GetFullPath($Path)
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
    $EvidenceDir = Join-Path $Root ".aegis\final-release-manifest\$stamp"
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
    $EvidenceDir = Join-Path $Root $EvidenceDir
}

$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$contractPath = Join-ProjectPath "evals\phase20-final-release-manifest-contract.json"
$contract = Read-JsonFile $contractPath
$checks = [System.Collections.Generic.List[object]]::new()
$failures = [System.Collections.Generic.List[string]]::new()

foreach ($file in @($contract.required_contract_files)) {
    $path = Join-ProjectPath (([string]$file) -replace '/', '\')
    $exists = Test-Path -LiteralPath $path -PathType Leaf
    Add-Check $checks "contract_file:$file" $exists "Required contract file is present: $file"
    if (-not $exists) {
        $failures.Add("Missing required contract file: $file") | Out-Null
    }
}

$decisionPath = Join-ProjectPath "docs\RELEASE_ARTIFACT_DECISION.md"
$decisionText = if (Test-Path -LiteralPath $decisionPath) { Get-Content -LiteralPath $decisionPath -Raw } else { "" }
$decisionRecorded = $decisionText -match "Phase 20" -and
    $decisionText -match "accepted as release inputs" -and
    $decisionText -match "generated release output" -and
    $decisionText -match "unsigned"
Add-Check $checks "artifact_decision_recorded" $decisionRecorded "Release artifact decision is recorded for Phase 20."
if (-not $decisionRecorded) {
    $failures.Add("Release artifact decision doc is incomplete.") | Out-Null
}

$unsignedDisclosure = $decisionText -match "unsigned local build"
Add-Check $checks "unsigned_build_disclosure" $unsignedDisclosure "Unsigned local build disclosure is present."
if (-not $unsignedDisclosure) {
    $failures.Add("Unsigned local build disclosure is missing.") | Out-Null
}

$validator = Get-Content -LiteralPath (Join-ProjectPath "scripts\validate-ecosystem.ps1") -Raw
$validationWired = $validator -match "test-final-release-manifest\.ps1" -and $validator -match "final-release-manifest-contract"
Add-Check $checks "validate_ecosystem_wiring" $validationWired "validate-ecosystem.ps1 includes the final release manifest gate."
if (-not $validationWired) {
    $failures.Add("validate-ecosystem.ps1 is missing final-release-manifest-contract wiring.") | Out-Null
}

$buildLogPath = Join-Path $EvidenceDir "build-release-root.log"
$buildArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    (Join-ProjectPath "scripts\build-release.ps1"),
    "-SkipBuild",
    "-OutputDir",
    "release"
)

$buildResult = Invoke-CapturedCommand -Executable "powershell" -Arguments $buildArgs -LogPath $buildLogPath
$buildPassed = $buildResult.exit_code -eq 0
Add-Check $checks "build_release_root_skip_build" $buildPassed "build-release.ps1 generated root release packages." @{
    exit_code = $buildResult.exit_code
    log = ConvertTo-ProjectRelativePath $buildLogPath
}
if (-not $buildPassed) {
    $failures.Add("build-release.ps1 failed while generating root release packages.") | Out-Null
}

$manifestPath = Join-ProjectPath "release\version-manifest.json"
$manifestExists = Test-Path -LiteralPath $manifestPath -PathType Leaf
Add-Check $checks "root_manifest_generated" $manifestExists "Root release/version-manifest.json exists."
if (-not $manifestExists) {
    $failures.Add("Root release/version-manifest.json is missing.") | Out-Null
}

$manifest = if ($manifestExists) { Read-JsonFile $manifestPath } else { $null }
$artifactResults = [System.Collections.Generic.List[object]]::new()

if ($null -ne $manifest) {
    foreach ($componentId in @($contract.components)) {
        $component = Get-ManifestComponent -Manifest $manifest -Id ([string]$componentId)
        $componentExists = $null -ne $component
        Add-Check $checks "manifest_component:$componentId" $componentExists "Root manifest includes component $componentId."
        if (-not $componentExists) {
            $failures.Add("Root manifest is missing component: $componentId") | Out-Null
            continue
        }

        $package = $component.package
        $packageHasFields = $null -ne $package -and
            -not [string]::IsNullOrWhiteSpace([string]$package.artifact) -and
            -not [string]::IsNullOrWhiteSpace([string]$package.path) -and
            [string]$package.sha256 -match '^[a-fA-F0-9]{64}$' -and
            [int64]$package.size_bytes -gt 0
        Add-Check $checks "manifest_package_fields:$componentId" $packageHasFields "Root manifest package metadata is complete for $componentId."
        if (-not $packageHasFields) {
            $failures.Add("Root manifest package metadata is incomplete for $componentId.") | Out-Null
            continue
        }

        $releaseRelative = ([string]$package.path) -replace '\\', '/'
        $pathIsReleaseRelative = $releaseRelative -like "release/*"
        Add-Check $checks "root_manifest_path_release_relative:$componentId" $pathIsReleaseRelative "Package path is release-relative for $componentId." @{
            path = [string]$package.path
        }
        if (-not $pathIsReleaseRelative) {
            $failures.Add("Package path is not release-relative for $componentId`: $($package.path)") | Out-Null
        }

        $packagePath = Join-ProjectPath (([string]$package.path) -replace '/', '\')
        $fileExists = Test-Path -LiteralPath $packagePath -PathType Leaf
        Add-Check $checks "root_artifact_present:$componentId" $fileExists "Root package file exists for $componentId."
        if (-not $fileExists) {
            $failures.Add("Root package file is missing for $componentId at $($package.path)") | Out-Null
            continue
        }

        $file = Get-Item -LiteralPath $packagePath
        $hash = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $expectedHash = ([string]$package.sha256).ToLowerInvariant()
        $sizeMatches = [int64]$package.size_bytes -eq [int64]$file.Length
        $hashMatches = $hash -eq $expectedHash

        Add-Check $checks "root_artifact_size_stamped:$componentId" $sizeMatches "Root manifest size matches package file for $componentId." @{
            expected = [int64]$package.size_bytes
            actual = [int64]$file.Length
        }
        Add-Check $checks "root_artifact_hash_stamped:$componentId" $hashMatches "Root manifest SHA-256 matches package file for $componentId." @{
            expected = $expectedHash
            actual = $hash
        }

        if (-not $sizeMatches) {
            $failures.Add("Root package size mismatch for $componentId.") | Out-Null
        }
        if (-not $hashMatches) {
            $failures.Add("Root package hash mismatch for $componentId.") | Out-Null
        }

        $artifactResults.Add([pscustomobject]@{
            component = [string]$componentId
            artifact = [string]$package.artifact
            path = ConvertTo-ProjectRelativePath $packagePath
            size_bytes = [int64]$file.Length
            sha256 = $hash
        }) | Out-Null
    }
}

foreach ($artifact in @($contract.required_artifacts)) {
    $artifactPath = Join-ProjectPath ("release\" + [string]$artifact)
    $exists = Test-Path -LiteralPath $artifactPath -PathType Leaf
    Add-Check $checks "required_artifact:$artifact" $exists "Required root release artifact exists: $artifact"
    if (-not $exists) {
        $failures.Add("Missing required root release artifact: $artifact") | Out-Null
    }
}

foreach ($tool in @("aegis-update.ps1", "build-release.ps1")) {
    $toolPath = Join-ProjectPath ("release\" + $tool)
    $exists = Test-Path -LiteralPath $toolPath -PathType Leaf
    Add-Check $checks "release_tool_copied:$tool" $exists "Release helper copied into root release output: $tool"
    if (-not $exists) {
        $failures.Add("Release helper was not copied into root release output: $tool") | Out-Null
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
            [string]$componentId,
            "-InstallRoot",
            $Root
        )

        $planResult = Invoke-CapturedCommand -Executable "powershell" -Arguments $updateArgs -LogPath $planLogPath
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
        Add-Check $checks "update_plan_dry_run:$componentId" $planned "Updater dry-run produced a planned state for $componentId against the root manifest." @{
            exit_code = $planResult.exit_code
            plan = if (Test-Path -LiteralPath $planPath) { ConvertTo-ProjectRelativePath $planPath } else { $null }
            log = ConvertTo-ProjectRelativePath $planLogPath
        }

        if (-not $planned) {
            $failures.Add("Updater dry-run did not produce planned state for root manifest component: $componentId") | Out-Null
        } else {
            $updatePlans.Add([pscustomobject]@{
                component = [string]$componentId
                state = [string]$planJson.state
                target_version = [string]$planJson.target_version
                package_path = [string]$planJson.package
                checksum_required = [bool]$planJson.checksum_required
                plan_file = ConvertTo-ProjectRelativePath $planPath
            }) | Out-Null
        }
    }
}

$requiredCheckPrefixes = @{
    root_artifacts_present = "root_artifact_present"
    root_artifact_hashes_stamped = "root_artifact_hash_stamped"
    root_artifact_sizes_stamped = "root_artifact_size_stamped"
    root_manifest_paths_are_release_relative = "root_manifest_path_release_relative"
    release_tools_copied = "release_tool_copied"
    update_plan_dry_runs = "update_plan_dry_run"
}
foreach ($requiredCheck in @($contract.required_checks)) {
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
    phase = 20
    status = $status
    evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
    contract = "evals/phase20-final-release-manifest-contract.json"
    artifact_decision = "docs/RELEASE_ARTIFACT_DECISION.md"
    manifest = if ($manifestExists) { ConvertTo-ProjectRelativePath $manifestPath } else { $null }
    build_log = ConvertTo-ProjectRelativePath $buildLogPath
    artifacts = @($artifactResults)
    update_plans = @($updatePlans)
    failures = @($failures)
    checks = @($checks)
}

$jsonPath = Join-Path $EvidenceDir "final-release-manifest.json"
$summaryPath = Join-Path $EvidenceDir "final-release-manifest-summary.md"
$payload | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$summary = [System.Collections.Generic.List[string]]::new()
$summary.Add("# Final Release Manifest Evidence") | Out-Null
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
