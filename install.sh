#!/bin/bash
# watch-and-learn install script (macOS/Linux)
set -e

echo "Installing watch-and-learn dependencies..."

pip install youtube-transcript-api yt-dlp imageio-ffmpeg pillow playwright vtracer fonttools ufolib2
python -m playwright install chromium

# Copy ffmpeg binary to skill's bin/ for portability
BIN_DIR="$(dirname "$0")/bin"
mkdir -p "$BIN_DIR"

FFMPEG_SRC=$(python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null || true)
if [ -n "$FFMPEG_SRC" ] && [ -f "$FFMPEG_SRC" ]; then
    cp "$FFMPEG_SRC" "$BIN_DIR/ffmpeg"
    chmod +x "$BIN_DIR/ffmpeg"
    echo "ffmpeg copied to $BIN_DIR/ffmpeg"
fi

echo ""
echo "Done. Use the skill in Claude Code:"
echo "  /watch-and-learn https://youtube.com/watch?v=..."
