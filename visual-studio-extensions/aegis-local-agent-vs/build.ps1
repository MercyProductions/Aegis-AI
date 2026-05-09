$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$solution = Join-Path $root "AegisLocalAgentVs.sln"
$project = Join-Path $root "src\AegisLocalAgentVs\AegisLocalAgentVs.csproj"
$projectDir = Split-Path -Parent $project
$release = Join-Path $root "release"

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
  throw "dotnet was not found. Install the .NET SDK and Visual Studio 2022 Community with the Visual Studio extension development workload."
}

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
  if ($coreClientText -notmatch 'DiagnosticRedactor\.RedactAndTruncate\(apiVersion\)' -or $coreClientText -notmatch 'DiagnosticRedactor\.RedactAndTruncate\(kind\)') {
    $issues += "AegisCoreClient contract mismatch diagnostics must redact unexpected api_version and kind values."
  }

  if ($issues.Count -gt 0) {
    throw "Visual Studio diagnostic redaction validation failed:`n - $($issues -join "`n - ")"
  }
}

Assert-VisualStudioCommandTable `
  -VsctPath (Join-Path $projectDir "AegisLocalAgentPackage.vsct") `
  -CommandIdsPath (Join-Path $projectDir "CommandIds.cs") `
  -CommandRegistrationPath (Join-Path $projectDir "Commands\AegisCommands.cs")

Assert-DiagnosticRedactionGuards -ProjectDirectory $projectDir

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
Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination (Join-Path $release "README.md") -Force
Copy-Item -LiteralPath (Join-Path $root "INSTALL.md") -Destination (Join-Path $release "INSTALL.md") -Force
Copy-Item -LiteralPath (Join-Path $root "CHANGELOG.md") -Destination (Join-Path $release "CHANGELOG.md") -Force
Copy-Item -LiteralPath (Join-Path $root "RELEASE_NOTES.md") -Destination (Join-Path $release "RELEASE_NOTES.md") -Force
Copy-Item -LiteralPath (Join-Path $root "TROUBLESHOOTING.md") -Destination (Join-Path $release "TROUBLESHOOTING.md") -Force

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
