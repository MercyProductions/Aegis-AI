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

function Test-UnderRoot {
  param([string]$Path)

  $full = [System.IO.Path]::GetFullPath($Path)
  $rootWithSlash = $Root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if (-not ($full.Equals($Root, [System.StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase))) {
    throw "Refusing to write outside project root: $full"
  }
  return $full
}

function ConvertTo-ProjectRelativePath {
  param([string]$Path)

  $full = [System.IO.Path]::GetFullPath($Path)
  $rootWithSlash = $Root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if ($full.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $full.Substring($rootWithSlash.Length)
  }
  return $full
}

function ConvertTo-CheckId {
  param([string]$Value)
  return $Value.Replace("/", "-").Replace("\", "-").Replace(" ", "-").Replace(":", "").Replace("{", "").Replace("}", "").ToLowerInvariant()
}

function Read-TextFile {
  param([string]$RelativePath)

  $path = Join-ProjectPath $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required file is missing: $RelativePath"
  }
  return Get-Content -LiteralPath $path -Raw
}

function Read-JsonFile {
  param([string]$RelativePath)
  return Read-TextFile $RelativePath | ConvertFrom-Json
}

function Read-JsonPath {
  param([string]$Path)
  return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Add-Check {
  param(
    [System.Collections.Generic.List[object]]$Checks,
    [System.Collections.Generic.List[string]]$Failures,
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

  if (-not $Passed) {
    $Failures.Add($Message) | Out-Null
  }
}

function Get-ManifestComponent {
  param([object]$Manifest, [string]$Id)

  if ($null -eq $Manifest -or $null -eq $Manifest.components) {
    return $null
  }
  $property = $Manifest.components.PSObject.Properties[$Id]
  if ($null -eq $property) {
    return $null
  }
  return $property.Value
}

function Get-PayloadStatus {
  param([object]$Payload)

  if ($null -eq $Payload) {
    return "missing"
  }
  $statusProperty = $Payload.PSObject.Properties["status"]
  if ($null -ne $statusProperty) {
    return [string]$statusProperty.Value
  }
  $overallStatusProperty = $Payload.PSObject.Properties["overall_status"]
  if ($null -ne $overallStatusProperty) {
    return [string]$overallStatusProperty.Value
  }
  return "present"
}

function Get-LatestEvidence {
  param(
    [string]$RootPath,
    [string]$JsonName,
    [string]$SummaryName
  )

  $fullRoot = Join-ProjectPath $RootPath
  if (-not (Test-Path -LiteralPath $fullRoot -PathType Container)) {
    return [pscustomobject]@{
      id = ""
      status = "missing"
      latest_folder = ""
      json_path = ""
      summary_path = ""
      summary_present = $false
      payload = $null
    }
  }

  $folders = @(Get-ChildItem -LiteralPath $fullRoot -Directory | Sort-Object Name -Descending)
  foreach ($folder in $folders) {
    $jsonPath = Join-Path $folder.FullName $JsonName
    $summaryPath = Join-Path $folder.FullName $SummaryName
    if (Test-Path -LiteralPath $jsonPath -PathType Leaf) {
      $payload = Read-JsonPath $jsonPath
      return [pscustomobject]@{
        id = ""
        status = Get-PayloadStatus $payload
        latest_folder = ConvertTo-ProjectRelativePath $folder.FullName
        json_path = ConvertTo-ProjectRelativePath $jsonPath
        summary_path = if (Test-Path -LiteralPath $summaryPath -PathType Leaf) { ConvertTo-ProjectRelativePath $summaryPath } else { "" }
        summary_present = Test-Path -LiteralPath $summaryPath -PathType Leaf
        payload = $payload
      }
    }
  }

  return [pscustomobject]@{
    id = ""
    status = "missing"
    latest_folder = ""
    json_path = ""
    summary_path = ""
    summary_present = $false
    payload = $null
  }
}

function Get-LatestAcceptedEvidence {
  param(
    [string]$RootPath,
    [string]$JsonName,
    [string]$SummaryName,
    [string[]]$AcceptedStatuses
  )

  $fullRoot = Join-ProjectPath $RootPath
  if (-not (Test-Path -LiteralPath $fullRoot -PathType Container)) {
    return Get-LatestEvidence -RootPath $RootPath -JsonName $JsonName -SummaryName $SummaryName
  }

  $folders = @(Get-ChildItem -LiteralPath $fullRoot -Directory | Sort-Object Name -Descending)
  foreach ($folder in $folders) {
    $jsonPath = Join-Path $folder.FullName $JsonName
    $summaryPath = Join-Path $folder.FullName $SummaryName
    if (-not (Test-Path -LiteralPath $jsonPath -PathType Leaf)) {
      continue
    }
    $payload = Read-JsonPath $jsonPath
    $status = Get-PayloadStatus $payload
    $summaryPresent = Test-Path -LiteralPath $summaryPath -PathType Leaf
    if (($AcceptedStatuses -contains $status) -and $summaryPresent) {
      return [pscustomobject]@{
        id = ""
        status = $status
        latest_folder = ConvertTo-ProjectRelativePath $folder.FullName
        json_path = ConvertTo-ProjectRelativePath $jsonPath
        summary_path = ConvertTo-ProjectRelativePath $summaryPath
        summary_present = $true
        payload = $payload
      }
    }
  }

  return Get-LatestEvidence -RootPath $RootPath -JsonName $JsonName -SummaryName $SummaryName
}

function Test-TextContainsPath {
  param(
    [string]$Text,
    [string]$Path
  )

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return $false
  }
  $slashPath = $Path.Replace("\", "/")
  $backslashPath = $Path.Replace("/", "\")
  return $Text.Contains($slashPath) -or $Text.Contains($backslashPath)
}

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\release-notes-limitations" (Get-Date -Format "yyyyMMdd-HHmmss"))
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root $EvidenceDir
}
$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$contract = Read-JsonFile "evals\phase24-release-notes-limitations-contract.json"
$manifest = Read-JsonFile "release\version-manifest.json"
$knownUnstable = Read-TextFile "KNOWN_UNSTABLE_SURFACES.md"

$checks = [System.Collections.Generic.List[object]]::new()
$failures = [System.Collections.Generic.List[string]]::new()

Add-Check -Checks $checks -Failures $failures -Id "contract_schema_version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Message "Phase 24 contract must use schema version 2026.05.21."
Add-Check -Checks $checks -Failures $failures -Id "contract_evidence_root" -Passed ([string]$contract.evidence_root -eq ".aegis/release-notes-limitations") -Message "Phase 24 evidence root must be .aegis/release-notes-limitations."
Add-Check -Checks $checks -Failures $failures -Id "contract_required_status" -Passed ([string]$contract.current_required_status -eq "ready") -Message "Phase 24 current required status must be ready."

foreach ($relativePath in @($contract.required_contract_files)) {
  $path = Join-ProjectPath ([string]$relativePath)
  Add-Check -Checks $checks -Failures $failures -Id "contract_file:$(ConvertTo-CheckId ([string]$relativePath))" -Passed (Test-Path -LiteralPath $path -PathType Leaf) -Message "Required Phase 24 file must exist: $relativePath"
}

$releaseNoteFiles = @()
foreach ($property in @($contract.release_notes.PSObject.Properties)) {
  $id = [string]$property.Name
  $relativePath = [string]$property.Value
  $path = Join-ProjectPath $relativePath
  $present = Test-Path -LiteralPath $path -PathType Leaf
  $text = ""
  if ($present) {
    $text = Get-Content -LiteralPath $path -Raw
  }
  Add-Check -Checks $checks -Failures $failures -Id "release_note_file:$id" -Passed $present -Message "Release note file must be present for $id."
  Add-Check -Checks $checks -Failures $failures -Id "release_note_nonempty:$id" -Passed ($present -and -not [string]::IsNullOrWhiteSpace($text)) -Message "Release note file must be non-empty for $id."
  $releaseNoteFiles += [pscustomobject]@{
    id = $id
    path = $relativePath
    present = $present
    length = $text.Length
    text = $text
  }
}

$rootNote = @($releaseNoteFiles | Where-Object { [string]$_.id -eq "root" } | Select-Object -First 1)
$rootText = if ($null -ne $rootNote) { [string]$rootNote.text } else { "" }

foreach ($section in @($contract.required_release_note_sections)) {
  $sectionTitle = [string]$section
  Add-Check -Checks $checks -Failures $failures -Id "root_section:$(ConvertTo-CheckId $sectionTitle)" -Passed ([bool]($rootText -match ("(?m)^##\s+" + [regex]::Escape($sectionTitle) + "\s*$"))) -Message "Root release notes must include section '$sectionTitle'."
}

Add-Check -Checks $checks -Failures $failures -Id "root_conditional_alpha" -Passed ([bool]($rootText -match "conditional private external alpha")) -Message "Root release notes must identify the candidate as conditional private external alpha."
Add-Check -Checks $checks -Failures $failures -Id "root_not_broad_alpha" -Passed ([bool]($rootText -match "not a broad public alpha|Broad alpha stays blocked")) -Message "Root release notes must keep broad alpha blocked."
Add-Check -Checks $checks -Failures $failures -Id "root_checksums_required" -Passed ([bool]($rootText -match "Checksums are required|checksum-verified")) -Message "Root release notes must state checksums are required."
Add-Check -Checks $checks -Failures $failures -Id "root_unsigned_disclosure" -Passed ([bool]($rootText -match "unsigned local build|unsigned-build limitation|not signed")) -Message "Root release notes must disclose unsigned local builds."

foreach ($componentIdValue in @($contract.release_components)) {
  $componentId = [string]$componentIdValue
  $component = Get-ManifestComponent -Manifest $manifest -Id $componentId
  $componentPresent = $null -ne $component
  Add-Check -Checks $checks -Failures $failures -Id "manifest_component:$componentId" -Passed $componentPresent -Message "release/version-manifest.json must include component '$componentId'."
  if ($componentPresent) {
    $artifact = [string]$component.package.artifact
    $path = [string]$component.package.path
    $sha = [string]$component.package.sha256
    $size = [string]$component.package.size_bytes
    Add-Check -Checks $checks -Failures $failures -Id "root_component:$componentId" -Passed ($rootText.Contains($componentId)) -Message "Root release notes must list component '$componentId'."
    Add-Check -Checks $checks -Failures $failures -Id "root_artifact:$componentId" -Passed ($rootText.Contains($artifact) -and $rootText.Contains($path)) -Message "Root release notes must list artifact and path for '$componentId'."
    Add-Check -Checks $checks -Failures $failures -Id "root_checksum:$componentId" -Passed ($rootText.Contains($sha)) -Message "Root release notes must list SHA-256 for '$componentId'."
    Add-Check -Checks $checks -Failures $failures -Id "root_size:$componentId" -Passed ($rootText.Contains($size)) -Message "Root release notes must list package size for '$componentId'."
  }
}

foreach ($commandValue in @($contract.required_commands)) {
  $command = [string]$commandValue
  Add-Check -Checks $checks -Failures $failures -Id "root_command:$(ConvertTo-CheckId $command)" -Passed ($rootText.Contains($command)) -Message "Root release notes must include command '$command'."
}

foreach ($pathValue in @($contract.required_recovery_paths)) {
  $path = [string]$pathValue
  Add-Check -Checks $checks -Failures $failures -Id "root_recovery_path:$(ConvertTo-CheckId $path)" -Passed ($rootText.Contains($path)) -Message "Root release notes must include recovery path '$path'."
}

foreach ($limitation in @($contract.required_limitations)) {
  $id = [string]$limitation.id
  $pattern = [string]$limitation.pattern
  Add-Check -Checks $checks -Failures $failures -Id "limitation:$id" -Passed ([bool]($rootText -match $pattern)) -Message "Root release notes must disclose limitation '$id'."
}

Add-Check -Checks $checks -Failures $failures -Id "known_unstable_phase24" -Passed ([bool]($knownUnstable -match "release-note|release notes|conditional")) -Message "Known unstable surfaces must mention the current release-note evidence or conditional status."

$evidenceSources = @()
foreach ($source in @($contract.required_evidence_sources)) {
  $id = [string]$source.id
  $acceptedStatuses = @($source.accepted_statuses | ForEach-Object { [string]$_ })
  $evidence = Get-LatestAcceptedEvidence -RootPath ([string]$source.root) -JsonName ([string]$source.json) -SummaryName ([string]$source.summary) -AcceptedStatuses $acceptedStatuses
  $statusAccepted = $acceptedStatuses -contains ([string]$evidence.status)
  $summaryPresent = [bool]$evidence.summary_present
  $folderLinked = Test-TextContainsPath -Text $rootText -Path ([string]$evidence.latest_folder)
  $summaryLinked = Test-TextContainsPath -Text $rootText -Path ([string]$evidence.summary_path)

  Add-Check -Checks $checks -Failures $failures -Id "evidence_status:$id" -Passed $statusAccepted -Message "Required evidence source '$id' must have an accepted status."
  Add-Check -Checks $checks -Failures $failures -Id "evidence_summary:$id" -Passed $summaryPresent -Message "Required evidence source '$id' must have a markdown summary."
  Add-Check -Checks $checks -Failures $failures -Id "release_notes_link:$id" -Passed ($folderLinked -or $summaryLinked) -Message "Root release notes must link evidence source '$id'."

  $evidenceSources += [pscustomobject]@{
    id = $id
    status = [string]$evidence.status
    latest_folder = [string]$evidence.latest_folder
    json_path = [string]$evidence.json_path
    summary_path = [string]$evidence.summary_path
    accepted = $statusAccepted
    summary_present = $summaryPresent
    linked_from_release_notes = ($folderLinked -or $summaryLinked)
  }
}

$componentNoteExpectations = @(
  [pscustomobject]@{ id = "website"; must_match = "release/aegis-website-0.1.0.zip|Known Limitations|unsigned local build" },
  [pscustomobject]@{ id = "desktop"; must_match = "release/aegis-desktop-0.2.0-portable.zip|Known Limitations|installer/update|unsigned local build" },
  [pscustomobject]@{ id = "vscode-extension"; must_match = "release/aegis-local-autopilot-0.1.8.vsix|Known Limitations|VS Code extension-host smoke|unsigned local build" },
  [pscustomobject]@{ id = "visual-studio-extension"; must_match = "release/AegisLocalAgentVs.vsix|Known Limitations|Visual Studio UI workflows|unsigned local build" }
)

foreach ($expectation in $componentNoteExpectations) {
  $note = @($releaseNoteFiles | Where-Object { [string]$_.id -eq [string]$expectation.id } | Select-Object -First 1)
  $text = if ($null -ne $note) { [string]$note.text } else { "" }
  foreach ($patternPart in ([string]$expectation.must_match).Split("|")) {
    Add-Check -Checks $checks -Failures $failures -Id "component_note:$($expectation.id):$(ConvertTo-CheckId $patternPart)" -Passed ([bool]($text -match [regex]::Escape($patternPart))) -Message "Release notes for $($expectation.id) must include '$patternPart'."
  }
}

$summary = [pscustomobject]@{
  schema_version = "2026.05.21"
  phase = 24
  status = if ($failures.Count -eq 0) { "ready" } else { "blocked" }
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  contract = "evals/phase24-release-notes-limitations-contract.json"
  release_notes = @($releaseNoteFiles | ForEach-Object {
    [pscustomobject]@{
      id = [string]$_.id
      path = [string]$_.path
      present = [bool]$_.present
      length = [int]$_.length
    }
  })
  evidence_sources = $evidenceSources
  limitations = @($contract.required_limitations | ForEach-Object { [string]$_.id })
  failures = $failures
  checks = $checks
}

$jsonPath = Join-Path $EvidenceDir "release-notes-limitations.json"
$markdownPath = Join-Path $EvidenceDir "release-notes-limitations-summary.md"
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 24 Release Notes And Limitations Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Release note files: $(@($summary.release_notes).Count)"
$markdown += "- Evidence sources: $(@($summary.evidence_sources).Count)"
$markdown += "- Limitations disclosed: $(@($summary.limitations).Count)"
$markdown += ""
$markdown += "## Release Notes"
$markdown += ""
$markdown += "| Id | Present | Path |"
$markdown += "| --- | --- | --- |"
foreach ($note in @($summary.release_notes)) {
  $markdown += "| $($note.id) | $($note.present) | $($note.path) |"
}
$markdown += ""
$markdown += "## Evidence Sources"
$markdown += ""
$markdown += "| Source | Status | Linked | Latest Folder |"
$markdown += "| --- | --- | --- | --- |"
foreach ($source in @($summary.evidence_sources)) {
  $markdown += "| $($source.id) | $($source.status) | $($source.linked_from_release_notes) | $($source.latest_folder) |"
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

$summary | ConvertTo-Json -Depth 12

if ($failures.Count -gt 0) {
  throw "Release notes limitations validation failed:`n - $($failures -join "`n - ")"
}
