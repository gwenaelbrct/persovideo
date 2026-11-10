"""Moteur plinko : les billes tombent entre des clous et se multiplient selon la case d'arrivée.

mode "multi"  : cases ×1 au centre, ×8 sur les bords
mode "deadly" : cases mortelles au centre, gros multiplicateurs sur les bords
"""
import argparse, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from common import FPS, FONT, Mixer, Encoder, ball_sprite, gradient_bg, hsv, fmt

SUB = 4
BINS = {
    "multi": [8, 5, 3, 2, 1, 1, 1, 1, 1, 2, 3, 5, 8],
    "deadly": [20, 10, 5, 3, 2, 0, 0, 0, 2, 3, 5, 10, 20],
}
PALETTES = [((8, 6, 24), (26, 8, 48), 0.75), ((4, 14, 10), (8, 36, 28), 0.38), ((20, 6, 14), (48, 12, 30), 0.95),
            ((4, 8, 22), (6, 22, 44), 0.55), ((18, 10, 2), (40, 22, 4), 0.10)]


def run(c, seed, duration, scale, out):
    rng = np.random.default_rng(seed)
    S = scale
    W, H = int(1080 * S), int(1920 * S)
    bg1, bg2, hue = PALETTES[seed % len(PALETTES)]
    bins = BINS[c.get("mode", "multi")]
    nb = len(bins)
    rows = nb - 1
    x0, x1 = 70 * S, 1010 * S
    bw = (x1 - x0) / nb
    ytop, ybot = 560 * S, 1500 * S
    pegs = []
    for r in range(rows):
        y = ytop + (ybot - ytop) * r / (rows - 1)
        n = r + 3
        for k in range(n):
            x = W / 2 + (k - (n - 1) / 2) * bw
            if x0 < x < x1:
                pegs.append((x, y))
    pegs = np.array(pegs)
    pr, br = 7 * S, 11 * S
    bin_top, bin_bot = 1560 * S, 1800 * S
    g = 1900 * S
    dt = 1 / (FPS * SUB)
    n_frames = int(duration * FPS)
    cap_live = c.get("cap_live", 160)

    pos = np.zeros((0, 2)); vel = np.zeros((0, 2)); hues = np.zeros(0)
    queue = float(c.get("start", 1))
    total_landed = 0
    bin_flash = np.zeros(nb)
    bin_count = np.zeros(nb, int)
    drop_acc = 0.0
    floaters = []  # textes « ×5 » qui montent

    bgimg = gradient_bg(W, H, bg1, bg2)
    f_big, f_mid, f_bin = (ImageFont.truetype(FONT, int(p * S)) for p in (140, 44, 34))
    enc = Encoder(out, W, H)
    mx = Mixer(duration, root=float(rng.choice([110.0, 123.5, 130.8])))
    last_tick, last_note = -1.0, -1.0
    sprites = {}
    peg_flash = np.zeros(len(pegs))

    def count():
        return len(pos) + queue

    for fi in range(n_frames):
        t = fi / FPS
        # débit de lâcher : augmente avec le temps (et avec la file d'attente)
        rate = 0.6 + 7.5 * (t / duration) ** 1.5           # billes / seconde
        drop_acc += rate / FPS
        while drop_acc >= 1 and queue >= 1 and len(pos) < cap_live:
            drop_acc -= 1; queue -= 1
            pos = np.vstack([pos, [W / 2 + rng.uniform(-40, 40) * S, 470 * S]])
            vel = np.vstack([vel, [rng.uniform(-60, 60) * S, 0]])
            hues = np.append(hues, (hue + rng.uniform(-0.08, 0.08)) % 1)
        if queue < 1 and len(pos) == 0:
            # sécurité : on ne laisse jamais le jeu vide
            queue = 1
        drop_acc = min(drop_acc, 3)
        landed_now = []
        peg_hits = 0
        for _ in range(SUB):
            if not len(pos):
                break
            vel[:, 1] += g * dt
            pos += vel * dt
            # clous
            dx = pos[:, None, 0] - pegs[None, :, 0]; dy = pos[:, None, 1] - pegs[None, :, 1]
            d2 = dx * dx + dy * dy
            bi, pj = np.nonzero(d2 < (br + pr) ** 2)
            if len(bi):
                dd = np.sqrt(d2[bi, pj]) + 1e-6
                nx, ny = dx[bi, pj] / dd, dy[bi, pj] / dd
                pos[bi, 0] = pegs[pj, 0] + nx * (br + pr); pos[bi, 1] = pegs[pj, 1] + ny * (br + pr)
                vn = vel[bi, 0] * nx + vel[bi, 1] * ny
                m = vn < 0
                vel[bi[m], 0] -= 1.55 * vn[m] * nx[m]; vel[bi[m], 1] -= 1.55 * vn[m] * ny[m]
                vel[bi[m], 0] += rng.normal(0, 45, m.sum()) * S
                peg_flash[pj] = 1.0
                peg_hits += int(m.sum())
            # billes entre elles
            n = len(pos)
            if n > 1:
                ddx = pos[:, None, 0] - pos[None, :, 0]; ddy = pos[:, None, 1] - pos[None, :, 1]
                dd2 = ddx * ddx + ddy * ddy
                iu, ju = np.nonzero(np.triu((dd2 < (2 * br) ** 2) & (dd2 > 1e-9), 1))
                if len(iu):
                    dd = np.sqrt(dd2[iu, ju]); nx = ddx[iu, ju] / dd; ny = ddy[iu, ju] / dd
                    ov = (2 * br - dd) * 0.5
                    np.add.at(pos[:, 0], iu, nx * ov); np.add.at(pos[:, 1], iu, ny * ov)
                    np.add.at(pos[:, 0], ju, -nx * ov); np.add.at(pos[:, 1], ju, -ny * ov)
            # murs
            m = pos[:, 0] < x0 + br; pos[m, 0] = x0 + br; vel[m, 0] = np.abs(vel[m, 0]) * 0.6
            m = pos[:, 0] > x1 - br; pos[m, 0] = x1 - br; vel[m, 0] = -np.abs(vel[m, 0]) * 0.6
            vel[:, 0] = np.clip(vel[:, 0], -500 * S, 500 * S)
            # arrivée dans une case
            arr = pos[:, 1] > bin_top + 40 * S
            if arr.any():
                for i in np.nonzero(arr)[0]:
                    b = int(np.clip((pos[i, 0] - x0) // bw, 0, nb - 1))
                    landed_now.append((b, pos[i, 0]))
                keep = ~arr
                pos, vel, hues = pos[keep], vel[keep], hues[keep]
        for b, x in landed_now:
            mult = bins[b]
            total_landed += 1
            bin_count[b] += 1
            bin_flash[b] = 1.0
            if mult == 0 and count() < 1.5:
                mult = 1          # la toute dernière bille est épargnée
            queue += mult
            floaters.append([x, bin_top - 10 * S, 0.0, "☠" if mult == 0 else f"×{mult}", mult])
        if landed_now and t - last_note > 0.06:
            best = max(bins[b] for b, _ in landed_now)
            if best == 0:
                mx.add(t, mx.thud(55), 0.35)
            else:
                mx.add(t, mx.note(mx.scale_freq(min(int(math.log2(best + 1) * 2.5), 9), octaves=2)), 0.4)
            last_note = t
        if peg_hits and t - last_tick > 0.05:
            mx.add(t, mx.thud(int(rng.choice([140, 160, 180]))), 0.05 * min(peg_hits, 6) ** 0.5); last_tick = t

        # ---------------- rendu
        img = bgimg.copy()
        dr = ImageDraw.Draw(img, "RGBA")
        hc = hsv(hue, 0.55, 1)
        for (x, y), fl in zip(pegs, peg_flash):
            rr = pr * (1 + 0.5 * fl)
            dr.ellipse([x - rr - 5 * S, y - rr - 5 * S, x + rr + 5 * S, y + rr + 5 * S], fill=(*hc, int(30 + 80 * fl)))
            dr.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 255, 255, int(170 + 85 * fl)))
        peg_flash *= 0.8
        for b in range(nb):
            bx0 = x0 + b * bw
            mult = bins[b]
            if mult == 0:
                base = (200, 40, 50)
            else:
                base = hsv(0.33 - min(mult, 20) / 20 * 0.33, 0.75, 0.9)     # vert -> rouge selon la valeur
            fl = bin_flash[b]
            colr = tuple(min(255, int(v * 0.55 + 120 * fl)) for v in base)
            dr.rounded_rectangle([bx0 + 3 * S, bin_top, bx0 + bw - 3 * S, bin_bot], 10 * S, fill=(*colr, 255), outline=(*base, 255), width=max(1, int(3 * S)))
            lab = "☠" if mult == 0 else f"×{mult}"
            tw = dr.textlength(lab, font=f_bin)
            dr.text((bx0 + (bw - tw) / 2, bin_top + 30 * S), lab, font=f_bin, fill=(255, 255, 255, 240))
            cnt = fmt(bin_count[b])
            fs = ImageFont.truetype(FONT, int(22 * S))
            tw = dr.textlength(cnt, font=fs)
            dr.text((bx0 + (bw - tw) / 2, bin_bot - 40 * S), cnt, font=fs, fill=(255, 255, 255, 160))
        bin_flash *= 0.85
        for i in range(len(pos)):
            key = round(hues[i], 2)
            if key not in sprites:
                sprites[key] = ball_sprite(br, hsv(key, 0.55, 1))
            sp = sprites[key]
            img.paste(sp, (int(pos[i, 0] - sp.width / 2), int(pos[i, 1] - sp.height / 2)), sp)
        keep_f = []
        for f in floaters[-40:]:
            f[2] += 1 / FPS
            if f[2] < 0.7:
                y = f[1] - f[2] * 120 * S
                fs = ImageFont.truetype(FONT, int((30 + 3 * min(f[4], 10)) * S))
                colf = (255, 80, 80) if f[4] == 0 else (255, 230, 120)
                dr.text((f[0] - 20 * S, y), f[3], font=fs, fill=(*colf, int(255 * (1 - f[2] / 0.7))))
                keep_f.append(f)
        floaters = keep_f
        big = fmt(count())
        tw = dr.textlength(big, font=f_big)
        dr.text(((W - tw) / 2, 140 * S), big, font=f_big, fill=(255, 255, 255, 255))
        subl = c.get("subtitle", "")
        tw = dr.textlength(subl, font=f_mid)
        dr.text(((W - tw) / 2, 320 * S), subl, font=f_mid, fill=(*hc, 235))
        dr.rounded_rectangle([W * .1, H - 70 * S, W * .9, H - 58 * S], 6 * S, fill=(255, 255, 255, 40))
        dr.rounded_rectangle([W * .1, H - 70 * S, W * .1 + W * .8 * (fi / n_frames), H - 58 * S], 6 * S, fill=(*hc, 255))
        enc.frame(img)
        if fi % 300 == 0:
            print(f"frame {fi}/{n_frames} count={count():.0f} live={len(pos)}", flush=True)
    mx.pad([mx.root / 2, mx.root * 0.75])
    enc.finish(mx, duration)
    print("OK", out, "count", count())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="multi")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--duration", type=float, default=70)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", default="out/plinko.mp4")
    a = ap.parse_args()
    run(dict(mode=a.mode, subtitle="1 BALL → HOW MANY?"), a.seed, a.duration, a.scale, a.out)
