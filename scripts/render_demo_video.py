"""Render the landing page demo video (MP4 + WebM + poster), procedurally.

Usage: pip install pillow imageio-ffmpeg && python scripts/render_demo_video.py

Frames are drawn with Pillow, encoded with the ffmpeg binary that
imageio-ffmpeg ships. Output goes to frontend/public/media/.
"""
import math, os, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "media"
OUT.mkdir(parents=True, exist_ok=True)
W, H, FPS, SECONDS = 1280, 720, 30, 12
N = FPS * SECONDS

GREEN, GREEN_D, ORANGE, INK, MUTE = (31,138,76), (23,112,61), (242,85,51), (22,22,24), (120,118,124)
OAT, OAT2, LINE, WHITE = (248,245,240), (241,235,226), (231,228,223), (255,255,255)
CRIT, CRIT_BG, OKC, OK_BG = (200,36,36), (252,220,212), (26,127,82), (224,243,233)

def font(size, bold=False):
    cands = ["C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
             "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"]
    for c in cands:
        if os.path.exists(c): return ImageFont.truetype(c, size)
    return ImageFont.load_default()
def serif(size):
    for c in ["C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/times.ttf"]:
        if os.path.exists(c): return ImageFont.truetype(c, size)
    return font(size)

F12, F13, F14, F16, F18B, F22B, F34S, F48S = font(12), font(13), font(14), font(16), font(18, True), font(22, True), serif(34), serif(48)

def ease(t):  # smooth in-out
    t = max(0.0, min(1.0, t)); return t*t*(3-2*t)
def seg(frame, start, dur):  # 0..1 progress for a window in seconds
    return ease((frame/FPS - start) / dur)
def lerp(a, b, t): return a + (b-a)*t
def rr(d, box, r, fill, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)
def pill(d, x, y, text, fg, bg, f=F12, padx=10, pady=4):
    tw = d.textlength(text, font=f); h = f.size + pady*2
    rr(d, (x, y, x+tw+padx*2, y+h), h/2, bg); d.text((x+padx, y+pady-1), text, font=f, fill=fg); return tw+padx*2

def draw_frame(i):
    t = i / FPS
    img = Image.new("RGB", (W, H), OAT2); d = ImageDraw.Draw(img)
    # warm/green glow
    glow = Image.new("RGB", (W, H), OAT2); gd = ImageDraw.Draw(glow)
    gd.ellipse((W*0.55, H*0.55, W*1.25, H*1.35), fill=(255,205,190)); gd.ellipse((-W*0.25, H*0.5, W*0.45, H*1.3), fill=(205,236,218))
    glow = glow.filter(ImageFilter.GaussianBlur(120)); img = Image.blend(img, glow, 0.9); d = ImageDraw.Draw(img)

    # title card (0-1.6s) fades out
    a = 1 - seg(i, 1.2, 0.6)
    if a > 0:
        ov = Image.new("RGBA", (W, H), (248,245,240, int(255*a))); od = ImageDraw.Draw(ov)
        od.text((W/2, H/2-30), "Run every incident", font=F48S, fill=(*INK, int(255*a)), anchor="mm")
        od.text((W/2, H/2+30), "like your best one", font=F48S, fill=(*INK, int(255*a)), anchor="mm")
        img.paste(ov, (0,0), ov); d = ImageDraw.Draw(img)
        if a > 0.98: return img

    # app frame slides up (1.2-2.2s)
    ry = lerp(80, 0, seg(i, 1.2, 1.0)); fx, fy, fw, fh = 90, 70+ry, 1100, 600
    shadow = Image.new("RGBA", (W, H), (0,0,0,0)); sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((fx, fy+24, fx+fw, fy+fh+24), 18, fill=(40,30,20,70)); shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    img.paste(shadow, (0,0), shadow); d = ImageDraw.Draw(img)
    rr(d, (fx, fy, fx+fw, fy+fh), 16, (42,41,46))
    # sidebar
    rr(d, (fx+12, fy+12, fx+170, fy+fh-12), 10, (42,41,46))
    d.rounded_rectangle((fx+22, fy+22, fx+44, fy+44), 6, fill=GREEN); d.text((fx+52, fy+24), "Restora", font=F16, fill=WHITE)
    rr(d, (fx+20, fy+62, fx+162, fy+92), 8, ORANGE); d.text((fx+91, fy+77), "Declare incident", font=F13, fill=WHITE, anchor="mm")
    for k, item in enumerate(["Home", "Incidents", "Alerts", "On-call", "Status pages", "Post-incident", "Insights"]):
        y = fy+112+k*30
        if k == 1: rr(d, (fx+20, y-6, fx+162, y+20), 7, (57,56,61))
        d.text((fx+30, y), item, font=F13, fill=WHITE if k == 1 else (165,162,166))
    # main panel
    px, py, pw, ph = fx+182, fy+12, fw-194, fh-24
    rr(d, (px, py, px+pw, py+ph), 12, WHITE)

    # header: incident title + status flow (appears 2.2s)
    p2 = seg(i, 2.2, 0.6)
    if p2 > 0:
        d.text((px+24, py+22), "INC-1042", font=F12, fill=MUTE); d.text((px+24, py+40), "Checkout API unavailable", font=F22B, fill=INK)
        d.line((px, py+82, px+pw, py+82), fill=LINE)
        steps = ["Triage", "Investigating", "Fixing", "Monitoring", "Closed"]
        # status advances over time
        cur = 1 if t < 5.2 else 2 if t < 8.6 else 3 if t < 10.6 else 4
        x = px+24
        for k, s in enumerate(steps):
            if k == cur: x += pill(d, x, py+94, s, INK, WHITE, F13) + 6; d.rounded_rectangle((x-8-d.textlength(s, font=F13)-20, py+94, x-6, py+94+F13.size+8), 12, outline=LINE)
            else: d.text((x, py+98), s, font=F13, fill=(90,88,94) if k < cur else MUTE); x += d.textlength(s, font=F13)+6
            if k < len(steps)-1: d.text((x, py+96), "›", font=F13, fill=(195,204,218)); x += 14
        sev = "CRITICAL" if t < 9.4 else "ERROR"
        pill(d, px+pw-150, py+94, sev, CRIT if sev == "CRITICAL" else (180,68,28), CRIT_BG if sev == "CRITICAL" else (253,228,216), F12)

    # timeline column
    tx, ty = px+24, py+150
    d.text((tx, ty), "Timeline", font=F18B, fill=INK)
    events = [(2.8, "18:02", "Alert fired: checkout health check failing", ORANGE),
              (3.6, "18:04", "Incident declared by Alex Moreau", GREEN),
              (5.2, "18:09", "Agent: payments 4.12.0 exhausted its connection pool", ORANGE),
              (6.4, "18:12", "Priya Raman: rolling back", GREEN),
              (8.6, "18:20", "Status changed Fixing → Monitoring", GREEN),
              (10.6, "18:41", "Incident closed · customer update published", GREEN)]
    for k, (at, ts, txt, col) in enumerate(events):
        p = seg(i, at, 0.5)
        if p <= 0: continue
        y = ty+40+k*46; ox = lerp(30, 0, p)
        d.text((tx+ox, y+2), ts, font=F12, fill=MUTE)
        d.ellipse((tx+52+ox, y+3, tx+64+ox, y+15), fill=col); d.ellipse((tx+48+ox, y-1, tx+68+ox, y+19), outline=(*col,), width=1)
        d.text((tx+78+ox, y), txt, font=F14, fill=INK)
        if k < len(events)-1 and seg(i, at+0.4, 0.3) > 0: d.line((tx+58, y+18, tx+58, y+44), fill=LINE)

    # right rail: agent card (5.2s) + actions
    rx, ry_, rw = px+pw-330, py+150, 300
    d.text((rx, ry_), "Agent", font=F18B, fill=INK)
    p5 = seg(i, 5.2, 0.6)
    if p5 > 0:
        cy = ry_+36+lerp(20, 0, p5); rr(d, (rx, cy, rx+rw, cy+150), 12, OAT, outline=LINE)
        d.rounded_rectangle((rx+14, cy+14, rx+38, cy+38), 8, fill=ORANGE); d.text((rx+26, cy+26), "◆", font=F13, fill=WHITE, anchor="mm")
        d.text((rx+48, cy+16), "Hypothesis · 92% confidence", font=F12, fill=MUTE)
        lines = ["Connection pool on payments 4.12.0", "exhausted 3 min after the 17:50 deploy.", "Rolling back is the likely fix."]
        for k, l in enumerate(lines): d.text((rx+14, cy+46+k*20), l, font=F14, fill=INK)
        bx = rx+14
        for k, lab in enumerate(["Roll back", "Draft update", "Show evidence"]):
            chosen = k == 0 and t >= 6.2
            bx += pill(d, bx, cy+112, lab, WHITE if chosen else INK, GREEN if chosen else WHITE, F12) + 6
    d.text((rx, ry_+210), "Actions", font=F18B, fill=INK)
    acts = [(6.4, "Roll back payments 4.12.0", "Priya Raman", 8.2), (6.9, "Drain checkout pods in eu-west", "Sam Lee", 9.0), (7.4, "Publish customer update", "Alex Moreau", 10.2)]
    for k, (at, txt, who, done_at) in enumerate(acts):
        p = seg(i, at, 0.4)
        if p <= 0: continue
        y = ry_+246+k*38; done = t >= done_at
        rr(d, (rx, y, rx+16, y+16), 4, OKC if done else WHITE, outline=OKC if done else (200,209,224))
        if done: d.text((rx+8, y+8), "✓", font=F12, fill=WHITE, anchor="mm")
        d.text((rx+26, y-1), txt, font=F14, fill=MUTE if done else INK); d.text((rx+26, y+16), who, font=F12, fill=MUTE)

    # status page toast (10.2s)
    p10 = seg(i, 10.2, 0.6)
    if p10 > 0:
        tw_, th_ = 420, 64; toy = lerp(H+10, H-th_-40, p10); tox = W/2 - tw_/2
        rr(d, (tox, toy, tox+tw_, toy+th_), 14, INK)
        d.ellipse((tox+18, toy+22, tox+38, toy+42), fill=OKC); d.text((tox+28, toy+32), "✓", font=F13, fill=WHITE, anchor="mm")
        d.text((tox+52, toy+12), "Published to status.restora.io", font=F16, fill=WHITE)
        d.text((tox+52, toy+36), "Customers can complete checkout again.", font=F12, fill=(190,188,192))

    # end card fade (11.3s)
    e = seg(i, 11.3, 0.7)
    if e > 0:
        ov = Image.new("RGBA", (W, H), (22,22,24, int(235*e))); od = ImageDraw.Draw(ov)
        od.text((W/2, H/2-22), "Restora", font=F48S, fill=(255,255,255,int(255*e)), anchor="mm")
        od.text((W/2, H/2+34), "From first alert to final fix", font=F16, fill=(200,198,202,int(255*e)), anchor="mm")
        img.paste(ov, (0,0), ov)
    return img

frames_dir = OUT / "_frames"; frames_dir.mkdir(exist_ok=True)
for i in range(N):
    draw_frame(i).save(frames_dir / f"f{i:04d}.png")
    if i % 60 == 0: print("frame", i, "/", N, flush=True)
draw_frame(int(FPS*4.0)).save(OUT / "restora-demo-poster.jpg", quality=88)

ff = imageio_ffmpeg.get_ffmpeg_exe()
mp4 = OUT / "restora-demo.mp4"
base = [ff, "-y", "-framerate", str(FPS), "-i", str(frames_dir / "f%04d.png")]
r = subprocess.run(base + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", "-movflags", "+faststart", str(mp4)], capture_output=True, text=True)
if r.returncode != 0:
    print("libx264 unavailable, falling back to mpeg4:", r.stderr[-300:])
    subprocess.run(base + ["-c:v", "mpeg4", "-q:v", "3", "-pix_fmt", "yuv420p", str(mp4)], check=True)
webm = OUT / "restora-demo.webm"
subprocess.run(base + ["-c:v", "libvpx-vp9", "-b:v", "1.2M", "-pix_fmt", "yuv420p", str(webm)], capture_output=True)
for f in frames_dir.glob("*.png"): f.unlink()
frames_dir.rmdir()
for f in OUT.iterdir(): print(f.name, round(f.stat().st_size/1024), "KB")
