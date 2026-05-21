param(
    [string]$Root = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
    $ScriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
    $Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $ScriptRoot))
} else {
    $Root = [System.IO.Path]::GetFullPath($Root)
}

$script:Checks = @()
$script:Failures = @()

function Read-ProjectFile {
    param([Parameter(Mandatory = $true)][string]$RelativePath)

    $path = Join-Path $Root $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required desktop contract file is missing: $RelativePath"
    }
    return Get-Content -LiteralPath $path -Raw
}

function Add-ContractCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][bool]$Passed,
        [Parameter(Mandatory = $true)][string]$Detail
    )

    $script:Checks += [pscustomobject]@{
        id = $Id
        passed = $Passed
        detail = $Detail
    }
    if (-not $Passed) {
        $script:Failures += $Detail
    }
}

function Assert-SourceContains {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [Parameter(Mandatory = $true)][string]$Detail
    )

    Add-ContractCheck -Id $Id -Passed ([bool]($Text -match $Pattern)) -Detail $Detail
}

$clientHeader = Read-ProjectFile "src\AegisClient.h"
$coreClient = Read-ProjectFile "src\core\CoreApiClient.cpp"
$appSource = Read-ProjectFile "src\AegisChatApp.cpp"
$runtimePresenter = Read-ProjectFile "src\desktop\RuntimeStatusPresenter.cpp"
$runtimePresenterHeader = Read-ProjectFile "src\desktop\RuntimeStatusPresenter.h"
$cmake = Read-ProjectFile "CMakeLists.txt"
$vcxproj = Read-ProjectFile "AegisChatBotDesktop.vcxproj"
$buildScript = Read-ProjectFile "build.ps1"

Assert-SourceContains `
    -Id "desktop-version-constant" `
    -Text $coreClient `
    -Pattern 'kDesktopClientVersion\s*=\s*"0\.2\.0"' `
    -Detail "CoreApiClient must advertise the native desktop release version used by Core compatibility checks."

Assert-SourceContains `
    -Id "desktop-schema-constant" `
    -Text $coreClient `
    -Pattern 'kDesktopReleaseSchemaVersion\s*=\s*"2026\.05\.12"' `
    -Detail "CoreApiClient must send the desktop release schema version to Core compatibility checks."

Assert-SourceContains `
    -Id "desktop-capability-helper" `
    -Text $coreClient `
    -Pattern 'DesktopRuntimeCapabilities' `
    -Detail "Desktop capabilities must be owned by a shared helper instead of duplicated between registration and compatibility checks."

Assert-SourceContains `
    -Id "desktop-release-capability" `
    -Text $coreClient `
    -Pattern '"release-compatibility"' `
    -Detail "Desktop must continue advertising the release-compatibility capability."

Assert-SourceContains `
    -Id "desktop-compatibility-endpoint" `
    -Text $coreClient `
    -Pattern '/v1/release/compatibility' `
    -Detail "Desktop must continue checking Core release compatibility through /v1/release/compatibility."

Assert-SourceContains `
    -Id "desktop-registers-client" `
    -Text $coreClient `
    -Pattern 'RegisterClient\(' `
    -Detail "Desktop must register itself with Core before relying on Core-owned runtime workflows."

Assert-SourceContains `
    -Id "desktop-parses-compatibility-state" `
    -Text $coreClient `
    -Pattern 'release_compatible\s*=\s*compatibility\["compatible"\]\.AsBool' `
    -Detail "Desktop must parse Core's release-compatible boolean."

Assert-SourceContains `
    -Id "desktop-parses-compatibility-blockers" `
    -Text $coreClient `
    -Pattern 'release_compatibility_blockers\s*=\s*ParseStringArray\(compatibility\["blockers"\]\)' `
    -Detail "Desktop must surface Core release compatibility blockers."

Assert-SourceContains `
    -Id "desktop-parses-compatibility-warnings" `
    -Text $coreClient `
    -Pattern 'release_compatibility_warnings\s*=\s*ParseStringArray\(compatibility\["warnings"\]\)' `
    -Detail "Desktop must surface Core release compatibility warnings."

Assert-SourceContains `
    -Id "desktop-parses-compatibility-recommendations" `
    -Text $coreClient `
    -Pattern 'release_compatibility_recommendations\s*=\s*ParseStringArray\(compatibility\["recommendations"\]\)' `
    -Detail "Desktop must surface Core release compatibility recommendations."

Assert-SourceContains `
    -Id "desktop-status-contract-fields" `
    -Text $clientHeader `
    -Pattern 'release_compatibility_checked[\s\S]*release_compatible[\s\S]*release_required_core_version[\s\S]*release_minimum_client_version[\s\S]*release_compatibility_blockers' `
    -Detail "DesktopRuntimeStatus must carry compatibility status, requirements, blockers, warnings, and recommendations."

Assert-SourceContains `
    -Id "desktop-renders-compatibility-blocker" `
    -Text $runtimePresenter `
    -Pattern 'Compatibility blocker:' `
    -Detail "Runtime status presenter must render Core release compatibility blockers."

Assert-SourceContains `
    -Id "desktop-renders-compatibility-warning" `
    -Text $runtimePresenter `
    -Pattern 'Compatibility warning:' `
    -Detail "Runtime status presenter must render Core release compatibility warnings."

Assert-SourceContains `
    -Id "desktop-renders-compatibility-requirements" `
    -Text $runtimePresenter `
    -Pattern 'Release requires: Core' `
    -Detail "Runtime status presenter must render minimum Core/Desktop release requirements."

Assert-SourceContains `
    -Id "desktop-runtime-presenter-contract" `
    -Text ($runtimePresenterHeader + $runtimePresenter) `
    -Pattern 'RuntimeServiceLabel[\s\S]*ReleaseCompatibilityTone[\s\S]*BuildReleaseCompatibilityView' `
    -Detail "Desktop runtime status presentation rules must live in the extracted presenter module."

Assert-SourceContains `
    -Id "desktop-runtime-panel-uses-presenter" `
    -Text $appSource `
    -Pattern 'RuntimeStatusPresenter\.h[\s\S]*RuntimeServiceLabel\(core_online\)[\s\S]*BuildReleaseCompatibilityView\(runtime_status_\)' `
    -Detail "AegisChatApp runtime status panel must use the extracted runtime status presenter."

Assert-SourceContains `
    -Id "desktop-cmake-includes-core-client" `
    -Text $cmake `
    -Pattern 'src/core/CoreApiClient\.cpp' `
    -Detail "CMake desktop build must include the Core API client."

Assert-SourceContains `
    -Id "desktop-cmake-includes-runtime-presenter" `
    -Text $cmake `
    -Pattern 'src/desktop/RuntimeStatusPresenter\.cpp' `
    -Detail "CMake desktop build must include the runtime status presenter."

Assert-SourceContains `
    -Id "desktop-msbuild-includes-core-client" `
    -Text $vcxproj `
    -Pattern 'src\\core\\CoreApiClient\.cpp' `
    -Detail "Visual Studio desktop build must include the Core API client."

Assert-SourceContains `
    -Id "desktop-msbuild-includes-runtime-presenter" `
    -Text $vcxproj `
    -Pattern 'src\\desktop\\RuntimeStatusPresenter\.cpp' `
    -Detail "Visual Studio desktop build must include the runtime status presenter."

Assert-SourceContains `
    -Id "desktop-build-runs-contract" `
    -Text $buildScript `
    -Pattern 'test-desktop-contract\.ps1[\s\S]*LASTEXITCODE[\s\S]*Desktop source contract failed' `
    -Detail "Desktop build must run the source contract guard before compiling and fail when the guard fails."

$summary = [pscustomobject]@{
    root = $Root
    status = if ($script:Failures.Count -eq 0) { "passed" } else { "failed" }
    checked_at = (Get-Date).ToString("o")
    source_metrics = [pscustomobject]@{
        aegis_chat_app_bytes = ([Text.Encoding]::UTF8.GetByteCount($appSource))
        aegis_client_bytes = ([Text.Encoding]::UTF8.GetByteCount((Read-ProjectFile "src\AegisClient.cpp")))
        runtime_status_presenter_bytes = ([Text.Encoding]::UTF8.GetByteCount($runtimePresenter))
    }
    checks = $script:Checks
}

$summary | ConvertTo-Json -Depth 5

if ($script:Failures.Count -gt 0) {
    throw "Desktop contract validation failed:`n - $($script:Failures -join "`n - ")"
}
