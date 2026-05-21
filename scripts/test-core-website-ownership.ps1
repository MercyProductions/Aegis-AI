param(
  [string]$Root = "",
  [string]$EvidenceDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
  $ScriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $ScriptRoot))
} else {
  $Root = [System.IO.Path]::GetFullPath($Root)
}

function Join-ProjectPath {
  param([Parameter(Mandatory = $true)][string]$Path)
  return Join-Path $Root $Path
}

function Test-UnderRoot {
  param([Parameter(Mandatory = $true)][string]$Path)

  $full = [System.IO.Path]::GetFullPath($Path)
  $rootWithSlash = $Root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if (-not ($full.Equals($Root, [System.StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase))) {
    throw "Refusing to write outside project root: $full"
  }
  return $full
}

function ConvertTo-ProjectRelativePath {
  param([Parameter(Mandatory = $true)][string]$Path)

  $full = [System.IO.Path]::GetFullPath($Path)
  $rootWithSlash = $Root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if ($full.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $full.Substring($rootWithSlash.Length)
  }
  return $full
}

function ConvertTo-CheckId {
  param([Parameter(Mandatory = $true)][string]$Value)
  return $Value.Replace("/", "-").Replace("\", "-").Replace(" ", "-").Replace(":", "").Replace("{", "").Replace("}", "").ToLowerInvariant()
}

function Read-ProjectFile {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  $path = Join-ProjectPath $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required Phase 25 file is missing: $RelativePath"
  }
  return Get-Content -LiteralPath $path -Raw
}

function Read-ProjectJson {
  param([Parameter(Mandatory = $true)][string]$RelativePath)
  return Read-ProjectFile $RelativePath | ConvertFrom-Json
}

function Add-Check {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][bool]$Passed,
    [Parameter(Mandatory = $true)][string]$Message,
    [object]$Details = $null
  )

  $script:Checks += [pscustomobject]@{
    id = $Id
    passed = $Passed
    message = $Message
    details = $Details
  }
  if (-not $Passed) {
    $script:Failures += $Message
  }
}

function Test-TextContainsAll {
  param(
    [Parameter(Mandatory = $true)][string]$Text,
    [Parameter(Mandatory = $true)][object[]]$Markers
  )

  foreach ($marker in @($Markers)) {
    if (-not $Text.Contains([string]$marker)) {
      return $false
    }
  }
  return $true
}

function Invoke-LoggedCommand {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$Executable,
    [string[]]$Arguments = @()
  )

  $resolvedWorkingDirectory = [System.IO.Path]::GetFullPath((Join-Path $Root $WorkingDirectory))
  $logPath = Join-Path $EvidenceDir "$Id.log"
  $command = (@($Executable) + $Arguments) -join " "
  $started = Get-Date
  $exitCode = 0
  $status = "passed"
  $reason = ""

  @(
    "Command: $command",
    "Working directory: $resolvedWorkingDirectory",
    "Started: $($started.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))",
    ""
  ) | Set-Content -LiteralPath $logPath -Encoding UTF8

  try {
    Push-Location $resolvedWorkingDirectory
    $global:LASTEXITCODE = 0
    & $Executable @Arguments *>> $logPath
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    if ($exitCode -ne 0) {
      $status = "failed"
      $reason = "Exited with code $exitCode."
    }
  } catch {
    $status = "failed"
    $exitCode = 1
    $reason = $_.Exception.Message
    "" | Add-Content -LiteralPath $logPath -Encoding UTF8
    "Exception:" | Add-Content -LiteralPath $logPath -Encoding UTF8
    ($_ | Out-String) | Add-Content -LiteralPath $logPath -Encoding UTF8
  } finally {
    Pop-Location
  }

  $ended = Get-Date
  $duration = [Math]::Round(($ended - $started).TotalSeconds, 2)
  @(
    "",
    "Ended: $($ended.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))",
    "Duration seconds: $duration",
    "Exit code: $exitCode",
    "Status: $status",
    "Reason: $reason"
  ) | Add-Content -LiteralPath $logPath -Encoding UTF8

  Add-Check -Id "command-$(ConvertTo-CheckId $Id)" -Passed ($status -eq "passed") -Message "Validation command must pass: $command" -Details @{ log = ConvertTo-ProjectRelativePath $logPath; duration_seconds = $duration }

  return [pscustomobject]@{
    id = $Id
    command = $command
    working_directory = ConvertTo-ProjectRelativePath $resolvedWorkingDirectory
    status = $status
    exit_code = $exitCode
    duration_seconds = $duration
    log = ConvertTo-ProjectRelativePath $logPath
  }
}

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\core-website-ownership" (Get-Date -Format "yyyyMMdd-HHmmss"))
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root $EvidenceDir
}
$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$script:Checks = @()
$script:Failures = @()
$contract = Read-ProjectJson "evals\phase25-core-website-ownership-contract.json"

$ownershipSource = Read-ProjectFile ([string]$contract.ownership_source)
$runtimeRoutes = Read-ProjectFile "website/backend/aegis_ai/routes/runtime.py"
$mainSource = Read-ProjectFile "website/backend/aegis_ai/main.py"
$coreClientSource = Read-ProjectFile "website/backend/aegis_ai/services/core_client.py"
$coreServerSource = Read-ProjectFile "aegis-core/aegis_core/server.py"
$providerAccountsRoutes = Read-ProjectFile "website/backend/aegis_ai/routes/provider_accounts.py"

Add-Check -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Message "Phase 25 contract must use schema version 2026.05.21."
Add-Check -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/core-website-ownership") -Message "Phase 25 evidence root must be .aegis/core-website-ownership."
Add-Check -Id "contract-required-status" -Passed ([string]$contract.current_required_status -eq "ready") -Message "Phase 25 required status must be ready."
Add-Check -Id "ownership-schema-version" -Passed ([bool]($ownershipSource -match 'OWNERSHIP_SCHEMA_VERSION\s*=\s*"2026\.05\.21"')) -Message "Runtime ownership source must expose schema version 2026.05.21."
Add-Check -Id "ownership-endpoint" -Passed ($runtimeRoutes.Contains('/api/runtime/ownership')) -Message "Website runtime routes must expose /api/runtime/ownership."
Add-Check -Id "ownership-routes-registered" -Passed ($mainSource.Contains('register_runtime_routes(')) -Message "Website main app must register runtime routes."

foreach ($relativePath in @($contract.required_contract_files)) {
  $path = Join-ProjectPath ([string]$relativePath)
  Add-Check -Id "contract-file-$(ConvertTo-CheckId ([string]$relativePath))" -Passed (Test-Path -LiteralPath $path -PathType Leaf) -Message "Required Phase 25 file must exist: $relativePath"
}

$domainSummaries = @()
foreach ($domainSpec in @($contract.required_domains)) {
  $domain = [string]$domainSpec.domain
  $owner = [string]$domainSpec.owner
  $domainPresent = [bool]($ownershipSource -match ('domain\s*=\s*"' + [regex]::Escape($domain) + '"'))
  $ownerPresent = [bool]($ownershipSource -match ('owner\s*=\s*"' + [regex]::Escape($owner) + '"'))
  Add-Check -Id "domain-present-$(ConvertTo-CheckId $domain)" -Passed $domainPresent -Message "Ownership matrix must include domain '$domain'."
  Add-Check -Id "domain-owner-$(ConvertTo-CheckId $domain)" -Passed ($domainPresent -and $ownerPresent) -Message "Ownership matrix must include owner '$owner' for domain '$domain'."
  $domainSummaries += [pscustomobject]@{
    domain = $domain
    owner = $owner
    present = $domainPresent
    owner_marker_present = $ownerPresent
  }
}

foreach ($domain in @($contract.core_owned_domains)) {
  Add-Check -Id "core-owned-$(ConvertTo-CheckId ([string]$domain))" -Passed ([bool](@($contract.required_domains) | Where-Object { [string]$_.domain -eq [string]$domain -and [string]$_.owner -eq "aegis-core" } | Select-Object -First 1)) -Message "Core-owned domain '$domain' must be owned by aegis-core."
}

foreach ($domain in @($contract.website_owned_domains)) {
  Add-Check -Id "website-owned-$(ConvertTo-CheckId ([string]$domain))" -Passed ([bool](@($contract.required_domains) | Where-Object { [string]$_.domain -eq [string]$domain -and [string]$_.owner -eq "website" } | Select-Object -First 1)) -Message "Website-owned domain '$domain' must be owned by Website."
}

foreach ($domain in @($contract.compatibility_domains)) {
  Add-Check -Id "compatibility-owned-$(ConvertTo-CheckId ([string]$domain))" -Passed ([bool](@($contract.required_domains) | Where-Object { [string]$_.domain -eq [string]$domain -and [string]$_.owner -eq "compatibility" } | Select-Object -First 1)) -Message "Compatibility domain '$domain' must be marked compatibility."
}

$delegationSummaries = @()
foreach ($mapping in @($contract.core_delegation_map)) {
  $domain = [string]$mapping.domain
  foreach ($marker in @($mapping.core_client_markers)) {
    Add-Check -Id "core-client-$domain-$(ConvertTo-CheckId ([string]$marker))" -Passed ($coreClientSource.Contains([string]$marker)) -Message "Core client must include marker '$marker' for '$domain'."
  }
  foreach ($marker in @($mapping.website_main_markers)) {
    Add-Check -Id "website-main-$domain-$(ConvertTo-CheckId ([string]$marker))" -Passed ($mainSource.Contains([string]$marker)) -Message "Website main must delegate through marker '$marker' for '$domain'."
  }
  foreach ($route in @($mapping.core_server_routes)) {
    Add-Check -Id "core-route-$domain-$(ConvertTo-CheckId ([string]$route))" -Passed ($coreServerSource.Contains([string]$route)) -Message "Aegis Core server must expose route '$route' for '$domain'."
  }
  $delegationSummaries += [pscustomobject]@{
    domain = $domain
    core_client_markers = @($mapping.core_client_markers)
    website_main_markers = @($mapping.website_main_markers)
    core_server_routes = @($mapping.core_server_routes)
  }
}

foreach ($routeModule in @($contract.thin_route_modules)) {
  $path = [string]$routeModule
  $text = Read-ProjectFile $path
  Add-Check -Id "thin-route-callable-$(ConvertTo-CheckId $path)" -Passed ($text.Contains("Callable")) -Message "Route module '$path' must accept injected callables."
  Add-Check -Id "thin-route-no-core-client-$(ConvertTo-CheckId $path)" -Passed (-not ($text -match 'core_runtime_client|AegisCoreClient|workspace_manager')) -Message "Route module '$path' must remain a thin adapter without direct Core/workspace manager ownership."
}

Add-Check -Id "provider-accounts-website-owned" -Passed ($ownershipSource.Contains('domain="provider-accounts"') -and $ownershipSource.Contains('owner="website"')) -Message "Provider accounts must remain Website-owned in the ownership matrix."
Add-Check -Id "provider-accounts-routes" -Passed ($providerAccountsRoutes.Contains('/api/provider-accounts') -and $providerAccountsRoutes.Contains('ProviderAccountManager')) -Message "Provider-account setup routes must remain Website-local."

foreach ($docSpec in @($contract.docs)) {
  $path = [string]$docSpec.path
  $text = Read-ProjectFile $path
  foreach ($marker in @($docSpec.required_markers)) {
    Add-Check -Id "doc-$($path)-$(ConvertTo-CheckId ([string]$marker))" -Passed ($text.Contains([string]$marker)) -Message "Documentation '$path' must include marker '$marker'."
  }
}

$clientSummaries = @()
foreach ($client in @($contract.client_contracts)) {
  $id = [string]$client.id
  $combined = ""
  foreach ($pathValue in @($client.files)) {
    $path = [string]$pathValue
    $combined += "`n" + (Read-ProjectFile $path)
  }
  $markersPresent = Test-TextContainsAll -Text $combined -Markers @($client.required_markers)
  Add-Check -Id "client-contract-$id" -Passed $markersPresent -Message "Client contract '$id' must include all required ownership markers."
  $clientSummaries += [pscustomobject]@{
    id = $id
    files = @($client.files)
    required_markers = @($client.required_markers)
    markers_present = $markersPresent
  }
}

$commandResults = @()
$commandResults += Invoke-LoggedCommand -Id "backend-runtime-ownership-tests" -WorkingDirectory "website\backend" -Executable "python" -Arguments @("-m", "pytest", "tests/test_runtime_ownership.py", "-q")
$commandResults += Invoke-LoggedCommand -Id "frontend-api-ownership-tests" -WorkingDirectory "website\frontend" -Executable "npm" -Arguments @("test", "--", "src/api.test.ts")

$summary = [pscustomobject]@{
  schema_version = "2026.05.21"
  phase = 25
  status = if ($script:Failures.Count -eq 0) { "ready" } else { "blocked" }
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  contract = "evals/phase25-core-website-ownership-contract.json"
  ownership_source = [string]$contract.ownership_source
  ownership_endpoint = [string]$contract.ownership_endpoint
  domains = $domainSummaries
  core_delegations = $delegationSummaries
  clients = $clientSummaries
  commands = $commandResults
  failures = $script:Failures
  checks = $script:Checks
}

$jsonPath = Join-Path $EvidenceDir "core-website-ownership.json"
$markdownPath = Join-Path $EvidenceDir "core-website-ownership-summary.md"
$summary | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 25 Core Website Ownership Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Ownership source: $($summary.ownership_source)"
$markdown += "- Ownership endpoint: $($summary.ownership_endpoint)"
$markdown += "- Domains checked: $(@($summary.domains).Count)"
$markdown += "- Client contracts checked: $(@($summary.clients).Count)"
$markdown += ""
$markdown += "## Domains"
$markdown += ""
$markdown += "| Domain | Owner | Present |"
$markdown += "| --- | --- | --- |"
foreach ($domain in @($summary.domains)) {
  $markdown += "| $($domain.domain) | $($domain.owner) | $($domain.present) |"
}
$markdown += ""
$markdown += "## Commands"
$markdown += ""
$markdown += "| Command | Status | Seconds | Log |"
$markdown += "| --- | --- | ---: | --- |"
foreach ($command in @($summary.commands)) {
  $markdown += "| $($command.command.Replace('|', '\|')) | $($command.status) | $($command.duration_seconds) | $($command.log) |"
}
$markdown += ""
$markdown += "## Checks"
$markdown += ""
$markdown += "| Check | Status | Message |"
$markdown += "| --- | --- | --- |"
foreach ($check in @($summary.checks)) {
  $status = if ([bool]$check.passed) { "passed" } else { "failed" }
  $message = ([string]$check.message).Replace("|", "\|")
  $markdown += "| $($check.id) | $status | $message |"
}
$markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

$summary | ConvertTo-Json -Depth 14

if ($script:Failures.Count -gt 0) {
  throw "Core/Website ownership validation failed:`n - $($script:Failures -join "`n - ")"
}
