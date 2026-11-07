param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^v\d+(\.\d+){1,3}$')]
    [string]$Tag
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$configPath = Join-Path $root 'updater_config.json'
$sourcePath = Join-Path $root 'AutoClicker.py'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Python ortamı bulunamadı. README.md içindeki hazırlık adımlarını tamamlayın.'
}

$source = Get-Content -LiteralPath $sourcePath -Raw -Encoding UTF8
$versionMatch = [regex]::Match($source, 'APP_VERSION\s*=\s*"([0-9]+(?:\.[0-9]+){1,3})"')
if (-not $versionMatch.Success) {
    throw 'AutoClicker.py içindeki APP_VERSION okunamadı.'
}
$versionTag = 'v' + $versionMatch.Groups[1].Value
if ($Tag -ne $versionTag) {
    throw "Etiket $Tag, kaynak sürümü $versionTag ile eşleşmiyor."
}

$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace([string]$config.owner) -or [string]::IsNullOrWhiteSpace([string]$config.repo)) {
    throw 'Önce updater_config.json içindeki owner ve repo alanlarını doldurun.'
}

$buildRoot = Join-Path $root (Join-Path 'build' $Tag)
$releaseRoot = Join-Path $root (Join-Path 'release' $Tag)
if (Test-Path -LiteralPath $buildRoot) {
    throw "Derleme klasörü zaten var; üzerine yazmamak için durdum: $buildRoot"
}
if (Test-Path -LiteralPath $releaseRoot) {
    throw "Sürüm klasörü zaten var; üzerine yazmamak için durdum: $releaseRoot"
}

$appDist = Join-Path $buildRoot 'app-dist'
$helperDist = Join-Path $buildRoot 'helper-dist'
$appWork = Join-Path $buildRoot 'app-work'
$helperWork = Join-Path $buildRoot 'helper-work'
$packageDir = Join-Path $buildRoot 'package'
$null = New-Item -ItemType Directory -Path $appDist, $helperDist, $appWork, $helperWork, $packageDir -Force

& $python -m PyInstaller --noconfirm --clean --workpath $appWork --distpath $appDist (Join-Path $root 'AutoClicker.spec')
if ($LASTEXITCODE -ne 0) { throw 'AutoClicker.exe derlenemedi.' }

& $python -m PyInstaller --noconfirm --clean --workpath $helperWork --distpath $helperDist (Join-Path $root 'AutoClickerUpdater.spec')
if ($LASTEXITCODE -ne 0) { throw 'AutoClickerUpdater.exe derlenemedi.' }

foreach ($fileName in @('AutoClicker.exe', 'AutoClickerUpdater.exe')) {
    $builtPath = if ($fileName -eq 'AutoClicker.exe') {
        Join-Path $appDist $fileName
    } else {
        Join-Path $helperDist $fileName
    }
    if (-not (Test-Path -LiteralPath $builtPath -PathType Leaf)) {
        throw "Derleme çıktısı bulunamadı: $builtPath"
    }
    Copy-Item -LiteralPath $builtPath -Destination $packageDir
}
Copy-Item -LiteralPath $configPath -Destination $packageDir

$null = New-Item -ItemType Directory -Path $releaseRoot -Force
$archivePath = Join-Path $releaseRoot 'AutoClicker-Windows.zip'
$checksumPath = Join-Path $releaseRoot 'SHA256SUMS.txt'
Compress-Archive -Path (Join-Path $packageDir '*') -DestinationPath $archivePath -CompressionLevel Optimal
$digest = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText($checksumPath, "$digest  AutoClicker-Windows.zip`r`n", [System.Text.Encoding]::ASCII)

Write-Host "Hazır: $releaseRoot"
Write-Host 'GitHub Release sayfasına AutoClicker-Windows.zip ve SHA256SUMS.txt dosyalarını ekleyin.'
