---
name: watch-and-learn
description: >
  Watch a video and learn from it — both what was said AND what was shown on screen — then check if
  the required tool/software is installed, help install and set it up if not, and assist the user in
  doing exactly what the video showed, step by step.
  Trigger this skill whenever the user provides a YouTube URL or local video/audio file path and wants
  Claude to watch it, learn from it, follow a tutorial, replicate steps, understand a design process,
  or do any follow-up work based on video content.
  Also trigger for: "watch this", "learn from this video", "follow this tutorial", "do what the video shows",
  "replicate this", "help me do this", or any YouTube/youtu.be link with follow-up intent.
  Works for ANY tool — Figma, Framer, Photoshop, Affinity Designer, Illustrator, Blender, VS Code,
  DaVinci Resolve, CapCut, Canva, or anything else shown in a video.
---

# Watch and Learn

Full workflow: watch video → identify tools used → check if installed → help install/setup if needed → assist with the actual work.

---

## Step 1: Extract transcript + frames

Always extract both for tutorial/design videos. Use transcript-only only for pure Q&A requests.

Script: `C:\Users\Lenovo\.claude\skills\watch-and-learn\scripts\get_transcript.py`

```
python "C:\Users\Lenovo\.claude\skills\watch-and-learn\scripts\get_transcript.py" "<url_or_path>" --frames
```

Parse output for `FRAME_SYNCED:` lines — format is `FRAME_SYNCED: [M:SS] /path/to/frame.jpg | transcript text at that moment`. Read ALL frames as images in order sorted by timestamp.

---

## Step 2: Identify the primary tool(s)

From transcript + frames, identify:
- **Primary software** (e.g. Figma, Framer, Photoshop, Illustrator, Blender, DaVinci Resolve, VS Code, etc.)
- **Version** if visible (shown in title bar, about screen, or splash)
- **Plugins/extensions** used (mentioned or visible in UI)
- **File formats** involved (.fig, .psd, .ai, .blend, .svg, etc.)

---

## Step 3: Check if the tool is installed

Run detection checks appropriate to the tool. On Windows:

```powershell
# Generic check
where.exe <toolname> 2>$null
Get-Command <toolname> -ErrorAction SilentlyContinue

# Check common install paths
Test-Path "C:\Program Files\<AppName>"
Test-Path "$env:LOCALAPPDATA\<AppName>"
Test-Path "$env:APPDATA\<AppName>"

# Check registry (installed apps)
Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* |
  Where-Object DisplayName -like "*<AppName>*" | Select DisplayName, DisplayVersion
```

Common tool locations to check:
| Tool | Check |
|------|-------|
| Figma | `$env:LOCALAPPDATA\Figma\Figma.exe` or `where figma` |
| Adobe apps | `C:\Program Files\Adobe\*` |
| Affinity | `C:\Program Files\Affinity\*` |
| Blender | `where blender` or `C:\Program Files\Blender Foundation\*` |
| VS Code | `where code` or `$env:LOCALAPPDATA\Programs\Microsoft VS Code\Code.exe` |
| Framer | Web app (framer.com) — no install needed |
| Canva | Web app (canva.com) — no install needed |
| DaVinci Resolve | `C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe` |
| CapCut | `$env:LOCALAPPDATA\CapCut\Apps\*` |
| GIMP | `where gimp` or `C:\Program Files\GIMP 2\*` |
| Inkscape | `where inkscape` or `C:\Program Files\Inkscape\*` |

---

## Step 4: If tool NOT installed — help install it

Tell the user clearly: "The video uses [Tool X] which isn't installed. Here's how to get it."

Then provide installation help based on tool type:

**Free/open source tools** — give the exact winget command if available, otherwise direct download link:
```powershell
winget install --id <PackageId> -e
```
Common winget IDs: `Figma.Figma`, `BlenderFoundation.Blender`, `GIMP.GIMP`, `Inkscape.Inkscape`, `Microsoft.VisualStudioCode`

**Paid/subscription tools** (Adobe, Affinity) — give the official download page URL and explain any account/license requirements.

**Web-based tools** (Framer, Canva, Figma web) — open the URL, explain account setup if needed.

**After installation:** ask the user to confirm it's done, then continue to Step 5.

Also check for **required plugins/extensions** mentioned in the video. List them and explain how to install each within the tool.

---

## Step 5: Setup verification

Once tool is confirmed installed:
- Ask user to open it
- Verify the correct version (especially if video uses a specific version with different UI)
- Check any needed account login, workspace setup, or initial configuration shown in video
- If video used specific assets (fonts, brushes, templates) — identify and link them

---

## Step 6: Walk through the video content

Now guide the user through what the video demonstrated. Two modes:

**Step-by-step guide** — numbered list, each step referencing both what was said AND what was visible on screen. Include exact values: colors, sizes, tool settings, keyboard shortcuts.

**On-demand help** — answer specific questions as user works through it themselves. Reference specific frames when pointing to something visual ("at around 8:15, you can see the Stack panel showing Gap: 10...").

For design/creative work, extract every specific value you can see in frames:
- Exact hex colors from color pickers
- Font names and sizes from type panels
- Exact dimensions and positions
- Layer/Stack structure visible in layers panel
- Specific settings in properties panels

Don't approximate. If you can read `#005B6E` from a frame, use that exact value.

---

## Step 7: Ask the user — do it yourself or should I do it?

Before proceeding, ask: **"Do you want to do this yourself, or should I do it for you?"**

**If user wants to do it themselves** → Step-by-step instructions, click by click, precise enough to follow blindly. No guessing required.

**If user wants Claude to do it** → Execute using this priority order (fastest to slowest):

### Execution priority

**1. Direct output** *(fastest — no external app needed)*
Generate the result as code/files Claude can write directly:
- HTML + CSS for web layouts
- SVG for vector graphics and logos
- Python/JS/etc. for anything coded
- JSON/config files for tool imports
- Markdown, copy, structured content

**2. Tool API/CLI** *(fast — direct commands)*
If the tool has a programmatic interface, use it:
- Figma: REST API to create/update frames, components, styles
- VS Code: `code` CLI to open, install extensions
- Blender: Python scripting API (`blender --python script.py`)
- ffmpeg: CLI for video/audio work
- ImageMagick: CLI for image manipulation

**3. Browser MCP** *(medium — DOM-aware, no pixel-clicking)*
For web-based tools (Framer, Canva, Figma web, etc.):
- Use `mcp__Claude_in_Chrome__*` tools
- Navigate, click, fill forms via DOM — faster and more reliable than computer use

**4. Computer use** *(slowest — last resort only)*
Only when 1–3 are impossible (Photoshop, Affinity, native desktop apps with no API):
- Use `mcp__computer-use__*` tools
- Screenshot → analyze → click → repeat
- Warn user it will be slower

Always try option 1 first. A well-generated SVG or HTML file the user can import is faster than operating any GUI.

---

## Handling problems

**Tool is paid/requires license user doesn't have:** Suggest the best free alternative that can accomplish the same thing shown in the video. Explain what features differ.

**Tool is platform-incompatible** (e.g. macOS-only app on Windows): Suggest equivalent Windows alternative.

**No transcript + no captions:** Frames-only mode still works well for visual tutorials.

**Frames extraction fails** (private/region-blocked video): Offer transcript-only mode. Ask if user can share a local recording.

**Plugin/extension not available:** Note it, suggest workaround or manual approach.

---

---

## Design Taste System

Every design output is filtered through the user's taste profile before delivery.

### Reading taste before designing

Before generating any design output, read:
- `C:\Users\Lenovo\.claude\skills\watch-and-learn\taste\TASTE.md` — synthesized aesthetic principles
- `C:\Users\Lenovo\.claude\skills\watch-and-learn\taste\fonts.md` — approved fonts
- `C:\Users\Lenovo\.claude\skills\watch-and-learn\taste\colors.md` — approved colors

If TASTE.md says "Empty — no references yet", proceed without taste constraints but note it to the user.

### Feeding new taste references

Triggered by: "taste this → [url/screenshot/font]"

```
python "C:\Users\Lenovo\.claude\skills\watch-and-learn\scripts\extract_taste.py" "<url_or_file>" --label "optional label"
```

After running:
1. Parse `REFERENCE_SAVED:` lines → read each image
2. Parse `COLOR:` lines → add to `taste/colors.md`
3. Parse `URL_FOR_BROWSER:` → use browser MCP to visit and screenshot if script couldn't
4. Read all reference images carefully — analyze: color palette, typography choices, spacing/whitespace, layout grid, visual hierarchy, texture/depth, what's absent (restraint)
5. Update `taste/TASTE.md` — add timestamped observations under "Raw Observations", then synthesize into the relevant sections (Aesthetic Principles, Typography, Color, Layout)
6. Update `taste/sources.md` with the new entry

### What to extract from references

- **Colors**: dominant, accent, background, text colors — exact hex
- **Typography**: font families (check CSS or visible in UI), sizes, weights, line-height feel
- **Spacing**: generous or tight? consistent rhythm?
- **Shapes**: sharp corners vs rounded? borders? shadows?
- **Density**: minimal/airy vs rich/packed?
- **Mood**: words that describe the feeling — clinical, warm, playful, serious, premium
- **What's NOT there**: negative space philosophy, what they chose to omit

### Shareable taste packs

The `taste/` directory is self-contained. Users can:
- Replace it with someone else's taste pack
- Share their own as a zip
- Keep multiple taste profiles and swap between them

---

---

## Letterform & Wordmark Pipeline

For logo/wordmark work — tracing references, extracting style DNA, assembling from parts.

### Commands

```bash
# Raster image → clean vector SVG (better than Illustrator Live Trace)
python vectorize.py trace <image.png> --out logo.svg

# Extract typographic DNA: stroke weight, contrast ratio, terminal style
python vectorize.py analyze <image_or_svg> --out dna.json

# Pull individual glyphs out of a traced wordmark by position
python vectorize.py extract <traced.svg> --chars "AURA" --out glyphs/

# Package extracted glyph SVGs into .otf font
python vectorize.py font glyphs/ --name "MyFont" --out MyFont.otf

# Full pipeline: reference image → trace → analyze → extract → assemble wordmark
python vectorize.py wordmark <reference.png> --text "AURA" --out wordmark.svg
```

### Workflow when user shows a reference

1. Run `wordmark` command on the reference image
2. Read `DNA_SAVED:` output — stroke weight, contrast ratio, terminal style, notes
3. Read `FOUND:` vs `MISSING:` letter report
4. For found letters: compose SVG is ready, open it, describe what was extracted
5. For missing letters: use DNA values to generate matching SVG paths by hand
   - Stroke weight % of cap height → scale strokes accordingly
   - Contrast ratio → how much thinner diagonals/crossbars are vs verticals
   - Terminal style → flat/diagonal cuts (sans) vs ball/bracketed serifs
   - Match x-height, cap-height, overshoot from the extracted glyphs

### DNA output fields

| Field | Meaning |
|-------|---------|
| `stroke_weight_px` | Dominant stem width in pixels |
| `stroke_weight_pct` | Stem width as % of cap height (portable across sizes) |
| `contrast_ratio` | Thick:thin stroke ratio (1.0 = mono, 4+ = Didone) |
| `terminal_style` | `likely_serif` or `likely_sans` |
| `complexity_nodes` | Total bezier nodes (high = intricate, low = geometric) |

### Honest limits

- **Auto-trace** works well for clean logos on white bg. Noisy/textured references → use `filter_speckle` higher value
- **Glyph extraction** works for wordmarks with visible spacing between letters. Tight/overlapping kerning → extraction will group wrong paths
- **Font assembly** creates correct metrics/slots but SVG→outline conversion needs FontForge for final OTF outlines
- **Missing glyphs** — Claude generates SVG path approximations using DNA; always refine in Illustrator/Affinity

---

## Dependencies

Pre-installed:
- `youtube-transcript-api` — YouTube captions
- `yt-dlp` — video download + fallback subtitles
- `imageio-ffmpeg` — frame extraction (ffmpeg at `C:\Users\Lenovo\.claude\bin\ffmpeg.exe`)

Optional:
- `openai-whisper` — local video audio transcription (`pip install openai-whisper`)
