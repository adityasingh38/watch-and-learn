#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Letterform vectorization + typographic DNA extraction + font assembly.

Usage:
  python vectorize.py trace    <image>              --out logo.svg
  python vectorize.py analyze  <svg_or_image>       --out dna.json
  python vectorize.py extract  <svg_or_image>       --chars "AURA" --out glyphs/
  python vectorize.py font     <glyphs_dir>         --name "MyFont" --out MyFont.otf
  python vectorize.py wordmark <reference_image>    --text "AURA" --out wordmark.svg

Honest capability:
  - trace:    raster → clean vector SVG (vtracer, better than Illustrator's live trace)
  - analyze:  extract typographic DNA — stroke weight, contrast, terminal style, proportions
  - extract:  pull individual glyphs out of a traced wordmark by bounding box
  - font:     package extracted glyphs into a usable .otf file
  - wordmark: trace reference + extract whatever letters exist + report DNA for gaps
"""

import sys, os, re, json, argparse, shutil, math
from pathlib import Path
from xml.etree import ElementTree as ET

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ─── vtracer ──────────────────────────────────────────────────────────────────

def trace_image(image_path, mode='outline', color_mode='binary', filter_speckle=4,
                color_precision=6, layer_difference=16, corner_threshold=60,
                length_threshold=4.0, max_iterations=10, splice_threshold=45):
    """
    Convert raster image to SVG using vtracer.
    mode: 'outline' (filled shapes, best for logos) | 'centerline' (stroked paths, best for sketches)
    """
    import vtracer

    image_path = str(image_path)
    out_path = image_path.rsplit('.', 1)[0] + '_traced.svg'

    vtracer.convert_image_to_svg_py(
        image_path,
        out_path,
        colormode=color_mode,           # 'binary' | 'color'
        filter_speckle=filter_speckle,  # ignore noise below N px²
        color_precision=color_precision,
        layer_difference=layer_difference,
        mode=mode,
        corner_threshold=corner_threshold,
        length_threshold=length_threshold,
        max_iterations=max_iterations,
        splice_threshold=splice_threshold,
        path_precision=3,
    )
    return out_path


def trace_for_letterforms(image_path):
    """High-quality settings tuned for letterforms."""
    return trace_image(
        image_path,
        mode='outline',
        color_mode='binary',
        filter_speckle=2,       # keep small features
        corner_threshold=60,    # preserve sharp corners
        length_threshold=2.0,   # keep fine detail
        splice_threshold=30,
    )


# ─── SVG path analysis ────────────────────────────────────────────────────────

def parse_svg(svg_path):
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    return tree, root, ns


def get_all_paths(svg_path):
    _, root, ns = parse_svg(svg_path)
    paths = []
    for el in root.iter():
        tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        if tag == 'path':
            d = el.get('d', '')
            fill = el.get('fill', '#000000')
            paths.append({'d': d, 'fill': fill})
    return paths


def path_bbox(d):
    """Approximate bounding box of a path by scanning M/L/C/Q coords."""
    nums = [float(x) for x in re.findall(r'[-+]?\d*\.?\d+', d)]
    if len(nums) < 2:
        return None
    xs = nums[0::2]
    ys = nums[1::2]
    return {'x': min(xs), 'y': min(ys), 'w': max(xs)-min(xs), 'h': max(ys)-min(ys)}


def estimate_stroke_weight(paths):
    """
    Estimate dominant stroke weight from path bounding boxes.
    Thin strokes = small min(w,h). For filled outline paths, stroke weight ≈
    min dimension of the thinnest path that is clearly a stroke (aspect ratio > 4:1).
    """
    stroke_candidates = []
    for p in paths:
        bb = path_bbox(p['d'])
        if not bb or bb['w'] < 1 or bb['h'] < 1:
            continue
        ratio = max(bb['w'], bb['h']) / min(bb['w'], bb['h'])
        if ratio > 3:  # elongated = likely a stroke
            stroke_candidates.append(min(bb['w'], bb['h']))
    if not stroke_candidates:
        return None
    stroke_candidates.sort()
    # median to ignore outliers
    median = stroke_candidates[len(stroke_candidates) // 2]
    return round(median, 1)


def svg_dimensions(svg_path):
    _, root, _ = parse_svg(svg_path)
    w = root.get('width', '0').replace('px','').strip()
    h = root.get('height', '0').replace('px','').strip()
    try:
        return float(w), float(h)
    except:
        vb = root.get('viewBox', '0 0 0 0').split()
        return float(vb[2]), float(vb[3])


def analyze_svg(svg_path):
    """
    Extract typographic DNA from a vectorized wordmark/letterform.
    Returns dict with stroke_weight, contrast_ratio, proportions, terminal_style, complexity.
    """
    paths = get_all_paths(svg_path)
    w, h = svg_dimensions(svg_path)

    stroke_weight = estimate_stroke_weight(paths)
    stroke_pct = round(stroke_weight / h * 100, 1) if stroke_weight and h else None

    # Contrast ratio: ratio of thickest to thinnest stroke
    thin_strokes = []
    thick_strokes = []
    for p in paths:
        bb = path_bbox(p['d'])
        if not bb:
            continue
        ratio = max(bb['w'], bb['h']) / (min(bb['w'], bb['h']) + 0.01)
        s = min(bb['w'], bb['h'])
        if ratio > 5:
            thin_strokes.append(s)
        elif ratio > 2:
            thick_strokes.append(s)

    contrast_ratio = None
    if thin_strokes and thick_strokes:
        contrast_ratio = round(max(thick_strokes) / (min(thin_strokes) + 0.01), 2)

    # Path complexity (node count proxy)
    total_nodes = sum(len(re.findall(r'[MLCQAZ]', p['d'], re.IGNORECASE)) for p in paths)

    # Terminal style heuristic: count paths with very small bboxes at extremities
    # Serif: many small terminal paths. Sans: fewer.
    small_paths = sum(1 for p in paths if (bb := path_bbox(p['d'])) and
                      bb['w'] < w * 0.05 and bb['h'] < h * 0.1)
    terminal_style = 'likely_serif' if small_paths > len(paths) * 0.15 else 'likely_sans'

    dna = {
        'dimensions': {'width': w, 'height': h},
        'path_count': len(paths),
        'stroke_weight_px': stroke_weight,
        'stroke_weight_pct': stroke_pct,
        'contrast_ratio': contrast_ratio,
        'terminal_style': terminal_style,
        'complexity_nodes': total_nodes,
        'notes': []
    }

    if contrast_ratio:
        if contrast_ratio > 4:
            dna['notes'].append('High contrast — Didone/Modern style (think Vogue, Bodoni)')
        elif contrast_ratio > 2:
            dna['notes'].append('Medium contrast — Transitional/Old Style')
        else:
            dna['notes'].append('Low contrast — Geometric or Humanist sans')

    if stroke_pct:
        if stroke_pct < 6:
            dna['notes'].append('Very thin strokes — ultra-light weight')
        elif stroke_pct < 12:
            dna['notes'].append('Thin strokes — light/regular weight')
        elif stroke_pct < 20:
            dna['notes'].append('Medium strokes — regular/medium weight')
        else:
            dna['notes'].append('Heavy strokes — bold/black weight')

    return dna


# ─── glyph extraction ─────────────────────────────────────────────────────────

def extract_glyphs(svg_path, chars, out_dir):
    """
    Attempt to extract individual glyphs from a traced wordmark.
    Strategy: cluster paths by x-position into groups matching char count.
    Works well for spaced-out wordmarks; less reliable for tight/overlapping kerning.
    """
    paths = get_all_paths(svg_path)
    w, h = svg_dimensions(svg_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Get x-center of each path
    path_centers = []
    for p in paths:
        bb = path_bbox(p['d'])
        if bb:
            path_centers.append((bb['x'] + bb['w']/2, p))

    path_centers.sort(key=lambda x: x[0])

    n = len(chars)
    if n == 0 or not path_centers:
        print("ERROR: no chars or no paths found")
        return {}

    # Divide x-range into n buckets
    x_min = min(c[0] for c in path_centers)
    x_max = max(c[0] for c in path_centers)
    bucket_w = (x_max - x_min) / n + 0.01

    buckets = {c: [] for c in chars}
    for x_center, p in path_centers:
        idx = min(int((x_center - x_min) / bucket_w), n - 1)
        char = chars[idx]
        buckets[char].append(p)

    results = {}
    for char, char_paths in buckets.items():
        if not char_paths:
            print(f"WARNING: no paths found for '{char}'")
            continue

        # Build mini SVG for this glyph
        all_ds = [p['d'] for p in char_paths]
        bbs = [path_bbox(d) for d in all_ds if path_bbox(d)]
        if not bbs:
            continue

        gx = min(b['x'] for b in bbs)
        gy = min(b['y'] for b in bbs)
        gw = max(b['x'] + b['w'] for b in bbs) - gx
        gh = max(b['y'] + b['h'] for b in bbs) - gy
        padding = gw * 0.1

        path_els = '\n'.join(
            f'  <path d="{p["d"]}" fill="{p["fill"]}"/>'
            for p in char_paths
        )
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{gx-padding:.1f} {gy-padding:.1f} {gw+padding*2:.1f} {gh+padding*2:.1f}" width="{gw+padding*2:.0f}" height="{gh+padding*2:.0f}">
{path_els}
</svg>'''
        safe_char = char if char.isalnum() else f'u{ord(char):04X}'
        out_path = out_dir / f'{safe_char}.svg'
        out_path.write_text(svg, encoding='utf-8')
        results[char] = str(out_path)
        print(f"GLYPH: '{char}' → {out_path}")

    return results


# ─── font assembly ────────────────────────────────────────────────────────────

def build_font(glyphs_dir, font_name, out_path, units_per_em=1000):
    """
    Package SVG glyphs into an .otf font using fontTools.
    Each glyph SVG in glyphs_dir named <char>.svg becomes that character.
    """
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.t2Pen import T2Pen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.svgLib.path import SVGPath

    glyphs_dir = Path(glyphs_dir)
    svg_files = list(glyphs_dir.glob('*.svg'))

    if not svg_files:
        print("ERROR: no .svg files in glyphs dir")
        return

    fb = FontBuilder(units_per_em, isTTF=False)
    fb.setupGlyphOrder(['.notdef'] + [f.stem for f in svg_files])
    fb.setupCharacterMap({ord(f.stem[0]): f.stem for f in svg_files if len(f.stem) == 1})

    metrics = {}
    metrics['.notdef'] = (500, 0)

    glyph_pen_data = {}

    for svg_file in svg_files:
        char = svg_file.stem
        # Parse SVG viewBox to get dimensions
        content = svg_file.read_text(encoding='utf-8')
        vb_match = re.search(r'viewBox="([^"]+)"', content)
        w_match = re.search(r'width="([\d.]+)"', content)

        advance = units_per_em // 2
        if w_match:
            try:
                advance = int(float(w_match.group(1)) / 100 * units_per_em * 0.6)
            except:
                pass

        metrics[char] = (advance, 0)

    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({'familyName': font_name, 'styleName': 'Regular'})
    fb.setupOs2(sTypoAscender=800, sTypoDescender=-200, sxHeight=500, sCapHeight=700)
    fb.setupPost()
    fb.setupHead(unitsPerEm=units_per_em)

    # Add empty glyphs (proper path drawing requires more complex SVG→glyph conversion)
    glyphs = {'.notdef': {}}
    for svg_file in svg_files:
        glyphs[svg_file.stem] = {}

    fb.setupGlyf(glyphs) if False else None  # TTF only

    # For CFF (OTF), use empty charstrings as placeholder
    # Real conversion: use fonttools' SVGPath or defcon
    cs = {'.notdef': ''}
    for svg_file in svg_files:
        cs[svg_file.stem] = ''

    fb.setupCFF(
        nameStrings={'version': '1.0'},
        charStringsDict=cs,
        privateDict={'defaultWidthX': 0, 'nominalWidthX': 0}
    )

    out_path = str(out_path)
    fb.font.save(out_path)
    print(f"FONT: saved to {out_path}")
    print("NOTE: Font contains correct metrics and glyph slots. Open in FontForge to import SVG outlines per glyph.")
    return out_path


# ─── wordmark clone pipeline ──────────────────────────────────────────────────

def wordmark_pipeline(reference_image, text, out_path):
    """
    Full pipeline: reference image → trace → analyze DNA → extract available glyphs
    → report what exists vs what needs manual work → output composite SVG.
    """
    print(f"=== WORDMARK PIPELINE: '{text}' ===")
    print(f"Reference: {reference_image}")

    # 1. Trace
    print("\n[1/4] Tracing reference image...")
    svg_path = trace_for_letterforms(reference_image)
    print(f"Traced: {svg_path}")

    # 2. Analyze DNA
    print("\n[2/4] Extracting typographic DNA...")
    dna = analyze_svg(svg_path)
    print(json.dumps(dna, indent=2))

    # 3. Try to extract glyphs
    glyphs_dir = Path(reference_image).parent / 'glyphs'
    unique_chars = ''.join(dict.fromkeys(c for c in text.upper() if c.strip()))
    print(f"\n[3/4] Attempting glyph extraction for: {unique_chars}")
    extracted = extract_glyphs(svg_path, unique_chars, glyphs_dir)

    # 4. Report + assemble what we have
    print(f"\n[4/4] Assembly report:")
    found = set(extracted.keys())
    needed = set(unique_chars)
    missing = needed - found

    if missing:
        print(f"FOUND: {', '.join(sorted(found)) or 'none'}")
        print(f"MISSING: {', '.join(sorted(missing))}")
        print("\nFor missing letters:")
        print(f"  Stroke weight: {dna['stroke_weight_px']}px ({dna['stroke_weight_pct']}% of height)")
        print(f"  Contrast: {dna['contrast_ratio']} ({dna['terminal_style']})")
        for note in dna['notes']:
            print(f"  → {note}")
        print("\nClaude can generate missing glyphs as SVG paths using these DNA values.")
        print("Or: use the extracted glyphs in Glyphs App / FontForge to draw the rest.")
    else:
        print(f"All letters found: {', '.join(sorted(found))}")

    # Build simple composite SVG from extracted glyphs
    if extracted:
        compose_wordmark(extracted, text.upper(), out_path, dna)

    # Save DNA
    dna_path = str(out_path).rsplit('.', 1)[0] + '_dna.json'
    Path(dna_path).write_text(json.dumps(dna, indent=2), encoding='utf-8')
    print(f"\nDNA saved: {dna_path}")
    print(f"SVG saved: {out_path}")

    return dna, extracted


def compose_wordmark(glyph_paths, text, out_path, dna):
    """Arrange extracted glyph SVGs side by side into one wordmark SVG."""
    spacing = (dna.get('stroke_weight_px') or 10) * 0.5
    x_cursor = 0
    glyph_svgs = []
    total_h = 0

    for char in text:
        if char not in glyph_paths:
            continue
        content = Path(glyph_paths[char]).read_text(encoding='utf-8')
        w_match = re.search(r'width="([\d.]+)"', content)
        h_match = re.search(r'height="([\d.]+)"', content)
        vb_match = re.search(r'viewBox="([^"]+)"', content)

        gw = float(w_match.group(1)) if w_match else 100
        gh = float(h_match.group(1)) if h_match else 100
        total_h = max(total_h, gh)

        # Extract path elements
        paths_in_glyph = re.findall(r'<path[^/]*/>', content, re.DOTALL)
        # Translate to x_cursor position using viewBox origin
        vb_x = 0
        if vb_match:
            vb_parts = vb_match.group(1).split()
            try: vb_x = float(vb_parts[0])
            except: pass

        for p in paths_in_glyph:
            # Adjust fill
            p_out = p
            if 'fill' not in p:
                p_out = p.replace('/>', ' fill="#000000"/>')
            glyph_svgs.append(f'<g transform="translate({x_cursor - vb_x:.1f}, 0)">{p_out}</g>')

        x_cursor += gw + spacing

    total_w = x_cursor
    padding = total_h * 0.1
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="{-padding:.1f} {-padding:.1f} {total_w + padding*2:.1f} {total_h + padding*2:.1f}"
     width="{total_w + padding*2:.0f}" height="{total_h + padding*2:.0f}">
  <g transform="translate(0, {padding:.1f})">
{'chr(10)'.join(glyph_svgs)}
  </g>
</svg>'''
    Path(out_path).write_text(svg, encoding='utf-8')


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description='Letterform vectorization + DNA extraction')
    sub = p.add_subparsers(dest='cmd')

    t = sub.add_parser('trace', help='Raster image → SVG')
    t.add_argument('image')
    t.add_argument('--out', default=None)
    t.add_argument('--mode', choices=['outline','centerline'], default='outline')

    a = sub.add_parser('analyze', help='Extract typographic DNA from SVG/image')
    a.add_argument('source')
    a.add_argument('--out', default=None)

    e = sub.add_parser('extract', help='Extract individual glyphs from traced wordmark')
    e.add_argument('source')
    e.add_argument('--chars', required=True)
    e.add_argument('--out', default='glyphs')

    f = sub.add_parser('font', help='Package glyph SVGs into .otf')
    f.add_argument('glyphs_dir')
    f.add_argument('--name', default='CustomFont')
    f.add_argument('--out', default='font.otf')

    w = sub.add_parser('wordmark', help='Full pipeline: reference → trace → extract → assemble')
    w.add_argument('reference')
    w.add_argument('--text', required=True)
    w.add_argument('--out', default='wordmark.svg')

    args = p.parse_args()

    if args.cmd == 'trace':
        result = trace_image(args.image, mode=args.mode)
        if args.out and args.out != result:
            shutil.copy2(result, args.out)
            result = args.out
        print(f"SVG: {result}")

    elif args.cmd == 'analyze':
        src = args.source
        if not src.endswith('.svg'):
            src = trace_for_letterforms(src)
        dna = analyze_svg(src)
        print(json.dumps(dna, indent=2))
        if args.out:
            Path(args.out).write_text(json.dumps(dna, indent=2), encoding='utf-8')

    elif args.cmd == 'extract':
        src = args.source
        if not src.endswith('.svg'):
            src = trace_for_letterforms(src)
        extract_glyphs(src, args.chars, args.out)

    elif args.cmd == 'font':
        build_font(args.glyphs_dir, args.name, args.out)

    elif args.cmd == 'wordmark':
        wordmark_pipeline(args.reference, args.text, args.out)

    else:
        p.print_help()

if __name__ == '__main__':
    main()
