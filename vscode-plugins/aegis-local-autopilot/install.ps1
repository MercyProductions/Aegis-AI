$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm was not found. Install Node.js, then rerun this installer."
    }

    npm run install-local
    if ($LASTEXITCODE -ne 0) {
        throw "npm run install-local failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
