param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^v\d+(\.\d+){1,3}$')]
    [string]$Tag
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$sourcePath = Join-Path $root 'AutoClicker.py'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Önce README içindeki Python ortamı hazırlığını tamamlayın.' }
$source = Get-Content -LiteralPath $sourcePath -Raw -Encoding UTF8
$match = [regex]::Match($source, 'APP_VERSION\s*=\s*"([0-9]+(?:\.[0-9]+){1,3})"')
if (-not $match.Success -or $Tag -ne ('v' + $match.Groups[1].Value)) { throw 'Etiket, AutoClicker.py içindeki APP_VERSION ile aynı olmalı.' }

$release = Join-Path $root (Join-Path 'release' $Tag)
$build = Join-Path $root (Join-Path 'build' $Tag)
if ((Test-Path -LiteralPath $release) -or (Test-Path -LiteralPath $build)) { throw 'Bu sürümün derleme veya yayın klasörü zaten var; üzerine yazmadım.' }
$null = New-Item -ItemType Directory -Path $release, $build -Force
$dist = Join-Path $build 'dist'
$work = Join-Path $build 'work'

& $python -m PyInstaller --noconfirm --clean --workpath $work --distpath $dist (Join-Path $root 'AutoClicker.spec')
if ($LASTEXITCODE -ne 0) { throw 'AutoClicker.exe derlenemedi.' }
$exe = Join-Path $dist 'AutoClicker.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'AutoClicker.exe derleme çıktısı bulunamadı.' }
Copy-Item -LiteralPath $exe -Destination (Join-Path $release 'AutoClicker.exe')

$digest = (Get-FileHash -LiteralPath (Join-Path $release 'AutoClicker.exe') -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText((Join-Path $release 'SHA256SUMS.txt'), "$digest  AutoClicker.exe`r`n", [System.Text.Encoding]::ASCII)
Copy-Item -LiteralPath (Join-Path $root "RELEASE_NOTES_$Tag.md") -Destination (Join-Path $release 'Release-Notes.md')
Write-Host "Hazır: $release"
Write-Host 'GitHub sürümüne yalnızca AutoClicker.exe dosyasını ekleyin. Video desteği EXE içine dahildir.'
