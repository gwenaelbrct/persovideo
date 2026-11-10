"""Template : murs qui se referment. Une bille touchée par un mur qui avance est doublée.

Usage: python3 crusher_walls.py --seed 1 --out out/walls.mp4
"""
import argparse, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from common import FPS, FONT, Mixer, Encoder, ball_sprite, gradient_bg, hsv

SUB = 4
PALETTES = [
    dict(bg=((10, 6, 20), (30, 8, 30)), wall=0.98, hues=(0.55, 0.62, 0.70, 0.80)),
    dict(bg=((4, 10, 20), (6, 24, 40)), wall=0.08, hues=(0.48, 0.52, 0.58, 0.45)),
    dict(bg=((14, 6, 4), (36, 14, 6)), wall=0.75, hues=(0.08, 0.12, 0.02, 0.95)),
]


def run(seed, duration, scale, out, cap=360):
    rng = np.random.default_rng(seed)
    pal = PALETTES[seed % len(PALETTES)]
    four = bool(seed % 2)                      # 2 murs (gauche/droite) ou 4 murs
    S = scale
    W, H = int(1080 * S), int(1920 * S)
    cx, cy = W / 2, H * 0.56
    HW, HH = 470 * S, 620 * S                   # demi-taille de l'arène ouverte
    close_frac = 0.42                           # fermeture maximale (fraction de la demi-taille)
    period = rng.uniform(4.5, 6.0)
    br = 12 * S
    vmin, vmax = 450 * S, 1300 * S
    dt = 1 / (FPS * SUB)
    n_frames = int(duration * FPS)

    pos = np.array([[cx, cy]]); vel = np.array([[rng.uniform(-1, 1) * 500 * S, -400 * S]])
    col = np.array([0]); cd = np.array([0.0])
    nh = len(pal["hues"])
    sprites = [ball_sprite(br, hsv(h, 0.6, 1)) for h in pal["hues"]]
    bg = gradient_bg(W, H, *pal["bg"])
    f_big, f_mid = ImageFont.truetype(FONT, int(150 * S)), ImageFont.truetype(FONT, int(44 * S))
    enc = Encoder(out, W, H)
    mx = Mixer(duration, root=float(rng.choice([98.0, 110.0, 116.5])))
    last_note, note_i, last_thud = -1.0, 0, -1.0
    flashes = []                                # [x, y, age, hue]
    wall_flash = 0.0

    def inset(tt):
        # 0 = ouvert, 1 = fermé ; montée douce, pause, retour
        ph = (tt % period) / period
        return close_frac * (0.5 - 0.5 * math.cos(2 * math.pi * min(ph / 0.8, 1)))

    for fi in range(n_frames):
        t = fi / FPS
        target = cap ** min(t / (0.85 * duration), 1.0)
        allow = len(pos) < target * 1.15
        doubled = 0
        for k in range(SUB):
            tt = t + k * dt
            s_now, s_next = inset(tt), inset(tt + dt)
            closing = s_next > s_now
            wspeed = (s_next - s_now) / dt
            xl, xr = cx - HW * (1 - s_now), cx + HW * (1 - s_now)
            if four:
                yt, yb = cy - HH * (1 - s_now), cy + HH * (1 - s_now)
            else:
                yt, yb = cy - HH, cy + HH
            sp = np.hypot(vel[:, 0], vel[:, 1])[:, None]
            vel *= np.clip(vmin / np.maximum(sp, 1e-6), 1.0, 1.03)
            vel *= np.where(sp > vmax, 0.99, 1.0)
            pos += vel * dt
            cd -= dt
            # collisions bille-bille
            n = len(pos)
            if n > 1:
                dx = pos[:, None, 0] - pos[None, :, 0]; dy = pos[:, None, 1] - pos[None, :, 1]
                d2 = dx * dx + dy * dy
                iu, ju = np.nonzero(np.triu((d2 < (2 * br) ** 2) & (d2 > 1e-9), 1))
                if len(iu):
                    dd = np.sqrt(d2[iu, ju]); nx = dx[iu, ju] / dd; ny = dy[iu, ju] / dd
                    ov = (2 * br - dd) * 0.5
                    np.add.at(pos[:, 0], iu, nx * ov); np.add.at(pos[:, 1], iu, ny * ov)
                    np.add.at(pos[:, 0], ju, -nx * ov); np.add.at(pos[:, 1], ju, -ny * ov)
                    rvn = (vel[iu, 0] - vel[ju, 0]) * nx + (vel[iu, 1] - vel[ju, 1]) * ny
                    imp = -rvn * (rvn < 0)
                    np.add.at(vel[:, 0], iu, imp * nx); np.add.at(vel[:, 1], iu, imp * ny)
                    np.add.at(vel[:, 0], ju, -imp * nx); np.add.at(vel[:, 1], ju, -imp * ny)
            # murs : rebond, et bille « écrasée » par un mur qui avance -> doublée
            crushed = np.zeros(len(pos), bool)
            push = HW * wspeed
            for axis, lo, hi, moving in ((0, xl, xr, True), (1, yt, yb, four)):
                m = pos[:, axis] < lo + br
                pos[m, axis] = lo + br; vel[m, axis] = np.abs(vel[m, axis]) + (push if moving and closing else 0)
                if moving and closing:
                    crushed |= m
                m = pos[:, axis] > hi - br
                pos[m, axis] = hi - br; vel[m, axis] = -np.abs(vel[m, axis]) - (push if moving and closing else 0)
                if moving and closing:
                    crushed |= m
            if crushed.any() and fi % 2 == 0 and t - last_thud > 0.12:
                mx.add(tt, mx.thud(85), 0.12); last_thud = t
            idx = np.nonzero(crushed & (cd <= 0))[0]
            if allow and len(idx):
                idx = idx[: max(0, min(len(idx), cap - len(pos)))]
                if len(idx):
                    cd[idx] = 0.8
                    newp = pos[idx] + rng.normal(0, 3 * S, (len(idx), 2))
                    newv = vel[idx] * [[-1, 1]] + rng.normal(0, 150 * S, (len(idx), 2))
                    newc = (col[idx] + 1) % nh
                    col[idx] = newc
                    pos = np.vstack([pos, newp]); vel = np.vstack([vel, newv])
                    col = np.concatenate([col, newc]); cd = np.concatenate([cd, np.full(len(idx), 0.8)])
                    for i in idx[:6]:
                        flashes.append([pos[i, 0], pos[i, 1], 0.0, int(col[i])])
                    doubled += len(idx)
                    wall_flash = 1.0
        if doubled and t - last_note > 0.1:
            note_i += 1
            mx.add(t, mx.note(mx.scale_freq(note_i, octaves=2)), 0.4)
            last_note = t

        # ---------- rendu ----------
        img = bg.copy()
        dr = ImageDraw.Draw(img, "RGBA")
        s_now = inset(t)
        xl, xr = cx - HW * (1 - s_now), cx + HW * (1 - s_now)
        yt, yb = (cy - HH * (1 - s_now), cy + HH * (1 - s_now)) if four else (cy - HH, cy + HH)
        wc = hsv(pal["wall"], 0.7, 1)
        # zone d'origine en pointillé
        dr.rectangle([cx - HW, cy - HH, cx + HW, cy + HH], outline=(*wc, 40), width=max(1, int(2 * S)))
        thick = 34 * S
        glow = int(60 + 120 * wall_flash)
        wall_flash = max(0, wall_flash - 0.15)
        walls = [(xl - thick, yt - thick, xl, yb + thick), (xr, yt - thick, xr + thick, yb + thick)]
        if four:
            walls += [(xl, yt - thick, xr, yt), (xl, yb, xr, yb + thick)]
        else:
            dr.rectangle([xl, yt - 6 * S, xr, yt], fill=(*wc, 120)); dr.rectangle([xl, yb, xr, yb + 6 * S], fill=(*wc, 120))
        for (a, b, c, d) in walls:
            for k in range(4, 0, -1):
                dr.rounded_rectangle([a - k * 6 * S, b - k * 6 * S, c + k * 6 * S, d + k * 6 * S], 10 * S, fill=(*wc, glow // (k + 2)))
            dr.rounded_rectangle([a, b, c, d], 8 * S, fill=(*wc, 255))
            # rayures « danger »
            for z in range(0, int(max(c - a, d - b)), int(40 * S)):
                if c - a < d - b:
                    dr.line([a, b + z, c, b + z + 20 * S], fill=(255, 255, 255, 90), width=max(1, int(6 * S)))
                else:
                    dr.line([a + z, b, a + z + 20 * S, d], fill=(255, 255, 255, 90), width=max(1, int(6 * S)))
        for i in range(len(pos)):
            sp = sprites[int(col[i])]
            img.paste(sp, (int(pos[i, 0] - sp.width / 2), int(pos[i, 1] - sp.height / 2)), sp)
        keep = []
        for f in flashes:
            f[2] += 1 / FPS
            if f[2] < 0.35:
                rr = br + f[2] * 120 * S
                c = hsv(pal["hues"][f[3]], 0.4, 1)
                dr.ellipse([f[0] - rr, f[1] - rr, f[0] + rr, f[1] + rr], outline=(*c, int(255 * (1 - f[2] / 0.35))), width=max(1, int(3 * S)))
                keep.append(f)
        flashes = keep
        txt = f"x{len(pos)}"
        tw = dr.textlength(txt, font=f_big)
        dr.text(((W - tw) / 2, 150 * S), txt, font=f_big, fill=(255, 255, 255, 255))
        sub = "CRUSHED = DOUBLED"
        tw = dr.textlength(sub, font=f_mid)
        dr.text(((W - tw) / 2, 330 * S), sub, font=f_mid, fill=(*wc, 230))
        dr.rounded_rectangle([W * .1, H - 90 * S, W * .9, H - 78 * S], 6 * S, fill=(255, 255, 255, 40))
        dr.rounded_rectangle([W * .1, H - 90 * S, W * .1 + W * .8 * (fi / n_frames), H - 78 * S], 6 * S, fill=(*wc, 255))
        enc.frame(img)
        if fi % 300 == 0:
            print(f"frame {fi}/{n_frames} balls={len(pos)}", flush=True)
    mx.pad([mx.root / 2, mx.root / 2 * 1.5])
    enc.finish(mx, duration)
    print("OK", out, "balls:", len(pos))
    return dict(final_count=len(pos), four_walls=four)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--duration", type=float, default=70)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", default="out/walls.mp4")
    a = ap.parse_args()
    run(a.seed, a.duration, a.scale, a.out)
