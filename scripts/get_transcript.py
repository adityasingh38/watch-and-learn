#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract transcript + time-synced frames from ANY video URL or local file.
Supports: YouTube, Vimeo, TikTok, Loom, Twitch, Instagram, Twitter/X, local files.
Caches results by video ID so repeat runs are instant.

Usage:
  python get_transcript.py <url_or_path>            # transcript only
  python get_transcript.py <url_or_path> --frames   # transcript + frames
  python get_transcript.py <url_or_path> --no-cache # bypass cache
"""

import sys, os, re, subprocess, tempfile, shutil, glob, json, hashlib, argparse
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

SKILL_DIR = Path(__file__).parent.parent
CACHE_DIR = SKILL_DIR / 'cache'

# ─── helpers ──────────────────────────────────────────────────────────────────

def get_ffmpeg():
    # 1. System ffmpeg
    if shutil.which('ffmpeg'):
        return shutil.which('ffmpeg')
    # 2. Skill-local bin (any platform)
    local_bin = SKILL_DIR / 'bin'
    for name in ('ffmpeg', 'ffmpeg.exe'):
        p = local_bin / name
        if p.exists():
            return str(p)
    # 3. imageio-ffmpeg bundled binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None

def video_cache_key(target):
    """Stable cache key: YouTube video ID or SHA1 of URL/path."""
    yt_match = re.search(r'(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})', target)
    if yt_match:
        return yt_match.group(1)
    if os.path.exists(target):
        return hashlib.sha1(Path(target).read_bytes()[:65536]).hexdigest()[:16]
    return hashlib.sha1(target.encode()).hexdigest()[:16]

def cache_path(key):
    return CACHE_DIR / key

def load_cache(key):
    p = cache_path(key)
    meta = p / 'meta.json'
    if meta.exists():
        return json.loads(meta.read_text(encoding='utf-8'))
    return None

def save_cache(key, data):
    p = cache_path(key)
    p.mkdir(parents=True, exist_ok=True)
    (p / 'meta.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def fmt_ts(seconds):
    s = int(seconds)
    return f"{s//60}:{s%60:02d}"

# ─── transcript ───────────────────────────────────────────────────────────────

def get_youtube_transcript(video_id):
    """YouTube captions via youtube-transcript-api. Returns list of {start, text}."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        tlist = api.list(video_id)
        t = None
        try:
            t = tlist.find_manually_created_transcript(['en','en-US','en-GB'])
        except Exception:
            try:
                t = tlist.find_generated_transcript(['en','en-US','en-GB'])
            except Exception:
                for x in tlist:
                    t = x
                    break
        if t and t.language_code not in ('en','en-US','en-GB'):
            try: t = t.translate('en')
            except: pass
        if t:
            segs = t.fetch()
            return [{'start': seg.start, 'text': seg.text} for seg in segs]
    except Exception as e:
        print(f"youtube-transcript-api: {e}", file=sys.stderr)
    return None

def get_yt_dlp_subtitles(url):
    """yt-dlp subtitle download for any site. Returns list of {start, text}."""
    import yt_dlp
    with tempfile.TemporaryDirectory() as tmp:
        opts = {
            'skip_download': True,
            'writeautomaticsub': True, 'writesubtitles': True,
            'subtitleslangs': ['en','en-US'],
            'subtitlesformat': 'vtt',
            'outtmpl': os.path.join(tmp, 'video'),
            'quiet': True, 'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        vtts = glob.glob(os.path.join(tmp, '*.vtt'))
        if not vtts:
            return None
        return parse_vtt(open(vtts[0], encoding='utf-8').read())

def parse_vtt(vtt):
    segs, seen = [], []
    lines = vtt.split('\n')
    for i, line in enumerate(lines):
        if '-->' not in line: continue
        start_str = line.split('-->')[0].strip()
        start_sec = vtt_time_to_sec(start_str)
        for j in range(i+1, min(i+5, len(lines))):
            text = re.sub(r'<[^>]+>','', lines[j].strip())
            text = text.replace('&amp;','&').replace('&lt;','<').replace('&gt;','>')
            if text and text not in seen[-3:]:
                segs.append({'start': start_sec, 'text': text})
                seen = (seen + [text])[-5:]
                break
    return segs or None

def vtt_time_to_sec(ts):
    ts = ts.strip()
    parts = ts.replace(',','.').split(':')
    try:
        if len(parts) == 3:
            return int(parts[0])*3600 + int(parts[1])*60 + float(parts[2])
        return int(parts[0])*60 + float(parts[1])
    except:
        return 0.0

def get_whisper_transcript(path):
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(path)
        return [{'start': seg['start'], 'text': seg['text'].strip()} for seg in result.get('segments',[])]
    except ImportError:
        return None

def segs_to_text(segs):
    return ' '.join(s['text'] for s in segs)

def segs_to_timestamped(segs):
    return '\n'.join(f"[{fmt_ts(s['start'])}] {s['text']}" for s in segs)

# ─── video download ───────────────────────────────────────────────────────────

def download_video(url, out_dir):
    import yt_dlp
    ffmpeg = get_ffmpeg()
    ffmpeg_dir = os.path.dirname(ffmpeg) if ffmpeg else None
    opts = {
        'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[height<=720]',
        'outtmpl': os.path.join(out_dir, 'video.%(ext)s'),
        'merge_output_format': 'mp4',
        'quiet': False, 'no_warnings': True,
    }
    if ffmpeg_dir:
        opts['ffmpeg_location'] = ffmpeg_dir
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        duration = info.get('duration', 0)
        title = info.get('title', '')
    videos = glob.glob(os.path.join(out_dir, 'video.*'))
    if not videos:
        raise RuntimeError("Download failed")
    return videos[0], duration, title

# ─── frame extraction with timestamps ────────────────────────────────────────

def extract_frames_synced(video_path, frames_dir, transcript_segs):
    """
    Extract frames at scene changes + every 30s baseline.
    Each frame gets a timestamp. Match frames to nearest transcript segment.
    Returns list of {timestamp_sec, timestamp_str, frame_path, transcript_at_time}.
    """
    ffmpeg = get_ffmpeg()
    if not ffmpeg:
        return [], "ffmpeg not available"

    os.makedirs(frames_dir, exist_ok=True)

    # 1. Scene-change frames — capture PTS alongside each frame
    #    showinfo filter prints pts_time to stderr; we parse it to get real timestamps
    scene_dir = os.path.join(frames_dir, '_scene')
    os.makedirs(scene_dir, exist_ok=True)
    scene_proc = subprocess.run([
        ffmpeg, '-i', video_path,
        '-vf', "select=gt(scene\\,0.25),showinfo,scale=1280:-2",
        '-vsync', 'vfr',
        os.path.join(scene_dir, 'frame_%06d.jpg'),
        '-y', '-loglevel', 'info'
    ], capture_output=True, text=True, errors='replace')
    # Parse real PTS from showinfo output: "pts_time:12.345"
    scene_pts = [float(m) for m in re.findall(r'pts_time:([\d.]+)', scene_proc.stderr)]

    # 2. Baseline frames every 30s — timestamps are exact multiples of 30
    base_dir = os.path.join(frames_dir, '_base')
    os.makedirs(base_dir, exist_ok=True)
    subprocess.run([
        ffmpeg, '-i', video_path,
        '-vf', 'fps=1/30,scale=1280:-2',
        os.path.join(base_dir, 'frame_%04d.jpg'),
        '-y', '-loglevel', 'error'
    ], check=False)

    # 4. Assign timestamps to frames
    scene_frames = sorted(glob.glob(os.path.join(scene_dir, '*.jpg')))
    base_frames  = sorted(glob.glob(os.path.join(base_dir,  '*.jpg')))

    results = []

    for i, f in enumerate(base_frames):
        ts = i * 30.0
        ts_str = fmt_ts(ts)
        dest = os.path.join(frames_dir, f'base_{i:04d}.jpg')
        shutil.copy2(f, dest)
        near_seg = nearest_segment(ts, transcript_segs)
        results.append({'ts': ts, 'ts_str': ts_str, 'path': dest,
                        'transcript': near_seg, 'type': 'base'})

    for i, f in enumerate(scene_frames):
        # Use real PTS if available, else fall back to frame index heuristic
        if i < len(scene_pts):
            ts = scene_pts[i]
        else:
            ts = i * 5.0  # rough fallback: assume scene every ~5s
        ts_str = fmt_ts(ts)
        dest = os.path.join(frames_dir, f'scene_{i:04d}.jpg')
        shutil.copy2(f, dest)
        near_seg = nearest_segment(ts, transcript_segs)
        results.append({'ts': ts, 'ts_str': ts_str, 'path': dest,
                        'transcript': near_seg, 'type': 'scene'})

    # Cleanup temp dirs
    shutil.rmtree(scene_dir, ignore_errors=True)
    shutil.rmtree(base_dir,  ignore_errors=True)

    # Sort by timestamp, cap at 200
    results.sort(key=lambda x: x['ts'])
    if len(results) > 200:
        step = len(results) // 200
        results = results[::step][:200]

    return results, None

def nearest_segment(ts, segs):
    """Find transcript text closest to timestamp ts."""
    if not segs:
        return ''
    best = min(segs, key=lambda s: abs(s['start'] - ts))
    return best['text']

# ─── caching helpers ──────────────────────────────────────────────────────────

def save_frames_to_cache(cache_dir, frame_results):
    frames_cache = cache_dir / 'frames'
    frames_cache.mkdir(exist_ok=True)
    frame_meta = []
    for fr in frame_results:
        fname = Path(fr['path']).name
        dest = frames_cache / fname
        shutil.copy2(fr['path'], dest)
        frame_meta.append({
            'ts': fr['ts'], 'ts_str': fr['ts_str'],
            'path': str(dest), 'transcript': fr['transcript'], 'type': fr['type']
        })
    return frame_meta

# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('target', help='Video URL or local file path')
    parser.add_argument('--frames', action='store_true', help='Extract frames')
    parser.add_argument('--no-cache', action='store_true', help='Bypass cache')
    args = parser.parse_args()

    target = args.target
    want_frames = args.frames
    use_cache = not args.no_cache

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = video_cache_key(target)
    cached = load_cache(key) if use_cache else None

    if cached and (not want_frames or cached.get('frames')):
        print("=== CACHED ===")
        print("=== FULL TRANSCRIPT ===")
        print(cached['full_text'])
        print("\n=== TIMESTAMPED ===")
        print(cached['timestamped'])
        if want_frames and cached.get('frames'):
            print(f"\n=== FRAMES ({len(cached['frames'])} total, from cache) ===")
            for fr in cached['frames']:
                print(f"FRAME_SYNCED: [{fr['ts_str']}] {fr['path']} | {fr['transcript']}")
        return

    # ── get transcript segments ──
    segs = None
    is_url = target.startswith('http://') or target.startswith('https://')

    if is_url:
        yt_id = re.search(r'(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})', target)
        if yt_id:
            segs = get_youtube_transcript(yt_id.group(1))
        if not segs:
            segs = get_yt_dlp_subtitles(target)
    elif os.path.exists(target):
        segs = get_whisper_transcript(target)
        if segs is None:
            print("ERROR: openai-whisper not installed. Run: pip install openai-whisper")
            sys.exit(1)
    else:
        print(f"ERROR: Not a valid URL or path: {target}")
        sys.exit(1)

    if not segs:
        segs = []
        print("WARNING: No transcript found for this video.", file=sys.stderr)

    full_text   = segs_to_text(segs)
    timestamped = segs_to_timestamped(segs)

    print("=== FULL TRANSCRIPT ===")
    print(full_text)
    print("\n=== TIMESTAMPED ===")
    print(timestamped)

    # ── extract frames ──
    frame_results = []
    if want_frames:
        print("\n=== EXTRACTING FRAMES ===")
        tmp_video_dir = None
        video_path = target

        if is_url:
            print("Downloading video...")
            tmp_video_dir = tempfile.mkdtemp(prefix='wl_video_')
            video_path, duration, title = download_video(target, tmp_video_dir)
            print(f"Downloaded: {video_path}")

        frames_dir = tempfile.mkdtemp(prefix='wl_frames_')
        frame_results, err = extract_frames_synced(video_path, frames_dir, segs)

        if tmp_video_dir:
            shutil.rmtree(tmp_video_dir, ignore_errors=True)

        if err:
            print(f"Frame error: {err}")
        else:
            print(f"\n=== FRAMES ({len(frame_results)} total) ===")
            for fr in frame_results:
                print(f"FRAME_SYNCED: [{fr['ts_str']}] {fr['path']} | {fr['transcript']}")

    # ── cache ──
    if use_cache:
        c = cache_path(key)
        c.mkdir(parents=True, exist_ok=True)
        frame_meta = save_frames_to_cache(c, frame_results) if frame_results else []
        save_cache(key, {
            'full_text': full_text,
            'timestamped': timestamped,
            'segments': segs,
            'frames': frame_meta,
        })
        print(f"\nCACHED: {key}")

if __name__ == '__main__':
    main()
