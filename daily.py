"""Génère la vidéo du jour + titre/description/hashtags + couverture.

Usage: python3 daily.py [--date 2026-11-11] [--scale 1.0]
Sortie: out/<date>/video.mp4, cover.jpg, meta.json
"""
import argparse, datetime as dtm, json, os, random, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Rotation : un template par jour, dans cet ordre, en boucle
ROTATION = [
    ("wheel", {}),
    ("race", {"exp": "x2_vs_half"}),
    ("walls", {}),
    ("race", {"exp": "plus1_vs_x2"}),
    ("wheel", {}),
    ("race", {"exp": "x3_fragile_vs_x2"}),
    ("walls", {}),
]

META = {
    "wheel": dict(
        titles=["1 ball enters the black hole… then THIS happens 🕳️", "Every ball that touches the black hole DOUBLES",
                "Can 1 ball fill the entire wheel? 🤯", "Black hole doubles every ball… wait for the end",
                "The most satisfying black hole you'll see today"],
        cover=["WILL IT FILL\nTHE WHEEL?", "1 BALL →\n350 BALLS?", "BLACK HOLE\nDOUBLES ALL"],
        desc="Each time a ball falls into the black hole, it comes out as TWO. How long until the wheel is full? 🕳️\n"
             "Chaque bille qui touche le trou noir se dédouble. Combien de temps pour remplir la roue ?",
        tags=["#satisfying", "#oddlysatisfying", "#physics", "#simulation", "#blackhole", "#marblerace", "#asmr", "#satisfyingvideo"]),
    "walls": dict(
        titles=["Every ball crushed by the walls DOUBLES 😳", "The walls are closing in… and the balls multiply",
                "Crushed = doubled. How many by the end?", "This ends way more chaotic than you think",
                "Satisfying wall crusher doubling simulation"],
        cover=["CRUSHED\n= DOUBLED", "THE WALLS\nARE CLOSING", "HOW MANY\nAT THE END?"],
        desc="Every ball squeezed by a moving wall turns into two. Guess the final number before the end! 🧱\n"
             "Chaque bille écrasée par un mur se dédouble. Devine le nombre final !",
        tags=["#satisfying", "#oddlysatisfying", "#physics", "#simulation", "#asmr", "#satisfyingvideo", "#chaos", "#balls"]),
    "race": dict(
        titles=["{title} — who reaches the bottom first? 🤔", "Math experiment: {title}. Guess the winner!",
                "{title}… the ending surprised me", "Exponential growth explained with balls: {title}"],
        cover=["{title}\nWHO WINS?", "GUESS\nTHE WINNER", "{title}"],
        desc="{question} Comment your guess BEFORE the end! 👇\n"
             "Expérience mathématique : qui atteint le bas en premier ? Donne ton pronostic en commentaire !",
        tags=["#math", "#maths", "#experiment", "#satisfying", "#exponential", "#simulation", "#marblerace", "#physics", "#didyouknow"]),
}
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
    a = ap.parse_args()
    day = dtm.date.fromisoformat(a.date)
    seed = day.toordinal()
    kind, opts = ROTATION[seed % len(ROTATION)]
    rnd = random.Random(seed)
    od = os.path.join(HERE, "out", a.date)
    os.makedirs(od, exist_ok=True)
    video = os.path.join(od, "video.mp4")
    py = [sys.executable, "-W", "ignore"]
    common = ["--seed", str(seed), "--duration", str(a.duration), "--scale", str(a.scale), "--out", video]
    fmtvars = {}
    if kind == "wheel":
        pal = rnd.choice(["neon", "sunset", "toxic"])
        cmd = py + [os.path.join(HERE, "wheel_blackhole.py"), "--palette", pal] + common
    elif kind == "walls":
        cmd = py + [os.path.join(HERE, "crusher_walls.py")] + common
    else:
        sys.path.insert(0, HERE)
        from race_towers import EXPERIMENTS
        e = EXPERIMENTS[opts["exp"]]
        fmtvars = dict(title=e["title"], question=e["question"].capitalize())
        cmd = py + [os.path.join(HERE, "race_towers.py"), "--exp", opts["exp"]] + common
    print("Template du jour:", kind, opts, "seed", seed, flush=True)
    subprocess.run(cmd, check=True, cwd=HERE)

    # Telegram limite les bots à 50 Mo : on recompresse si besoin
    if os.path.getsize(video) > 45e6:
        tmp = video + ".tmp.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-c:v", "libx264", "-crf", "26", "-preset", "medium",
                        "-c:a", "copy", tmp], check=True)
        os.replace(tmp, video)

    m = META[kind]
    title = rnd.choice(m["titles"]).format(**fmtvars)
    cover_text = rnd.choice(m["cover"]).format(**fmtvars)
    tags = rnd.sample(m["tags"], 6) + COMMON_TAGS
    desc = m["desc"].format(**fmtvars)
    caption = f"{title}\n\n{desc}\n\n{' '.join(tags)}"
    make_cover(video, os.path.join(od, "cover.jpg"), cover_text, t=20 if kind == "race" else 55)  # course : pas de spoiler
    meta = dict(date=a.date, template=kind, options=opts, seed=seed, title=title, description=desc, hashtags=tags,
                youtube_title=(title[:90] + " #shorts"), caption=caption)
    with open(os.path.join(od, "meta.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
