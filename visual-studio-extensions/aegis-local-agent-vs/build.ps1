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

New-Item -ItemType Directory -Force -Path $release | Out-Null
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
Copy-Item -LiteralPath (Join-Path $root "DOGFOODING_NOTES.md") -Destination (Join-Path $release "DOGFOODING_NOTES.md") -Force

$projectText = Get-Content -Raw -LiteralPath $project
$expectedVersion = [regex]::Match($projectText, "<Version>([^<]+)</Version>").Groups[1].Value
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
} finally {
  $zip.Dispose()
}

Write-Host "Packaged $($vsix.FullName)"
Write-Host "Copied to $(Join-Path $release 'AegisLocalAgentVs.vsix')"
