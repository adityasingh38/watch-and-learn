# watch-and-learn

**A Claude Code skill that watches any video and does the work.**

Give it a YouTube link. It reads the transcript, extracts frames, identifies every tool used, checks if it's installed on your machine, and either walks you through the process step by step — or just does it for you.

---

## Demo

> Framer tutorial video → Claude extracts layout, colors, fonts → builds it as pixel-accurate HTML in one shot

<!-- Record with ScreenToGif or OBS: show video on left, Claude building HTML on right, ~60s -->
![demo](demo/demo.gif)

**Input:** `https://www.youtube.com/watch?v=fVe523ZrhYM`  
**Output:** Responsive HTML section — teal `#005B6E` hero, Inter 78px, orange `#FFA600` buttons — exact values read from video frames.

---

## What it does

```
you: /watch-and-learn https://youtube.com/watch?v=...

claude: Watched it. Tool: Framer (web app, no install needed).
        Video covers: building a responsive section with Stack layout,
        breakpoints at 810px (tablet) and 390px (phone).
        
        Key values from frames:
          Hero color: #005B6E
          Button color: #FFA600  
          Font: Inter Regular, 78px
          Button corner radius: 10px
          Stack gap: 10px
        
        Do you want to do this yourself, or should I do it for you?

you: you do it

claude: [writes pixel-accurate HTML/CSS matching the video exactly]
```

---

## Features

- **Full transcript + frame extraction** — reads what was said AND what was shown on screen
- **Timestamp-synced frames** — every frame paired with the transcript line spoken at that moment
- **Multi-site support** — YouTube, Vimeo, TikTok, Loom, Twitch, Instagram, Twitter/X, local files
- **Video caching** — second run on same video is instant (cached by video ID)
- **Tool detection** — checks if Figma, Blender, Photoshop, VS Code, etc. are installed
- **Auto-install** — runs `winget install` or gives exact download link for missing tools
- **Asks first** — "do it yourself or should I?" before executing anything
- **Smart execution order** — HTML/SVG first → API/CLI → browser MCP → computer use (always picks fastest)
- **Figma integration** — generates ready-to-run Figma plugin scripts from video design specs
- **Design taste system** — builds your aesthetic profile from references you feed it over time

---

## Installation

```bash
# Clone into your Claude skills directory
git clone https://github.com/adityasuper38/watch-and-learn ~/.claude/skills/watch-and-learn
cd ~/.claude/skills/watch-and-learn

# Windows
powershell -ExecutionPolicy Bypass -File install.ps1

# macOS / Linux
bash install.sh

# Optional: local video transcription (no subtitles)
pip install openai-whisper
```

That's it. No API keys needed for YouTube. No ffmpeg system install needed (bundled via imageio-ffmpeg).

---

## Usage

Load the skill in any Claude Code session:

```
/watch-and-learn https://www.youtube.com/watch?v=VIDEO_ID
```

Or with a local file:

```
/watch-and-learn /path/to/tutorial.mp4
```

### Commands

| Intent | What to say |
|--------|-------------|
| Watch and learn | `/watch-and-learn <url>` |
| Watch + do the work | `/watch-and-learn <url>` → answer "you do it" |
| Feed design reference | `taste this → <url or image>` |
| Check what Claude knows | `what did you learn from that video?` |

---

## Design Taste System

Claude builds your aesthetic profile incrementally from references you give it.

```
taste this → https://linear.app
taste this → https://stripe.com/payments
taste this → /path/to/screenshot.png
```

Each reference is analyzed for: color palette, typography, spacing rhythm, layout density, visual hierarchy. Findings accumulate in `taste/TASTE.md` and inform every design output.

**Shareable taste packs:** the `taste/` folder is self-contained. Zip it, share it, swap it.

```bash
# Use someone else's taste pack
rm -rf ~/.claude/skills/watch-and-learn/taste
unzip designer-taste-pack.zip -d ~/.claude/skills/watch-and-learn/taste
```

---

## How it works

```
Video URL
   │
   ├── youtube-transcript-api ──→ Full transcript + timestamps
   │
   ├── yt-dlp + ffmpeg ─────────→ Video frames
   │     ├── Scene changes (threshold 0.25)
   │     └── Baseline every 30s
   │
   └── Frame × Transcript sync ─→ [1:23] "set the fill to teal" + frame showing color picker at #005B6E
   
Claude reads everything → identifies tool → checks install → asks → executes
```

**Execution priority** (fastest to slowest):
1. Direct output — HTML, SVG, code, JSON (no external app)
2. CLI/API — Figma plugin script, `blender --python`, `ffmpeg`, etc.
3. Browser MCP — web apps (Framer, Canva, Figma web)
4. Computer use — native desktop apps with no API (Photoshop, Affinity)

---

## Supported tools

Figma · Framer · Canva · Adobe Photoshop · Illustrator · After Effects · Premiere · Affinity Designer · Blender · DaVinci Resolve · CapCut · VS Code · any web app · any CLI tool

---

## Figma integration

For Figma videos, generates a ready-to-paste plugin script:

```bash
python scripts/figma_api.py build-from-spec --spec design.json --out figma_script.js
```

Run in Figma: `Plugins → Development → Open console`, paste the output.

Or feed a design JSON spec directly:

```json
{
  "frames": [{"name": "Hero", "width": 1200, "height": 600, "fill": "#005B6E"}],
  "texts": [{"content": "Section", "x": 460, "y": 260, "size": 78, "color": "#FFFFFF", "font": "Inter"}],
  "rectangles": [{"name": "btn", "width": 200, "height": 50, "fill": "#FFA600", "radius": 10}]
}
```

---

## File structure

```
watch-and-learn/
├── SKILL.md                    # Claude's instructions (the skill brain)
├── README.md                   # This file
├── scripts/
│   ├── get_transcript.py       # Transcript + frame extraction (all sites)
│   ├── extract_taste.py        # Design reference analyzer
│   └── figma_api.py            # Figma plugin script generator
├── taste/
│   ├── TASTE.md                # Your synthesized aesthetic profile
│   ├── sources.md              # Reference log
│   ├── fonts.md                # Font catalog
│   ├── colors.md               # Color catalog
│   └── references/             # Saved screenshots
├── cache/                      # Video cache (by video ID)
└── demo/
    └── framer-section-demo.html
```

---

## Getting stars

If this saved you time, star it. If you have a taste pack worth sharing, PR it into `taste-packs/`.

---

## License

MIT
