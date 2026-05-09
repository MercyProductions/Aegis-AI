$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
    npm run package
    $vsix = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot "release") -Filter "*.vsix" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $vsix) {
        throw "No VSIX package was created."
    }
    code --install-extension $vsix.FullName --force
    Write-Host "Installed $($vsix.Name) into VS Code."
}
finally {
    Pop-Location
}
