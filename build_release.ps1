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

# Publish the optional video decoder separately. The app fetches and caches it
# only when a user chooses a video, keeping the regular EXE download smaller.
$ffmpegSource = & $python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'
$ffmpegHash = (Get-FileHash -LiteralPath $ffmpegSource -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ffmpegHash -ne '3256173f3f8bffd7df12227c68adf68025edb1832273a9530688a7bb1ed8edec') { throw 'Video çözücüsü beklenen resmi dosya değil.' }
$runtimeDir = Join-Path $build 'video-runtime'
$null = New-Item -ItemType Directory -Path $runtimeDir -Force
Copy-Item -LiteralPath $ffmpegSource -Destination (Join-Path $runtimeDir 'ffmpeg.exe')
Copy-Item -LiteralPath (Join-Path $root 'FFmpeg-NOTICE.txt') -Destination $runtimeDir
$runtimeZip = Join-Path $release 'AutoClicker-VideoRuntime.zip'
Compress-Archive -Path (Join-Path $runtimeDir '*') -DestinationPath $runtimeZip -CompressionLevel Optimal

$digest = (Get-FileHash -LiteralPath (Join-Path $release 'AutoClicker.exe') -Algorithm SHA256).Hash.ToLowerInvariant()
$compatArchive = Join-Path $root 'release\v1.0.3\AutoClicker-Windows.zip'
if (Test-Path -LiteralPath $compatArchive -PathType Leaf) {
    Copy-Item -LiteralPath $compatArchive -Destination (Join-Path $release 'AutoClicker-Windows.zip')
    $compatDigest = (Get-FileHash -LiteralPath (Join-Path $release 'AutoClicker-Windows.zip') -Algorithm SHA256).Hash.ToLowerInvariant()
    [System.IO.File]::WriteAllText((Join-Path $release 'SHA256SUMS.txt'), "$compatDigest  AutoClicker-Windows.zip`r`n", [System.Text.Encoding]::ASCII)
} else {
    [System.IO.File]::WriteAllText((Join-Path $release 'SHA256SUMS.txt'), "$digest  AutoClicker.exe`r`n", [System.Text.Encoding]::ASCII)
}
Copy-Item -LiteralPath (Join-Path $root 'THIRD_PARTY_NOTICES.md') -Destination $release
Copy-Item -LiteralPath (Join-Path $root "RELEASE_NOTES_$Tag.md") -Destination (Join-Path $release 'Release-Notes.md')
Write-Host "Hazır: $release"
Write-Host 'Yeni kullanıcılar AutoClicker.exe dosyasını indirir. Video çözücüsü ilk video seçiminde onayla indirilir.'
