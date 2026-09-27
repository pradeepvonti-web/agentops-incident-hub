"""Render three short looping feature clips for the landing page pillars.

Usage: pip install pillow imageio-ffmpeg && python scripts/render_feature_clips.py
Outputs frontend/public/media/clip-{oncall,investigate,status}.{mp4,webm} + posters.
"""
import math, os, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "media"
OUT.mkdir(parents=True, exist_ok=True)
W, H, FPS, SECONDS = 960, 600, 30, 8
N = FPS * SECONDS

GREEN, ORANGE, INK, MUTE = (31,138,76), (242,85,51), (22,22,24), (120,118,124)
OAT, OAT2, LINE, WHITE = (248,245,240), (241,235,226), (231,228,223), (255,255,255)
OKC, OK_BG = (26,127,82), (224,243,233)

def font(size, bold=False):
    for c in (["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"] if bold else ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]):
        if os.path.exists(c): return ImageFont.truetype(c, size)
    return ImageFont.load_default()
F11, F12, F13, F14B, F16B, F20B = font(11), font(12), font(13), font(14, True), font(16, True), font(20, True)

def ease(t): t = max(0.0, min(1.0, t)); return t*t*(3-2*t)
def seg(i, start, dur): return ease((i/FPS - start) / dur)
def lerp(a, b, t): return a + (b-a)*t
def rr(d, box, r, fill, outline=None, width=1): d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)
def pill(d, x, y, text, fg, bg, f=F12, padx=9, pady=3):
    tw = d.textlength(text, font=f); h = f.size + pady*2
    rr(d, (x, y, x+tw+padx*2, y+h), h/2, bg); d.text((x+padx, y+pady-1), text, font=f, fill=fg); return tw+padx*2

def base(warm=False):
    img = Image.new("RGB", (W, H), OAT); d = ImageDraw.Draw(img)
    glow = Image.new("RGB", (W, H), OAT); gd = ImageDraw.Draw(glow)
    gd.ellipse((W*0.5, H*0.55, W*1.2, H*1.3), fill=(255,214,200) if warm else (208,236,220))
    glow = glow.filter(ImageFilter.GaussianBlur(90)); img = Image.blend(img, glow, 0.85)
    return img, ImageDraw.Draw(img)

def card(img, box, r=12):
    shadow = Image.new("RGBA", (W, H), (0,0,0,0)); sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((box[0], box[1]+16, box[2], box[3]+16), r, fill=(40,30,20,60)); shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    img.paste(shadow, (0,0), shadow); d = ImageDraw.Draw(img); rr(d, box, r, WHITE); return d

# ---------------------------------------------------------------- on-call
def oncall(i):
    img, d = base(); t = i / FPS
    d = card(img, (70, 90, 890, 520))
    d.text((94, 108), "Payments primary", font=F20B, fill=INK); d.text((94, 136), "Europe/London · weekly handover, Thursday 09:00", font=F12, fill=MUTE)
    gx, gy, gw = 200, 190, 660
    days = ["Mon 27", "Tue 28", "Wed 29", "Thu 30"]
    for k, day in enumerate(days):
        x = gx + k*gw/4; d.text((x+6, gy-24), day, font=F12, fill=MUTE); d.line((x, gy-4, x, 470), fill=LINE)
    rows = [("EUR", "Priya Raman", 0.00, 0.50, (220,243,230), (19,92,52)), ("AMER", "Sam Lee", 0.25, 0.50, (223,233,251), (28,63,122)), ("APAC", "Dana Okafor", 0.50, 0.50, (253,240,196), (109,81,0))]
    for k, (r, name, l, w, bg, fg) in enumerate(rows):
        y = gy + 20 + k*80; d.text((94, y+22), r, font=F13, fill=MUTE); d.line((gx, y+70, gx+gw, y+70), fill=LINE)
        x0 = gx + l*gw; x1 = x0 + w*gw; rr(d, (x0+4, y+10, x1-4, y+58), 8, bg); d.text((x0+16, y+24), name, font=F14B, fill=fg)
    # an override slides in over the AMER row (2.0s), then a cover request badge lands (4.5s)
    p = seg(i, 2.0, 0.8)
    if p > 0:
        x0 = gx + 0.42*gw; x1 = x0 + 0.18*gw; y = gy + 20 + 80; ox = lerp(60, 0, p)
        rr(d, (x0+4+ox, y+10, x1-4+ox, y+58), 8, (253,228,216), outline=ORANGE, width=2); d.text((x0+16+ox, y+18), "Override", font=F11, fill=(138,42,18)); d.text((x0+16+ox, y+34), "Alex Moreau", font=F14B, fill=(138,42,18))
    now_x = gx + (0.31 + 0.02*math.sin(t)) * gw
    d.line((now_x, gy-4, now_x, 470), fill=ORANGE, width=2); pill(d, now_x-24, gy-46, "10:29", WHITE, ORANGE, F11)
    p = seg(i, 4.5, 0.6)
    if p > 0:
        bx, by = 560, lerp(60, 82, p); rr(d, (bx, by, bx+300, by+58), 12, INK)
        d.text((bx+16, by+10), "Cover request accepted", font=F14B, fill=WHITE); d.text((bx+16, by+32), "Alex covers 21:00–23:00. Priya notified.", font=F11, fill=(200,198,202))
    return img

# ---------------------------------------------------------- investigate
def investigate(i):
    img, d = base(warm=True); t = i / FPS
    d = card(img, (70, 70, 890, 540))
    d.text((94, 90), "INC-1043  Search latency regression", font=F20B, fill=INK); pill(d, 94, 124, "ERROR", (180,68,28), (253,228,216)); pill(d, 170, 124, "Investigating", INK, OAT2)
    events = [(0.6, "17:20", "Alert fired: search p95 above threshold", ORANGE), (1.6, "17:26", "Incident declared by Sam Lee", GREEN),
              (2.8, "17:31", "Agent: correlating with 09:10 flag rollout (query-expansion)", ORANGE), (4.2, "17:44", "Cause identified: high-cardinality queries", GREEN), (5.6, "18:05", "Flag disabled · p95 back to 210ms", GREEN)]
    for k, (at, ts, txt, col) in enumerate(events):
        p = seg(i, at, 0.5)
        if p <= 0: continue
        y = 176 + k*54; ox = lerp(24, 0, p)
        d.text((94+ox, y+2), ts, font=F12, fill=MUTE); d.ellipse((150+ox, y+3, 162+ox, y+15), fill=col); d.ellipse((145+ox, y-2, 167+ox, y+20), outline=col)
        d.text((178+ox, y), txt, font=F13, fill=INK)
        if k < 4 and seg(i, at+0.4, 0.3) > 0: d.line((156, y+20, 156, y+52), fill=LINE)
    p = seg(i, 3.0, 0.6)
    if p > 0:
        bx, by = 560, lerp(190, 176, p); rr(d, (bx, by, bx+300, by+150), 12, OAT, outline=LINE)
        d.rounded_rectangle((bx+14, by+12, bx+36, by+34), 7, fill=ORANGE); d.text((bx+46, by+14), "Hypothesis · 88% confidence", font=F11, fill=MUTE)
        for k, l in enumerate(["Query-expansion flag at 50% traffic", "is generating high-cardinality queries.", "Disable the flag; expect p95 < 300ms."]): d.text((bx+14, by+44+k*20), l, font=F13, fill=INK)
        chosen = t > 4.0; bx2 = bx+14
        for k, lab in enumerate(["Disable flag", "Show evidence"]): bx2 += pill(d, bx2, by+112, lab, WHITE if (k == 0 and chosen) else INK, GREEN if (k == 0 and chosen) else WHITE, F11) + 6
    # latency sparkline dropping after 5.6s
    sx, sy, sw, sh = 560, 380, 300, 120; rr(d, (sx, sy, sx+sw, sy+sh), 10, OAT)
    d.text((sx+12, sy+8), "search p95 (ms)", font=F11, fill=MUTE)
    pts = []
    for k in range(60):
        x = sx + 12 + k*(sw-24)/59; base_v = 1350 if k < 42 else lerp(1350, 210, ease((k-42)/12))
        v = base_v + 60*math.sin(k*0.9 + t); pts.append((x, sy+sh-14 - (v/1500)*(sh-40)))
    cut = int(min(60, (t/6.5)*60))
    if cut > 1: d.line(pts[:cut], fill=ORANGE if cut < 45 else GREEN, width=2)
    return img

# -------------------------------------------------------------- status
def status(i):
    img, d = base(); t = i / FPS
    for k, off in enumerate([(0, -28, 0.5), (0, -14, 0.75)]):
        rr(d, (110, 100+off[1], 850, 160+off[1]), 12, (255,255,255))
    d = card(img, (90, 100, 870, 540))
    d.text((114, 122), "Restora Status", font=F20B, fill=INK); d.text((114, 150), "status.restora.io", font=F12, fill=MUTE); pill(d, 740, 124, "Subscribe", WHITE, INK, F12)
    ok = t > 5.2
    rr(d, (114, 186, 846, 236), 10, OK_BG if ok else (253,240,196), outline=(200,233,216) if ok else (239,227,166))
    d.text((132, 201), ("✓ We're fully operational" if ok else "◐ Degraded performance"), font=F14B, fill=OKC if ok else (122,91,0))
    comps = [("Checkout", "Partial outage" if t < 3.2 else "Operational"), ("Search", "Degraded performance" if t < 4.4 else "Operational"), ("Identity", "Operational"), ("Orders", "Operational")]
    for k, (name, st) in enumerate(comps):
        y = 262 + k*54; d.text((132, y+6), name, font=F14B, fill=INK)
        good = st == "Operational"; tw = d.textlength(st, font=F11)
        pill(d, 846-tw-18-2, y+2, st, OKC if good else (180,68,28), OK_BG if good else (253,228,216), F11)
        for b in range(45):
            bx = 300 + b*9; bad = (not good) and b > 41
            d.rectangle((bx, y+8, bx+6, y+24), fill=(217,84,77) if bad else OKC)
        d.line((132, y+42, 846, y+42), fill=LINE)
    p = seg(i, 1.2, 0.6)
    if p > 0:
        by = lerp(560, 480, p); rr(d, (114, by, 846, by+50), 10, INK)
        d.text((132, by+8), "Update published", font=F14B, fill=WHITE); d.text((132, by+28), "Rollback complete. Customers can check out again. — Alex, 18:41", font=F11, fill=(200,198,202))
    return img

ff = imageio_ffmpeg.get_ffmpeg_exe()
for name, fn, poster_at in [("clip-oncall", oncall, 5.5), ("clip-investigate", investigate, 6.5), ("clip-status", status, 6.0)]:
    frames = OUT / f"_{name}"; frames.mkdir(exist_ok=True)
    for i in range(N): fn(i).save(frames / f"f{i:04d}.png")
    fn(int(FPS*poster_at)).save(OUT / f"{name}-poster.jpg", quality=86)
    inp = [ff, "-y", "-framerate", str(FPS), "-i", str(frames / "f%04d.png")]
    r = subprocess.run(inp + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-movflags", "+faststart", str(OUT / f"{name}.mp4")], capture_output=True)
    if r.returncode != 0: subprocess.run(inp + ["-c:v", "mpeg4", "-q:v", "3", "-pix_fmt", "yuv420p", str(OUT / f"{name}.mp4")], check=True)
    subprocess.run(inp + ["-c:v", "libvpx-vp9", "-b:v", "900k", "-pix_fmt", "yuv420p", str(OUT / f"{name}.webm")], capture_output=True)
    for f in frames.glob("*.png"): f.unlink()
    frames.rmdir(); print("rendered", name, flush=True)
for f in sorted(OUT.iterdir()): print(f.name, round(f.stat().st_size/1024), "KB")
