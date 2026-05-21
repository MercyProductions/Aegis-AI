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

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\extension-package-candidates" (Get-Date -Format "yyyyMMdd-HHmmss"))
} else {
  $EvidenceDir = [System.IO.Path]::GetFullPath($EvidenceDir)
}

$script:Checks = @()
$script:Failures = @()

function Read-ProjectFile {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  $path = Join-Path $Root $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required extension package candidate file is missing: $RelativePath"
  }
  return Get-Content -LiteralPath $path -Raw
}

function Read-ProjectJson {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  return Read-ProjectFile $RelativePath | ConvertFrom-Json
}

function ConvertTo-CheckId {
  param([Parameter(Mandatory = $true)][string]$Value)

  return $Value.Replace("/", "-").Replace("\", "-").Replace(" ", "-").Replace(":", "").Replace("{", "").Replace("}", "").ToLowerInvariant()
}

function Add-CandidateCheck {
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

function Assert-SetIncludes {
  param(
    [Parameter(Mandatory = $true)][string]$IdPrefix,
    [Parameter(Mandatory = $true)][object[]]$Values,
    [Parameter(Mandatory = $true)][string[]]$Required,
    [Parameter(Mandatory = $true)][string]$Label
  )

  $actual = @($Values | ForEach-Object { [string]$_ })
  foreach ($item in $Required) {
    Add-CandidateCheck -Id "$IdPrefix-$(ConvertTo-CheckId $item)" -Passed ($actual -contains $item) -Detail "$Label must include '$item'."
  }
}

function Assert-SourceContains {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$Text,
    [Parameter(Mandatory = $true)][string]$Pattern,
    [Parameter(Mandatory = $true)][string]$Detail
  )

  Add-CandidateCheck -Id $Id -Passed ([bool]($Text -match $Pattern)) -Detail $Detail
}

function Get-RelativePath {
  param([Parameter(Mandatory = $true)][string]$FullPath)

  $rootUri = [System.Uri]::new(($Root.TrimEnd('\') + '\'))
  $pathUri = [System.Uri]::new([System.IO.Path]::GetFullPath($FullPath))
  return [System.Uri]::UnescapeDataString($rootUri.MakeRelativeUri($pathUri).ToString()).Replace("/", "\")
}

function Get-ArtifactStatus {
  param([Parameter(Mandatory = $true)][object]$Candidate)

  $artifactRelative = [string]$Candidate.artifact
  $artifactPath = Join-Path $Root $artifactRelative
  $present = Test-Path -LiteralPath $artifactPath -PathType Leaf
  $size = if ($present) { (Get-Item -LiteralPath $artifactPath).Length } else { 0 }
  $minimumSize = [int64]$Candidate.minimum_size_bytes
  $docs = @()
  foreach ($doc in @($Candidate.required_docs)) {
    $relative = [string]$doc
    $path = Join-Path $Root $relative
    $docPresent = Test-Path -LiteralPath $path -PathType Leaf
    $docs += [pscustomobject]@{
      path = $relative
      present = $docPresent
      size_bytes = if ($docPresent) { (Get-Item -LiteralPath $path).Length } else { 0 }
    }
  }

  return [pscustomobject]@{
    id = [string]$Candidate.id
    artifact = $artifactRelative
    present = $present
    size_bytes = $size
    minimum_size_bytes = $minimumSize
    size_ok = $size -ge $minimumSize
    docs = $docs
    docs_ready = -not [bool](@($docs) | Where-Object { -not $_.present -or $_.size_bytes -le 0 } | Select-Object -First 1)
    validation_commands = @($Candidate.validation_commands | ForEach-Object { [string]$_ })
  }
}

$contract = Read-ProjectJson "evals\phase18-extension-package-candidates-contract.json"
$docs = Read-ProjectFile "docs\EXTENSION_PACKAGE_CANDIDATES.md"
$preflightDocs = Read-ProjectFile "docs\RELEASE_ARTIFACT_PREFLIGHT.md"
$releaseDocs = Read-ProjectFile "docs\RELEASE_PACKAGING_AND_UPDATES.md"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"
$vscodePackage = Read-ProjectJson "vscode-plugins\aegis-local-autopilot\package.json"
$visualStudioBuild = Read-ProjectFile "visual-studio-extensions\aegis-local-agent-vs\build.ps1"

Add-CandidateCheck -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Detail "Phase 18 extension package candidates contract must use the current schema version."
Add-CandidateCheck -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/extension-package-candidates") -Detail "Phase 18 candidates must have a stable .aegis root."
Add-CandidateCheck -Id "contract-current-status-ready" -Passed ([string]$contract.current_required_status -eq "ready") -Detail "Extension package candidates should be ready once both VSIX artifacts exist."
Assert-SetIncludes -IdPrefix "candidate-id" -Values @($contract.package_candidates | ForEach-Object { $_.id }) -Required @("vscode-extension", "visual-studio-extension") -Label "Package candidate ids"
Assert-SetIncludes -IdPrefix "candidate-output" -Values @($contract.candidate_outputs) -Required @("extension-package-candidates.json", "extension-package-candidates-summary.md") -Label "Candidate outputs"

foreach ($file in @($contract.required_contract_files)) {
  $relativePath = [string]$file
  Add-CandidateCheck -Id "contract-file-$(ConvertTo-CheckId $relativePath)" -Passed (Test-Path -LiteralPath (Join-Path $Root $relativePath) -PathType Leaf) -Detail "Required Phase 18 contract file must exist: $relativePath"
}

Assert-SourceContains -Id "docs-contract-link" -Text $docs -Pattern 'phase18-extension-package-candidates-contract\.json' -Detail "Candidate docs must link the Phase 18 contract."
Assert-SourceContains -Id "docs-command" -Text $docs -Pattern 'test-extension-package-candidates\.ps1' -Detail "Candidate docs must document the validation command."
Assert-SourceContains -Id "docs-evidence-root" -Text $docs -Pattern '\.aegis/extension-package-candidates' -Detail "Candidate docs must document the evidence root."
Assert-SourceContains -Id "preflight-docs-vsix" -Text $preflightDocs -Pattern 'vscode_vsix_missing|visual_studio_vsix_missing' -Detail "Preflight docs must keep VSIX blocker semantics visible."
Assert-SourceContains -Id "release-docs-vsix" -Text $releaseDocs -Pattern 'AegisLocalAgentVs\.vsix|aegis-local-autopilot' -Detail "Release packaging docs must mention extension artifacts."
Assert-SourceContains -Id "validator-candidate-script" -Text $validator -Pattern 'test-extension-package-candidates\.ps1' -Detail "Ecosystem validation must run the extension package candidates gate."
Assert-SourceContains -Id "validator-candidate-gate" -Text $validator -Pattern 'extension-package-candidates' -Detail "Ecosystem validation must name the extension package candidates gate."
Assert-SourceContains -Id "vscode-package-script" -Text ($vscodePackage.scripts.package) -Pattern 'package-release\.js' -Detail "VS Code package script must use package-release.js."
Assert-SourceContains -Id "visual-studio-release-copy" -Text $visualStudioBuild -Pattern 'AegisLocalAgentVs\.vsix' -Detail "Visual Studio build must copy the VSIX to the release folder."

$candidates = @($contract.package_candidates | ForEach-Object { Get-ArtifactStatus -Candidate $_ })
foreach ($candidate in $candidates) {
  Add-CandidateCheck -Id "artifact-present-$($candidate.id)" -Passed ([bool]$candidate.present) -Detail "Artifact must exist: $($candidate.artifact)"
  Add-CandidateCheck -Id "artifact-size-$($candidate.id)" -Passed ([bool]$candidate.size_ok) -Detail "Artifact must be at least $($candidate.minimum_size_bytes) bytes: $($candidate.artifact)"
  Add-CandidateCheck -Id "release-docs-$($candidate.id)" -Passed ([bool]$candidate.docs_ready) -Detail "Release docs must exist and be non-empty for $($candidate.id)."
}

$ready = -not [bool](@($candidates) | Where-Object { -not $_.present -or -not $_.size_ok -or -not $_.docs_ready } | Select-Object -First 1)
$status = if ($ready) { "ready" } else { "blocked" }
Add-CandidateCheck -Id "candidate-current-status" -Passed ($status -eq [string]$contract.current_required_status) -Detail "Extension package candidate status must be '$($contract.current_required_status)' for the current evidence state."

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$jsonPath = Join-Path $EvidenceDir "extension-package-candidates.json"
$markdownPath = Join-Path $EvidenceDir "extension-package-candidates-summary.md"

$payload = [pscustomobject]@{
  root = $Root
  status = $status
  generated_at = (Get-Date).ToString("o")
  evidence_dir = $EvidenceDir
  contract = [pscustomobject]@{
    schema_version = [string]$contract.schema_version
    evidence_root = [string]$contract.evidence_root
  }
  candidates = $candidates
  checks = $script:Checks
}
$payload | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 18 Extension Package Candidates"
$markdown += ""
$markdown += "- Status: $status"
$markdown += "- Generated at: $($payload.generated_at)"
$markdown += "- Evidence dir: $EvidenceDir"
$markdown += ""
$markdown += "## Candidates"
$markdown += ""
$markdown += "| Candidate | Artifact | Present | Size Bytes | Docs Ready |"
$markdown += "| --- | --- | --- | ---: | --- |"
foreach ($candidate in $candidates) {
  $markdown += "| $($candidate.id) | $($candidate.artifact) | $($candidate.present) | $($candidate.size_bytes) | $($candidate.docs_ready) |"
}
$markdown += ""
$markdown += "## Release Docs"
$markdown += ""
$markdown += "| Candidate | Doc | Present | Size Bytes |"
$markdown += "| --- | --- | --- | ---: |"
foreach ($candidate in $candidates) {
  foreach ($doc in @($candidate.docs)) {
    $markdown += "| $($candidate.id) | $($doc.path) | $($doc.present) | $($doc.size_bytes) |"
  }
}
$markdown += ""
$markdown += "## Checks"
$markdown += ""
$markdown += "| Check | Status | Detail |"
$markdown += "| --- | --- | --- |"
foreach ($check in $script:Checks) {
  $checkStatus = if ($check.passed) { "passed" } else { "failed" }
  $detail = ([string]$check.detail).Replace("|", "\|")
  $markdown += "| $($check.id) | $checkStatus | $detail |"
}
$markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

$payload | ConvertTo-Json -Depth 10

if ($script:Failures.Count -gt 0) {
  throw "Extension package candidate validation failed:`n - $($script:Failures -join "`n - ")"
}
