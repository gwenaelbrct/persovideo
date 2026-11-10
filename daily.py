"""Génère la vidéo du jour (1 concept parmi 30, jamais le même sur 30 jours) + textes + couverture.

Usage: python3 daily.py [--date 2026-11-11] [--scale 1.0]
Sortie: out/<date>/video.mp4, cover.jpg, meta.json
"""
import argparse, datetime as dtm, json, os, random, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

from concepts import CONCEPTS, concept_for_day, render

COMMON_TAGS = ["#fyp", "#viral", "#shorts", "#pourtoi"]


def make_cover(video, out_jpg, text, t=55):
    frame = out_jpg + ".png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", video, "-frames:v", "1", frame], check=True)
    img = Image.open(frame).convert("RGB")
    W, H = img.size
    img = Image.blend(img, img.filter(ImageFilter.GaussianBlur(6)), 0.35)
    dr = ImageDraw.Draw(img, "RGBA")
    lines = text.split("\n")
    size = int(W * 0.13)
    f = ImageFont.truetype(FONT, size)
    while max(dr.textlength(l, font=f) for l in lines) > W * 0.9:
        size -= 4; f = ImageFont.truetype(FONT, size)
    y = H * 0.36
    for l in lines:
        tw = dr.textlength(l, font=f)
        x = (W - tw) / 2
        dr.rounded_rectangle([x - 24, y - 12, x + tw + 24, y + size * 1.12], 18, fill=(0, 0, 0, 150))
        dr.text((x, y), l, font=f, fill=(255, 225, 60), stroke_width=max(2, size // 16), stroke_fill=(0, 0, 0))
        y += size * 1.3
    img.save(out_jpg, quality=92)
    os.remove(frame)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dtm.date.today().isoformat())
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--duration", type=float, default=70)
    ap.add_argument("--concept", default=None, help="forcer un concept (test)")
    a = ap.parse_args()
    day = dtm.date.fromisoformat(a.date)
    seed = day.toordinal()
    cid = a.concept or concept_for_day(seed)
    c = CONCEPTS[cid]
    rnd = random.Random(seed)
    od = os.path.join(HERE, "out", a.date)
    os.makedirs(od, exist_ok=True)
    video = os.path.join(od, "video.mp4")
    print("Concept du jour:", cid, "seed", seed, flush=True)
    render(cid, seed, a.duration, a.scale, video)

    # Telegram limite les bots à 50 Mo : on recompresse si besoin
    if os.path.getsize(video) > 45e6:
        tmp = video + ".tmp.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-c:v", "libx264", "-crf", "26", "-preset", "medium",
                        "-c:a", "copy", tmp], check=True)
        os.replace(tmp, video)

    title = rnd.choice(c["titles"])
    cover_text = rnd.choice(c["cover"])
    tags = rnd.sample(c["tags"], min(6, len(c["tags"]))) + COMMON_TAGS
    desc = c["desc"]
    caption = f"{title}\n\n{desc}\n\n{' '.join(tags)}"
    make_cover(video, os.path.join(od, "cover.jpg"), cover_text, t=min(20 if c["engine"] == "race" else 55, a.duration - 2))  # course : pas de spoiler
    meta = dict(date=a.date, template=cid, options=c["params"], seed=seed, title=title, description=desc, hashtags=tags,
                youtube_title=(title[:90] + " #shorts"), caption=caption)
    with open(os.path.join(od, "meta.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
