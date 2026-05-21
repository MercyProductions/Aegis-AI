param(
  [switch]$SkipBuild,
  [string]$OutputDir = "release"
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptRoot
$RootFull = [System.IO.Path]::GetFullPath($Root)
$OutputRoot = Join-Path $RootFull $OutputDir
$StageRoot = Join-Path $RootFull ".tmp\release-staging"
$ManifestPath = Join-Path $RootFull "VERSION.json"

function Assert-UnderRoot {
  param([string]$Path)
  $full = [System.IO.Path]::GetFullPath($Path)
  $rootWithSlash = $RootFull.TrimEnd("\") + "\"
  if (-not $full.Equals($RootFull, [System.StringComparison]::OrdinalIgnoreCase) -and
      -not $full.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to operate outside workspace root: $full"
  }
  return $full
}

function Reset-Directory {
  param([string]$Path)
  $full = Assert-UnderRoot $Path
  if (Test-Path -LiteralPath $full) {
    Remove-Item -LiteralPath $full -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $full | Out-Null
  return $full
}

function Ensure-Directory {
  param([string]$Path)
  $full = Assert-UnderRoot $Path
  New-Item -ItemType Directory -Force -Path $full | Out-Null
  return $full
}

function Copy-ExistingPath {
  param([string]$Source, [string]$Destination)
  if (Test-Path -LiteralPath $Source) {
    $parent = Split-Path -Parent $Destination
    Ensure-Directory $parent | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
  }
}

function Compress-Staging {
  param([string]$Stage, [string]$Destination)
  if (Test-Path -LiteralPath $Destination) {
    Remove-Item -LiteralPath (Assert-UnderRoot $Destination) -Force
  }
  $children = @(Get-ChildItem -LiteralPath $Stage -Force)
  if ($children.Count -eq 0) {
    throw "No files staged for package $Destination"
  }
  Compress-Archive -LiteralPath ($children | ForEach-Object { $_.FullName }) -DestinationPath $Destination -Force
  return Get-Item -LiteralPath $Destination
}

function Get-Component {
  param([object]$Manifest, [string]$ComponentId)
  $property = $Manifest.components.PSObject.Properties[$ComponentId]
  if ($null -eq $property) {
    throw "VERSION.json does not define component '$ComponentId'."
  }
  return $property.Value
}

function Update-PackageMetadata {
  param([object]$Manifest, [string]$ComponentId, [string]$ArtifactPath)
  $component = Get-Component $Manifest $ComponentId
  $item = Get-Item -LiteralPath $ArtifactPath
  $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $item.FullName
  $rootUri = New-Object System.Uri (($RootFull.TrimEnd("\") + "\"))
  $itemUri = New-Object System.Uri $item.FullName
  $relative = [System.Uri]::UnescapeDataString($rootUri.MakeRelativeUri($itemUri).ToString())
  $component.package.artifact = $item.Name
  $component.package.path = $relative
  $component.package.sha256 = $hash.Hash.ToLowerInvariant()
  $component.package.size_bytes = $item.Length
}

function Invoke-ReleaseBuilds {
  Write-Host "Running release builds..."
  & (Join-Path $RootFull "build.ps1")
  if (Test-Path -LiteralPath (Join-Path $RootFull "website\frontend\package.json")) {
    npm --prefix (Join-Path $RootFull "website\frontend") run build
  }
  if (Test-Path -LiteralPath (Join-Path $RootFull "vscode-plugins\aegis-local-autopilot\scripts\package-release.js")) {
    node (Join-Path $RootFull "vscode-plugins\aegis-local-autopilot\scripts\package-release.js")
  }
  if (Test-Path -LiteralPath (Join-Path $RootFull "visual-studio-extensions\aegis-local-agent-vs\build.ps1")) {
    & (Join-Path $RootFull "visual-studio-extensions\aegis-local-agent-vs\build.ps1")
  }
}

if (-not (Test-Path -LiteralPath $ManifestPath)) {
  throw "VERSION.json is required before packaging."
}

if (-not $SkipBuild) {
  Invoke-ReleaseBuilds
}

Ensure-Directory $OutputRoot | Out-Null
Reset-Directory $StageRoot | Out-Null
$Manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
$Manifest.generated_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

$CoreStage = Reset-Directory (Join-Path $StageRoot "aegis-core")
Copy-ExistingPath (Join-Path $RootFull "aegis-core\aegis_core") (Join-Path $CoreStage "aegis_core")
Copy-ExistingPath (Join-Path $RootFull "aegis-core\pyproject.toml") (Join-Path $CoreStage "pyproject.toml")
Copy-ExistingPath (Join-Path $RootFull "aegis-core\README.md") (Join-Path $CoreStage "README.md")
Copy-ExistingPath (Join-Path $RootFull "aegis-core\docs") (Join-Path $CoreStage "docs")
Copy-ExistingPath $ManifestPath (Join-Path $CoreStage "VERSION.json")
$CorePackage = Compress-Staging $CoreStage (Join-Path $OutputRoot "aegis-core-$((Get-Component $Manifest 'aegis-core').version).zip")
Update-PackageMetadata $Manifest "aegis-core" $CorePackage.FullName

$WebsiteStage = Reset-Directory (Join-Path $StageRoot "website")
Copy-ExistingPath (Join-Path $RootFull "website\backend") (Join-Path $WebsiteStage "backend")
Copy-ExistingPath (Join-Path $RootFull "website\frontend\dist") (Join-Path $WebsiteStage "frontend\dist")
Copy-ExistingPath (Join-Path $RootFull "website\frontend\package.json") (Join-Path $WebsiteStage "frontend\package.json")
Copy-ExistingPath (Join-Path $RootFull "website\README.md") (Join-Path $WebsiteStage "README.md")
Copy-ExistingPath (Join-Path $RootFull "WEBSITE_CORE_ADAPTER.md") (Join-Path $WebsiteStage "WEBSITE_CORE_ADAPTER.md")
Copy-ExistingPath $ManifestPath (Join-Path $WebsiteStage "VERSION.json")
$WebsitePackage = Compress-Staging $WebsiteStage (Join-Path $OutputRoot "aegis-website-$((Get-Component $Manifest 'website').version).zip")
Update-PackageMetadata $Manifest "website" $WebsitePackage.FullName

$DesktopStage = Reset-Directory (Join-Path $StageRoot "desktop")
Copy-ExistingPath (Join-Path $RootFull "x64\Release\AegisChatBotDesktop.exe") (Join-Path $DesktopStage "AegisChatBotDesktop.exe")
Copy-ExistingPath (Join-Path $RootFull "AegisChatBot.config.ini") (Join-Path $DesktopStage "AegisChatBot.config.ini")
Copy-ExistingPath (Join-Path $RootFull "README.md") (Join-Path $DesktopStage "README.md")
Copy-ExistingPath (Join-Path $RootFull "INSTALL.md") (Join-Path $DesktopStage "INSTALL.md")
Copy-ExistingPath (Join-Path $RootFull "docs\RELEASE_PACKAGING_AND_UPDATES.md") (Join-Path $DesktopStage "RELEASE_PACKAGING_AND_UPDATES.md")
$DesktopPackage = Compress-Staging $DesktopStage (Join-Path $OutputRoot "aegis-desktop-$((Get-Component $Manifest 'desktop').version)-portable.zip")
Update-PackageMetadata $Manifest "desktop" $DesktopPackage.FullName

$VsCodeComponent = Get-Component $Manifest "vscode-extension"
$VsCodeSource = Join-Path $RootFull ("vscode-plugins\aegis-local-autopilot\release\" + $VsCodeComponent.package.artifact)
if (-not (Test-Path -LiteralPath $VsCodeSource)) {
  $VsCodeSource = Join-Path $RootFull ("vscode-plugins\aegis-local-autopilot\" + $VsCodeComponent.package.artifact)
}
if (Test-Path -LiteralPath $VsCodeSource) {
  $VsCodePackage = Join-Path $OutputRoot $VsCodeComponent.package.artifact
  Copy-Item -LiteralPath $VsCodeSource -Destination $VsCodePackage -Force
  Update-PackageMetadata $Manifest "vscode-extension" $VsCodePackage
} else {
  Write-Warning "VS Code VSIX was not found; run package-release.js to create it."
}

$VsComponent = Get-Component $Manifest "visual-studio-extension"
$VsSource = Join-Path $RootFull ("visual-studio-extensions\aegis-local-agent-vs\release\" + $VsComponent.package.artifact)
if (Test-Path -LiteralPath $VsSource) {
  $VsPackage = Join-Path $OutputRoot $VsComponent.package.artifact
  Copy-Item -LiteralPath $VsSource -Destination $VsPackage -Force
  Update-PackageMetadata $Manifest "visual-studio-extension" $VsPackage
} else {
  Write-Warning "Visual Studio VSIX was not found; run the Visual Studio extension build script to create it."
}

$GeneratedManifest = Join-Path $OutputRoot "version-manifest.json"
$Manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $GeneratedManifest -Encoding UTF8
Copy-ExistingPath (Join-Path $RootFull "scripts\aegis-update.ps1") (Join-Path $OutputRoot "aegis-update.ps1")
Copy-ExistingPath (Join-Path $RootFull "scripts\build-release.ps1") (Join-Path $OutputRoot "build-release.ps1")

Write-Host "Release packages written to $OutputRoot"
Get-ChildItem -LiteralPath $OutputRoot -File | Select-Object Name, Length, LastWriteTime
