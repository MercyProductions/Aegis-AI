param(
  [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"

$root = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$solution = Join-Path $root "AegisLocalAgentVs.sln"
$project = Join-Path $root "src\AegisLocalAgentVs\AegisLocalAgentVs.csproj"
$projectDir = Split-Path -Parent $project
$release = Join-Path $root "release"
$releaseDocumentationFiles = @(
  "README.md",
  "INSTALL.md",
  "CHANGELOG.md",
  "RELEASE_NOTES.md",
  "TROUBLESHOOTING.md",
  "LICENSE.txt"
)

function Invoke-MSBuild {
  param(
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments
  )

  & dotnet msbuild @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "dotnet msbuild failed with exit code $LASTEXITCODE. Arguments: $($Arguments -join ' ')"
  }
}

function Assert-ReleaseDocumentationSources {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Root,
    [Parameter(Mandatory = $true)]
    [string[]]$FileNames
  )

  $issues = @()
  foreach ($fileName in $FileNames) {
    $sourcePath = Join-Path $Root $fileName
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
      $issues += "Missing release documentation source '$fileName'."
      continue
    }

    $sourceFile = Get-Item -LiteralPath $sourcePath
    if ($sourceFile.Length -eq 0) {
      $issues += "Release documentation source '$fileName' is empty."
    }
  }

  if ($issues.Count -gt 0) {
    throw "Visual Studio release documentation validation failed:`n - $($issues -join "`n - ")"
  }
}

function Convert-CommandIdValue {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Value
  )

  return [Convert]::ToInt32($Value.Substring(2), 16)
}

function Assert-VisualStudioCommandTable {
  param(
    [Parameter(Mandatory = $true)]
    [string]$VsctPath,
    [Parameter(Mandatory = $true)]
    [string]$CommandIdsPath,
    [Parameter(Mandatory = $true)]
    [string]$CommandRegistrationPath
  )

  $vsctText = Get-Content -Raw -LiteralPath $VsctPath
  $commandIdsText = Get-Content -Raw -LiteralPath $CommandIdsPath
  $registrationText = Get-Content -Raw -LiteralPath $CommandRegistrationPath

  $buttonIds = @(
    [regex]::Matches($vsctText, '<Button\b[^>]*\bid="(?<id>[^"]+)"') |
      ForEach-Object { $_.Groups["id"].Value } |
      Sort-Object -Unique
  )

  $symbolValues = @{}
  foreach ($match in [regex]::Matches($vsctText, '<IDSymbol\s+name="(?<name>[^"]+)"\s+value="(?<value>0x[0-9A-Fa-f]+)"\s*/>')) {
    $name = $match.Groups["name"].Value
    if ($name.EndsWith("CommandId")) {
      $symbolValues[$name] = $match.Groups["value"].Value
    }
  }

  $constantValues = @{}
  foreach ($match in [regex]::Matches($commandIdsText, 'public\s+const\s+int\s+(?<name>[A-Za-z0-9_]+)\s*=\s*(?<value>0x[0-9A-Fa-f]+)\s*;')) {
    $constantValues[$match.Groups["name"].Value] = $match.Groups["value"].Value
  }

  $registeredConstants = @(
    [regex]::Matches($registrationText, 'CommandIds\.(?<name>[A-Za-z0-9_]+)') |
      ForEach-Object { $_.Groups["name"].Value } |
      Sort-Object -Unique
  )

  $issues = @()

  foreach ($buttonId in $buttonIds) {
    if (-not $symbolValues.ContainsKey($buttonId)) {
      $issues += "VSCT button '$buttonId' has no matching command IDSymbol."
    }
  }

  foreach ($symbolName in ($symbolValues.Keys | Sort-Object)) {
    if ($buttonIds -notcontains $symbolName) {
      $issues += "VSCT command symbol '$symbolName' has no matching Button."
    }

    $constantName = $symbolName -replace 'CommandId$', ''
    if (-not $constantValues.ContainsKey($constantName)) {
      $issues += "VSCT command symbol '$symbolName' has no matching CommandIds.$constantName constant."
      continue
    }

    $symbolValue = Convert-CommandIdValue $symbolValues[$symbolName]
    $constantValue = Convert-CommandIdValue $constantValues[$constantName]
    if ($symbolValue -ne $constantValue) {
      $issues += "VSCT command symbol '$symbolName' value $($symbolValues[$symbolName]) does not match CommandIds.$constantName value $($constantValues[$constantName])."
    }
  }

  foreach ($constantName in ($constantValues.Keys | Sort-Object)) {
    $symbolName = "${constantName}CommandId"
    if (-not $symbolValues.ContainsKey($symbolName)) {
      $issues += "CommandIds.$constantName has no matching VSCT command symbol '$symbolName'."
    }

    if ($registeredConstants -notcontains $constantName) {
      $issues += "CommandIds.$constantName is not registered in AegisCommands."
    }
  }

  foreach ($registeredName in $registeredConstants) {
    if (-not $constantValues.ContainsKey($registeredName)) {
      $issues += "AegisCommands registers missing CommandIds.$registeredName."
    }
  }

  if ($issues.Count -gt 0) {
    throw "Visual Studio command table validation failed:`n - $($issues -join "`n - ")"
  }
}

function Assert-DiagnosticRedactionGuards {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectDirectory
  )

  $runtimeText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Services\AegisAgentRuntime.cs")
  $safeEditText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Services\SafeEditService.cs")
  $redactorText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Services\DiagnosticRedactor.cs")
  $coreClientText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Services\AegisCoreClient.cs")
  $memoryText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Services\ProjectMemoryService.cs")

  $issues = @()
  if ($runtimeText -match 'result\.Lines\.Add\(\$"[^"]*\{ex\.Message\}') {
    $issues += "AegisAgentRuntime health-check lines must use SafeDiagnostic(ex), not raw ex.Message."
  }
  if ($runtimeText -match 'SetValidationOutput\(ex\.ToString\(\)\)') {
    $issues += "AegisAgentRuntime command error output must redact ex.ToString() before showing it."
  }
  if ($safeEditText -match 'return\s+new\[\]\s*\{[^}]*\+\s*ex\.Message') {
    $issues += "SafeEditService rollback messages must redact ex.Message before returning user-visible text."
  }
  if ($redactorText -notmatch 'AuthorizationHeaderPattern') {
    $issues += "DiagnosticRedactor must redact full Authorization header values before assignment-style redaction runs."
  }
  if ($redactorText -notmatch 'JsonSecretPattern') {
    $issues += "DiagnosticRedactor must redact JSON-shaped secret fields before assignment-style redaction runs."
  }
  if ($redactorText -notmatch '(?s)JsonSecretPattern\.Replace\(redacted, "\$1\[redacted\]"\).*AuthorizationHeaderPattern\.Replace\(redacted, "\$1\[redacted\]"\).*BearerTokenPattern\.Replace\(redacted, "\$1\[redacted\]"\).*AssignmentSecretPattern\.Replace\(redacted, "\$1\[redacted\]"') {
    $issues += "DiagnosticRedactor must apply JSON and Authorization header redaction before bearer and assignment redaction."
  }
  foreach ($secretNeedle in @("x-api-key", "access[_-]?token", "refresh[_-]?token", "id[_-]?token", "client[_-]?secret", "private[_-]?key")) {
    if ($redactorText -notmatch [regex]::Escape($secretNeedle)) {
      $issues += "DiagnosticRedactor must redact OAuth/provider secret field '$secretNeedle'."
    }
    if ($memoryText -notmatch [regex]::Escape($secretNeedle)) {
      $issues += "ProjectMemoryService must filter OAuth/provider secret line '$secretNeedle'."
    }
  }
  if ($coreClientText -notmatch 'DiagnosticRedactor\.RedactAndTruncate\(apiVersion\)' -or $coreClientText -notmatch 'DiagnosticRedactor\.RedactAndTruncate\(kind\)') {
    $issues += "AegisCoreClient contract mismatch diagnostics must redact unexpected api_version and kind values."
  }

  if ($issues.Count -gt 0) {
    throw "Visual Studio diagnostic redaction validation failed:`n - $($issues -join "`n - ")"
  }
}

function Assert-UrlNormalizationGuards {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectDirectory
  )

  $optionsText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Options\AegisOptionsPage.cs")
  $coreClientText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Services\AegisCoreClient.cs")
  $ollamaClientText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Services\OllamaClient.cs")

  $issues = @()
  if ($optionsText -notmatch 'StripKnownServiceEndpointPath') {
    $issues += "AegisSettingsSnapshot must preserve reverse-proxy prefixes while trimming known endpoint suffixes."
  }
  if ($optionsText -notmatch 'BuildServiceUrl') {
    $issues += "AegisSettingsSnapshot must expose a service URL builder that appends API paths below normalized prefixes."
  }
  if ($optionsText -notmatch 'Array\.IndexOf\(lowered, "v1"\)' -or $optionsText -notmatch '"health"' -or $optionsText -notmatch '"models"') {
    $issues += "Core URL normalization must strip known /v1, /health, and /models endpoint suffixes."
  }
  if ($optionsText -notmatch '"api"' -or $optionsText -notmatch '"tags"' -or $optionsText -notmatch '"chat"') {
    $issues += "Ollama URL normalization must strip known /api endpoint suffixes."
  }
  if ($coreClientText -match '\$"\{BaseUrl\}/v1/' -or $coreClientText -notmatch 'CoreUrl\("/v1/health"\)' -or $coreClientText -notmatch 'BuildServiceUrl') {
    $issues += "AegisCoreClient must build Core request URLs through the shared URL helper."
  }
  if ($ollamaClientText -match '\$"\{NormalizeBaseUrl\(settings\)\}/api/' -or $ollamaClientText -notmatch 'OllamaUrl\(settings, "/api/tags"\)' -or $ollamaClientText -notmatch 'BuildServiceUrl') {
    $issues += "OllamaClient must build Ollama request URLs through the shared URL helper."
  }

  if ($issues.Count -gt 0) {
    throw "Visual Studio URL normalization validation failed:`n - $($issues -join "`n - ")"
  }
}

function Assert-SafeEditRollbackGuards {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectDirectory
  )

  $safeEditText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Services\SafeEditService.cs")

  $issues = @()
  foreach ($blockedSegment in @("Library", "Temp", "Logs")) {
    if ($safeEditText -notmatch "`"$([regex]::Escape($blockedSegment))`"") {
      $issues += "SafeEditService must block Unity generated/runtime folder segment '$blockedSegment'."
    }
  }
  foreach ($secretNeedle in @("password", "passwd", "api[_-]?key", "auth", "id_rsa", "keystore")) {
    if ($safeEditText -notmatch [regex]::Escape($secretNeedle)) {
      $issues += "SafeEditService secret filename guard must include '$secretNeedle'."
    }
  }
  if ($safeEditText -match 'SecretFilePattern\.IsMatch\(segment\)') {
    $issues += "SafeEditService secret matching should check the leaf filename, not every path segment, so ordinary names like tokenizer.py are allowed."
  }
  if ($safeEditText -match 'TimestampFromCreatedAt') {
    $issues += "SafeEditService rollback must not fall back from explicit backupId to createdAt-derived folders."
  }
  if ($safeEditText -notmatch 'manifest\.BackupId\?\.Trim\(\)' -or
      $safeEditText -notmatch 'IsSafeBackupId\(backupId\)' -or
      $safeEditText -notmatch 'Path\.Combine\(normalizedBase, backupId\)') {
    $issues += "SafeEditService rollback must resolve backup folders from the manifest backupId only."
  }

  if ($issues.Count -gt 0) {
    throw "Visual Studio rollback safety validation failed:`n - $($issues -join "`n - ")"
  }
}

function Assert-SolutionScannerParityGuards {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectDirectory
  )

  $scannerText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Services\SolutionScanner.cs")
  $intelligenceText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Services\SolutionIntelligenceService.cs")

  $issues = @()
  foreach ($suffix in @(".fsproj", ".vbproj", ".slnx", ".cc", ".cxx")) {
    if ($scannerText -notmatch [regex]::Escape($suffix)) {
      $issues += "SolutionScanner must recognize $suffix during solution context scans."
    }
  }
  foreach ($suffix in @(".fs", ".fsi", ".fsx", ".vb", ".fsproj", ".vbproj", ".slnx", ".cc", ".cxx", ".hxx")) {
    if ($intelligenceText -notmatch [regex]::Escape($suffix)) {
      $issues += "SolutionIntelligenceService must index $suffix for smart context parity."
    }
  }
  if ($scannerText -notmatch '"Visual Basic"' -or $scannerText -notmatch '"F#"') {
    $issues += "SolutionScanner must classify F# and Visual Basic project types."
  }
  if ($intelligenceText -notmatch 'AnalyzeFSharp' -or $intelligenceText -notmatch 'AnalyzeVisualBasic') {
    $issues += "SolutionIntelligenceService must keep F# and Visual Basic symbol analysis paths."
  }
  if ($intelligenceText -notmatch 'xaml \+ "\.vb"') {
    $issues += "SolutionIntelligenceService must preserve Visual Basic XAML code-behind relationships."
  }
  if ($scannerText -notmatch 'packages\.lock\.json') {
    $issues += "SolutionScanner must treat NuGet packages.lock.json as an important dependency metadata file."
  }
  if ($scannerText -match 'name\.Equals\("packages-lock\.json"') {
    $issues += "SolutionScanner must not use the invalid NuGet lockfile name packages-lock.json as a filename-only rule."
  }
  foreach ($secretNeedle in @("password", "passwd", "api[_-]?key", "auth", "id_rsa", "keystore", "crt", "cer")) {
    if ($scannerText -notmatch [regex]::Escape($secretNeedle)) {
      $issues += "SolutionScanner secret filename guard must include '$secretNeedle'."
    }
    if ($intelligenceText -notmatch [regex]::Escape($secretNeedle)) {
      $issues += "SolutionIntelligenceService secret filename guard must include '$secretNeedle'."
    }
  }
  foreach ($secretGuard in @(
    @{ Name = "SolutionScanner"; Text = $scannerText },
    @{ Name = "SolutionIntelligenceService"; Text = $intelligenceText }
  )) {
    $match = [regex]::Match($secretGuard.Text, 'SecretFilePattern\s*=\s*new Regex\(@"([^"]+)"')
    if (-not $match.Success) {
      $issues += "$($secretGuard.Name) must define a SecretFilePattern regex."
      continue
    }

    $pattern = [regex]::new($match.Groups[1].Value, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    foreach ($blockedFile in @(".env", ".env.example", "id_rsa", "service-token.json", "prod.password.txt", "private-key.pem", "client_api-key.json", "auth.json", "local.keystore", "client.crt")) {
      if (-not $pattern.IsMatch($blockedFile)) {
        $issues += "$($secretGuard.Name) must block secret-like file '$blockedFile'."
      }
    }
    foreach ($safeFile in @(".gitignore", "tokenizer.py", "authenticationService.cs", "privateer.cpp")) {
      if ($pattern.IsMatch($safeFile)) {
        $issues += "$($secretGuard.Name) must not over-block ordinary file '$safeFile'."
      }
    }
  }
  foreach ($unityFile in @("Packages/manifest.json", "Packages/packages-lock.json", ".asmdef", ".asmref")) {
    if ($scannerText -notmatch [regex]::Escape($unityFile)) {
      $issues += "SolutionScanner must keep Unity metadata visible in important solution context: $unityFile."
    }
    if ($intelligenceText -notmatch [regex]::Escape($unityFile)) {
      $issues += "SolutionIntelligenceService must classify Unity metadata as smart-context config: $unityFile."
    }
  }

  if ($issues.Count -gt 0) {
    throw "Visual Studio solution scanner parity validation failed:`n - $($issues -join "`n - ")"
  }
}

function Assert-CoreFirstRuntimeGuards {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectDirectory
  )

  $coreClientText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Services\AegisCoreClient.cs")
  $runtimeText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Services\AegisAgentRuntime.cs")
  $modelsText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "Models\AgentModels.cs")
  $toolWindowText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "ToolWindows\AegisToolWindowControl.xaml")
  $toolWindowCodeText = Get-Content -Raw -LiteralPath (Join-Path $ProjectDirectory "ToolWindows\AegisToolWindowControl.xaml.cs")

  $issues = @()
  foreach ($endpoint in @(
    "/v1/clients/sync",
    "/v1/workflows",
    "/v1/changes/propose",
    "/v1/changes/apply",
    "/v1/checkpoints",
    "/v1/checkpoints/restore",
    "/v1/validation/run",
    "/v1/workspaces/intelligence",
    "/v1/workspaces/roadmap"
  )) {
    if ($coreClientText -notmatch [regex]::Escape($endpoint)) {
      $issues += "AegisCoreClient must include Core endpoint $endpoint."
    }
  }

  foreach ($runtimeNeedle in @(
    "StartCoreWorkflowAsync",
    "RecordVisualStudioValidationWithCoreAsync",
    "core.ApplyProposalAsync",
    "core.RestoreCheckpointAsync",
    "core.WorkspaceIntelligenceAsync",
    "MarkCoreFallback"
  )) {
    if ($runtimeText -notmatch [regex]::Escape($runtimeNeedle)) {
      $issues += "AegisAgentRuntime must keep Core-first runtime hook '$runtimeNeedle'."
    }
  }

  foreach ($modelNeedle in @("CoreRuntimeState", "CoreWorkflowId", "CoreProposalId", "CoreCheckpointId")) {
    if ($modelsText -notmatch [regex]::Escape($modelNeedle)) {
      $issues += "Agent models must expose '$modelNeedle' for Core workflow tracking."
    }
  }

  if ($toolWindowText -notmatch "RuntimeStatusBox" -or $toolWindowCodeText -notmatch "SetRuntimeState") {
    $issues += "Visual Studio tool window must expose runtime authority status."
  }

  if ($issues.Count -gt 0) {
    throw "Visual Studio Core-first runtime validation failed:`n - $($issues -join "`n - ")"
  }
}

Assert-VisualStudioCommandTable `
  -VsctPath (Join-Path $projectDir "AegisLocalAgentPackage.vsct") `
  -CommandIdsPath (Join-Path $projectDir "CommandIds.cs") `
  -CommandRegistrationPath (Join-Path $projectDir "Commands\AegisCommands.cs")

Assert-DiagnosticRedactionGuards -ProjectDirectory $projectDir
Assert-UrlNormalizationGuards -ProjectDirectory $projectDir
Assert-SafeEditRollbackGuards -ProjectDirectory $projectDir
Assert-SolutionScannerParityGuards -ProjectDirectory $projectDir
Assert-CoreFirstRuntimeGuards -ProjectDirectory $projectDir
Assert-ReleaseDocumentationSources -Root $root -FileNames $releaseDocumentationFiles

if ($ValidateOnly) {
  Write-Host "Visual Studio package validation guards passed."
  return
}

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
  throw "dotnet was not found. Install the .NET SDK and Visual Studio 2022 Community with the Visual Studio extension development workload."
}

New-Item -ItemType Directory -Force -Path $release | Out-Null
$sourceOnlyReleaseFiles = @(
  "DOGFOODING_NOTES.md",
  "DETECTED_MODELS.md",
  ".gitignore"
)
foreach ($fileName in $sourceOnlyReleaseFiles) {
  $staleReleaseFile = Join-Path $release $fileName
  if (Test-Path -LiteralPath $staleReleaseFile) {
    Remove-Item -LiteralPath $staleReleaseFile -Force
  }
}
Invoke-MSBuild @($solution, "/t:Clean", "/p:Configuration=Release", "/p:DeployExtension=false")
Invoke-MSBuild @($solution, "/t:Restore", "/p:Configuration=Release")
Invoke-MSBuild @($solution, "/t:Build", "/p:Configuration=Release", "/p:DeployExtension=false")
Invoke-MSBuild @($project, "/t:GeneratePkgDef", "/p:Configuration=Release", "/p:DeployExtension=false")

$sourceManifest = Join-Path $projectDir "extension.vsixmanifest"
$objManifest = Join-Path $projectDir "obj\Release\extension.vsixmanifest"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $objManifest) | Out-Null
Copy-Item -LiteralPath $sourceManifest -Destination $objManifest -Force

Invoke-MSBuild @($project, "/t:CreateVsixContainer", "/p:Configuration=Release", "/p:DeployExtension=false")

$vsix = Get-ChildItem -Path (Join-Path $root "src\AegisLocalAgentVs\bin\Release") -Filter "*.vsix" -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $vsix) {
  throw "Build completed but no VSIX was found."
}

Copy-Item -LiteralPath $vsix.FullName -Destination (Join-Path $release "AegisLocalAgentVs.vsix") -Force
foreach ($fileName in $releaseDocumentationFiles) {
  Copy-Item -LiteralPath (Join-Path $root $fileName) -Destination (Join-Path $release $fileName) -Force
}

$projectText = Get-Content -Raw -LiteralPath $project
$expectedVersion = [regex]::Match($projectText, "<Version>([^<]+)</Version>").Groups[1].Value
$expectedMoreInfo = "https://github.com/MercyProductions/Aegis-AI"
Add-Type -AssemblyName System.IO.Compression.FileSystem

$assemblyPath = Join-Path $projectDir "bin\Release\AegisLocalAgentVs.dll"
$assembly = [Reflection.Assembly]::LoadFrom($assemblyPath)
$resourceStream = $assembly.GetManifestResourceStream("VSPackage.resources")
if (-not $resourceStream) {
  throw "AegisLocalAgentVs.dll is missing VSPackage.resources."
}

try {
  $resourceReader = [Resources.ResourceReader]::new($resourceStream)
  try {
    $hasMenuResource = $false
    foreach ($entry in $resourceReader) {
      if ($entry.Key -eq "Menus.ctmenu") {
        $hasMenuResource = $true
        break
      }
    }

    if (-not $hasMenuResource) {
      throw "AegisLocalAgentVs.dll is missing the Menus.ctmenu command resource."
    }
  } finally {
    $resourceReader.Dispose()
  }
} finally {
  $resourceStream.Dispose()
}

$releaseVsix = Join-Path $release "AegisLocalAgentVs.vsix"
$zip = [IO.Compression.ZipFile]::OpenRead($releaseVsix)
try {
  $entry = $zip.GetEntry("extension.vsixmanifest")
  if (-not $entry) {
    throw "VSIX package is missing extension.vsixmanifest."
  }

  $reader = [IO.StreamReader]::new($entry.Open())
  try {
    $manifestText = $reader.ReadToEnd()
  } finally {
    $reader.Dispose()
  }

  if ($manifestText -notmatch "Version=`"$([regex]::Escape($expectedVersion))`"") {
    throw "VSIX manifest version does not match project version $expectedVersion."
  }

  if ($manifestText -notmatch "<MoreInfo>$([regex]::Escape($expectedMoreInfo))</MoreInfo>") {
    throw "VSIX manifest MoreInfo must point to $expectedMoreInfo."
  }

  if ($manifestText -match "localhost") {
    throw "VSIX manifest contains a localhost placeholder URL."
  }

  foreach ($packageEntry in $zip.Entries) {
    if ($packageEntry.FullName -like "*DOGFOODING_NOTES.md") {
      throw "VSIX package must not include internal dogfooding notes."
    }
  }

  if ($manifestText -match "DETECTED_MODELS") {
    throw "VSIX manifest must not reference local detected model inventory."
  }

  foreach ($packageEntry in $zip.Entries) {
    if ($packageEntry.FullName -like "*DETECTED_MODELS.md") {
      throw "VSIX package must not include local detected model inventory."
    }
  }

  foreach ($packageEntry in $zip.Entries) {
    if ($packageEntry.FullName -like "*.gitignore") {
      throw "VSIX package must not include repository-only .gitignore files."
    }
  }

} finally {
  $zip.Dispose()
}

Write-Host "Packaged $($vsix.FullName)"
Write-Host "Copied to $(Join-Path $release 'AegisLocalAgentVs.vsix')"
