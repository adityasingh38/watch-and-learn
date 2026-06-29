#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract design taste from a URL or image file.
Usage: python extract_taste.py <url_or_image_path> [--label "optional label"]

Outputs:
- Screenshots saved to taste/references/
- Extracted colors printed to stdout
- Font hints printed to stdout
"""
import sys
import os
import re
import subprocess
import argparse
import shutil

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASTE_DIR = os.path.join(SKILL_DIR, 'taste')
REFS_DIR = os.path.join(TASTE_DIR, 'references')

def get_ffmpeg():
    local = r'C:\Users\Lenovo\.claude\bin\ffmpeg.exe'
    if os.path.exists(local):
        return local
    if shutil.which('ffmpeg'):
        return shutil.which('ffmpeg')
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None

def screenshot_url(url, label):
    """Take screenshot(s) of a URL using yt-dlp or requests+PIL."""
    screenshots = []

    # Try using Chrome MCP via subprocess isn't possible here.
    # Instead: download page HTML + use playwright if available, else requests.
    try:
        from playwright.sync_api import sync_playwright
        slug = re.sub(r'[^\w]', '_', label or url)[:40]
        out_path = os.path.join(REFS_DIR, f'{slug}_full.png')
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.screenshot(path=out_path, full_page=True)
            browser.close()
        screenshots.append(out_path)
        print(f"SCREENSHOT: {out_path}")
        return screenshots
    except ImportError:
        pass

    # Fallback: yt-dlp thumbnail if it's a video URL
    try:
        import yt_dlp
        slug = re.sub(r'[^\w]', '_', label or url)[:40]
        thumb_path = os.path.join(REFS_DIR, f'{slug}_thumb.jpg')
        ydl_opts = {
            'skip_download': True,
            'writethumbnail': True,
            'outtmpl': os.path.join(REFS_DIR, slug),
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        thumbs = [f for f in os.listdir(REFS_DIR) if f.startswith(slug) and f.endswith(('.jpg', '.png', '.webp'))]
        for t in thumbs:
            screenshots.append(os.path.join(REFS_DIR, t))
            print(f"SCREENSHOT: {os.path.join(REFS_DIR, t)}")
        return screenshots
    except Exception:
        pass

    print(f"NOTE: Could not auto-screenshot {url}. Claude will visit via browser MCP.", file=sys.stderr)
    print(f"URL_FOR_BROWSER: {url}")
    return []

def extract_colors_from_image(image_path):
    """Extract dominant colors from an image."""
    try:
        from PIL import Image
        import colorsys

        img = Image.open(image_path).convert('RGB')
        img = img.resize((200, 200))  # downsample for speed

        pixels = list(img.getdata())
        # Simple frequency count
        from collections import Counter
        counts = Counter(pixels)

        # Get top 20, filter near-whites and near-blacks, round to buckets
        def bucket(c, b=32):
            return tuple(round(x / b) * b for x in c)

        bucketed = Counter(bucket(p) for p in pixels)
        top = bucketed.most_common(30)

        colors = []
        for (r, g, b), count in top:
            # Skip very light (bg) and very dark unless prominent
            brightness = (r + g + b) / 3
            saturation = max(r, g, b) - min(r, g, b)
            if brightness > 240 and saturation < 20:
                continue
            hex_color = f'#{r:02X}{g:02X}{b:02X}'
            colors.append((hex_color, r, g, b, count))
            if len(colors) >= 8:
                break

        return colors
    except ImportError:
        return []

def process_local_image(path, label):
    """Process a local image file directly."""
    slug = re.sub(r'[^\w]', '_', label or os.path.basename(path))[:40]
    dest = os.path.join(REFS_DIR, slug + os.path.splitext(path)[1])
    shutil.copy2(path, dest)
    print(f"REFERENCE_SAVED: {dest}")
    return [dest]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', help='URL or local image/video path')
    parser.add_argument('--label', default=None, help='Human label for this reference')
    args = parser.parse_args()

    os.makedirs(REFS_DIR, exist_ok=True)

    source = args.source
    label = args.label or source

    print(f"=== TASTE EXTRACTION: {label} ===")

    # Get images to analyze
    images = []
    if source.startswith('http://') or source.startswith('https://'):
        images = screenshot_url(source, label)
    elif os.path.exists(source):
        ext = os.path.splitext(source)[1].lower()
        if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
            images = process_local_image(source, label)
        elif ext in ('.mp4', '.mov', '.avi', '.mkv', '.webm'):
            # Extract a few frames
            ffmpeg = get_ffmpeg()
            if ffmpeg:
                slug = re.sub(r'[^\w]', '_', label)[:40]
                frame_path = os.path.join(REFS_DIR, f'{slug}_frame_%02d.jpg')
                subprocess.run([
                    ffmpeg, '-i', source,
                    '-vf', 'fps=1/30,scale=1440:-2',
                    '-frames:v', '5',
                    frame_path, '-y', '-loglevel', 'error'
                ], check=False)
                import glob
                images = glob.glob(os.path.join(REFS_DIR, f'{slug}_frame_*.jpg'))
                for img in images:
                    print(f"REFERENCE_SAVED: {img}")
        else:
            print(f"ERROR: Unsupported file type: {ext}")
            sys.exit(1)
    else:
        print(f"ERROR: Not a valid URL or file path: {source}")
        sys.exit(1)

    # Extract colors from each image
    all_colors = []
    for img_path in images:
        colors = extract_colors_from_image(img_path)
        all_colors.extend(colors)

    if all_colors:
        print("\n=== EXTRACTED COLORS ===")
        seen = set()
        for hex_c, r, g, b, count in all_colors:
            if hex_c not in seen:
                seen.add(hex_c)
                print(f"COLOR: {hex_c}  rgb({r},{g},{b})")

    print("\n=== DONE ===")
    print(f"LABEL: {label}")
    print(f"IMAGES_SAVED: {len(images)}")
    print("Claude: read the saved images and update taste/TASTE.md with design observations.")

if __name__ == '__main__':
    main()
