# watch-and-learn install script (Windows)
# Run: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

Write-Host "Installing watch-and-learn dependencies..."

# Python packages
pip install youtube-transcript-api yt-dlp imageio-ffmpeg pillow playwright vtracer fonttools ufolib2

# Playwright browser (for taste URL screenshots)
python -m playwright install chromium

# Copy ffmpeg binary to skill's bin/ for portability
$binDir = "$PSScriptRoot\bin"
New-Item -ItemType Directory -Force $binDir | Out-Null

try {
    $ffmpegSrc = python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" 2>$null
    if ($ffmpegSrc -and (Test-Path $ffmpegSrc)) {
        Copy-Item $ffmpegSrc "$binDir\ffmpeg.exe" -Force
        Write-Host "ffmpeg copied to $binDir\ffmpeg.exe"
    }
} catch {
    Write-Host "Note: imageio-ffmpeg not found, skipping ffmpeg copy. System ffmpeg will be used if available."
}

Write-Host ""
Write-Host "Done. Use the skill in Claude Code:"
Write-Host "  /watch-and-learn https://youtube.com/watch?v=..."
