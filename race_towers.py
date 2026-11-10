"""Template « expérience » : course entre 2 à 4 tours à creuser.

Chaque côté a une règle appliquée quand une bille touche l'étage courant.
Chaque bille inflige des dégâts = nombre de billes qu'elle représente.
Les étages ont une résistance croissante (10, 100, 1K, ...). Premier en bas = gagnant.

Usage: python3 race_towers.py --exp x2_vs_half --seed 1 --out out/race.mp4
"""
import argparse, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from common import FPS, FONT, Mixer, Encoder, ball_sprite, gradient_bg, hsv, fmt

SUB = 3
CAP = 140            # billes réellement simulées par côté (au-delà, une bille "pèse" plusieurs)

# ---------------------------------------------------------------- expériences
# rule: comment une bille réagit quand elle touche l'étage
EXPERIMENTS = {
    "x2_vs_half": dict(
        title="×2 vs ÷2", question="WHO REACHES THE BOTTOM FIRST?",
        lanes=[dict(start=1, rule="double", sub="×2 ON EVERY HIT", hue=0.52),
               dict(start=10_000_000, rule="half", sub="÷2 ON EVERY HIT", hue=0.93)],
        floors=[10, 100, 1_000, 10_000, 100_000, 1_000_000, 10_000_000, 50_000_000]),
    "plus1_vs_x2": dict(
        title="+1 vs ×2", question="CAN +1 BEAT ×2 WITH A HEAD START?",
        lanes=[dict(start=50, rule="plus1", sub="+1 ON EVERY HIT", hue=0.12),
               dict(start=1, rule="double", sub="×2 ON EVERY HIT", hue=0.55)],
        floors=[10, 100, 1_000, 5_000, 20_000, 100_000, 500_000]),
    "x3_fragile_vs_x2": dict(
        title="×3 (dies 50%) vs ×2", question="RISKY ×3 OR SAFE ×2?",
        lanes=[dict(start=1, rule="triple_fragile", sub="×3 BUT 50% DIE", hue=0.30),
               dict(start=1, rule="double", sub="×2 ON EVERY HIT", hue=0.80)],
        floors=[10, 100, 1_000, 10_000, 100_000, 1_000_000]),
    "battle_royale": dict(
        title="4 RULES, 1 WINNER", question="WHICH RULE WINS THE RACE?",
        lanes=[dict(start=100, rule="plus1", sub="+1 / HIT", hue=0.12),
               dict(start=1, rule="double", sub="×2 / HIT", hue=0.55),
               dict(start=1, rule="triple_fragile", sub="×3 · 50% DIE", hue=0.30),
               dict(start=1_000_000, rule="half", sub="÷2 / HIT", hue=0.93)],
        floors=[10, 100, 1_000, 10_000, 100_000, 1_000_000, 5_000_000]),
    "risk_ladder": dict(
        title="HOW MUCH RISK?", question="SAFE ×2, ×3 OR ×4?",
        lanes=[dict(start=1, rule="double", sub="×2 · SAFE", hue=0.55),
               dict(start=1, rule="triple_fragile", sub="×3 · 50% DIE", hue=0.12),
               dict(start=1, rule="quad_fragile", sub="×4 · 75% DIE", hue=0.95)],
        floors=[10, 100, 1_000, 10_000, 100_000, 1_000_000]),
    "plus10_vs_x15": dict(
        title="+10 vs ×1.5", question="SLOW AND STEADY OR EXPONENTIAL?",
        lanes=[dict(start=100, rule="plus10", sub="+10 ON EVERY HIT", hue=0.08),
               dict(start=1, rule="x1_5", sub="×1.5 ON EVERY HIT", hue=0.62)],
        floors=[10, 100, 1_000, 5_000, 20_000, 100_000, 500_000]),
}


def nice(x):
    """Arrondit à un nombre « joli » : 1, 1.5, 2, 2.5, 3, 4, 5, 6, 7.5 × 10^k."""
    if x < 10:
        return max(1, int(round(x)))
    e = 10 ** math.floor(math.log10(x))
    m = min((1, 1.5, 2, 2.5, 3, 4, 5, 6, 7.5, 10), key=lambda v: abs(v * e - x))
    return int(m * e)


class Side:
    def __init__(self, cfg, x0, x1, top, floor_tops, floor_h, S, rng, hpmul):
        self.cfg, self.x0, self.x1, self.top = cfg, x0, x1, top
        self.floor_tops, self.floor_h = floor_tops, floor_h
        self.hp = [float(nice(h * hpmul)) for h in EXP["floors"]]
        self.hp_max = list(self.hp)
        self.level = 0
        self.S, self.rng = S, rng
        self.r = 10 * S
        start = nice(cfg["start"] * hpmul) if cfg["start"] >= 1000 else cfg["start"]
        self.start = start
        n = min(start, CAP)
        self.w = np.full(n, start / n)
        self.pos = np.column_stack([rng.uniform(x0 + self.r, x1 - self.r, n), rng.uniform(top + 10 * S, top + 120 * S, n)])
        self.vel = np.column_stack([rng.uniform(-220, 220, n) * S, rng.uniform(0, 80, n) * S])
        self.finished_at = None
        self.cd = np.zeros(n)
        self.hits_this_frame = 0
        self.breaks = []            # temps de casse
        self.debris = []
        self.flash = 0.0

    @property
    def count(self):
        return float(self.w.sum())

    def floor_y(self):
        return self.floor_tops[self.level] if self.level < len(self.floor_tops) else None

    def step(self, dt, g, t):
        if len(self.pos) == 0:
            return
        S, r = self.S, self.r
        self.vel[:, 1] += g * dt
        self.pos += self.vel * dt
        self.cd -= dt
        # murs latéraux
        lo, hi = self.x0 + r, self.x1 - r
        m = self.pos[:, 0] < lo; self.pos[m, 0] = lo; self.vel[m, 0] = np.abs(self.vel[m, 0])
        m = self.pos[:, 0] > hi; self.pos[m, 0] = hi; self.vel[m, 0] = -np.abs(self.vel[m, 0])
        m = self.pos[:, 1] < self.top + r; self.pos[m, 1] = self.top + r; self.vel[m, 1] = np.abs(self.vel[m, 1])
        # collisions bille-bille
        n = len(self.pos)
        if n > 1:
            dx = self.pos[:, None, 0] - self.pos[None, :, 0]
            dy = self.pos[:, None, 1] - self.pos[None, :, 1]
            d2 = dx * dx + dy * dy
            iu, ju = np.nonzero(np.triu((d2 < (2 * r) ** 2) & (d2 > 1e-9), 1))
            if len(iu):
                dd = np.sqrt(d2[iu, ju]); nx = dx[iu, ju] / dd; ny = dy[iu, ju] / dd
                ov = (2 * r - dd) * 0.5
                np.add.at(self.pos[:, 0], iu, nx * ov); np.add.at(self.pos[:, 1], iu, ny * ov)
                np.add.at(self.pos[:, 0], ju, -nx * ov); np.add.at(self.pos[:, 1], ju, -ny * ov)
                rvn = (self.vel[iu, 0] - self.vel[ju, 0]) * nx + (self.vel[iu, 1] - self.vel[ju, 1]) * ny
                imp = -rvn * (rvn < 0)
                np.add.at(self.vel[:, 0], iu, imp * nx); np.add.at(self.vel[:, 1], iu, imp * ny)
                np.add.at(self.vel[:, 0], ju, -imp * nx); np.add.at(self.vel[:, 1], ju, -imp * ny)
        sp = np.hypot(self.vel[:, 0], self.vel[:, 1])
        vmax = 2200 * S
        fast = sp > vmax
        if fast.any():
            self.vel[fast] *= (vmax / sp[fast])[:, None]
        bad = ~np.isfinite(self.pos).all(1) | ~np.isfinite(self.vel).all(1)
        if bad.any():
            self.pos[bad] = [(self.x0 + self.x1) / 2, self.top + 40 * S]; self.vel[bad] = 0
        fy = self.floor_y()
        if fy is None:
            # fond atteint : sol final, simples rebonds
            gy = self.floor_tops[-1] + self.floor_h - r
            m = (self.pos[:, 1] > gy) & (self.vel[:, 1] > 0)
            self.pos[m, 1] = gy; self.vel[m, 1] *= -0.85
            return
        below = self.pos[:, 1] > fy - r
        bounce = np.nonzero(below & (self.vel[:, 1] > 0) & (self.cd > 0))[0]
        if len(bounce):   # contact déjà compté : simple rebond
            self.pos[bounce, 1] = fy - r
            self.vel[bounce, 1] = -np.abs(self.vel[bounce, 1])
        hit = np.nonzero(below & (self.vel[:, 1] > 0) & (self.cd <= 0))[0]
        if not len(hit):
            return
        hb = fy - self.top - 2 * r
        self.cd[hit] = 0.6 * 2 * math.sqrt(2 * hb / g)
        # rebond : relancé pour remonter à peu près en haut du puits
        self.pos[hit, 1] = fy - r
        h = hb * self.rng.uniform(0.8, 1.0, len(hit))
        self.vel[hit, 1] = -np.sqrt(2 * g * h)
        self.vel[hit, 0] += self.rng.normal(0, 60 * S, len(hit))
        dmg = float(self.w[hit].sum())
        self.hits_this_frame += len(hit)
        self.apply_rule(hit)
        self.hp[self.level] -= dmg
        self.flash = 1.0
        if self.hp[self.level] <= 0:
            self.hp[self.level] = 0
            self.breaks.append(t)
            self.spawn_debris(self.level)
            self.level += 1
            if self.level >= len(self.floor_tops):
                self.finished_at = t

    def apply_rule(self, hit):
        rule, rng = self.cfg["rule"], self.rng
        if rule == "double":
            self.multiply(hit, 2)
        elif rule == "half":
            self.w[hit] /= 2
            dead = self.w < 0.999
            self.keep(~dead)
        elif rule == "plus1":
            # chaque contact ajoute 1 bille au total
            room = CAP - len(self.pos)
            k = min(room, len(hit))
            if k > 0:
                self.add(hit[:k])
            if len(hit) > k:
                self.w += (len(hit) - k) / len(self.w)
        elif rule in ("plus10",):
            n_add = 10 * len(hit)
            room = CAP - len(self.pos)
            k = min(room, n_add)
            if k > 0:
                self.add(np.resize(hit, k))
            if n_add > k:
                self.w += (n_add - k) / len(self.w)
        elif rule == "x1_5":
            lucky = hit[rng.random(len(hit)) < 0.5]
            self.multiply(lucky, 2)
        elif rule in ("triple_fragile", "quad_fragile"):
            k_mul, p_die = (3, 0.5) if rule == "triple_fragile" else (4, 0.75)
            alive = rng.random(len(hit)) >= p_die
            dead_idx = hit[~alive]
            self.multiply(hit[alive], k_mul)
            mask = np.ones(len(self.pos), bool); mask[dead_idx] = False
            if mask.sum() == 0:
                mask[dead_idx[0]] = True   # on garde toujours au moins une bille
            self.keep(mask)

    def keep(self, mask):
        self.pos, self.vel, self.w, self.cd = self.pos[mask], self.vel[mask], self.w[mask], self.cd[mask]

    def add(self, idx):
        p = self.pos[idx].copy(); v = self.vel[idx].copy(); v[:, 0] *= -1
        self.pos = np.vstack([self.pos, p]); self.vel = np.vstack([self.vel, v]); self.w = np.concatenate([self.w, self.w[idx]]); self.cd = np.concatenate([self.cd, self.cd[idx]])

    def multiply(self, idx, k):
        """Multiplie la population des billes idx par k (clones réels tant qu'on a de la place, sinon poids)."""
        if not len(idx):
            return
        room = CAP - len(self.pos)
        clones_needed = len(idx) * (k - 1)
        if clones_needed <= room:
            for _ in range(k - 1):
                self.add(idx)
                p = self.pos[-len(idx):]; p[:, 0] += self.rng.uniform(-6, 6, len(idx)) * self.S
        else:
            self.w[idx] *= k

    def spawn_debris(self, lvl):
        y0 = self.floor_tops[lvl]
        for _ in range(40):
            self.debris.append([self.rng.uniform(self.x0, self.x1), self.rng.uniform(y0, y0 + self.floor_h),
                                self.rng.normal(0, 250) * self.S, self.rng.uniform(-500, -100) * self.S,
                                self.rng.uniform(8, 22) * self.S, 1.4])


def simulate(seed, duration, scale, hpmul, render=None):
    """Simule (et rend si render est fourni). Retourne le temps d'arrivée du gagnant."""
    rng = np.random.default_rng(seed)
    S = scale
    W, H = int(1080 * S), int(1920 * S)
    top = 520 * S
    n_fl = len(EXP["floors"])
    fbot = 1860 * S
    fstart = 880 * S
    fh = (fbot - fstart) / n_fl
    ftops = [fstart + i * fh for i in range(n_fl)]
    lanes = EXP["lanes"]
    nl = len(lanes)
    gap = 40 * S if nl == 2 else 26 * S
    lw = (980 * S - gap * (nl - 1)) / nl
    sides = [Side(cfg, 50 * S + i * (lw + gap), 50 * S + i * (lw + gap) + lw, top, ftops, fh, S,
                  np.random.default_rng(seed * 7 + 1 + i), hpmul) for i, cfg in enumerate(lanes)]
    g = 2000 * S
    dt = 1 / (FPS * SUB)
    n_frames = int(duration * FPS)
    winner, win_t = None, None
    for fi in range(n_frames):
        t = fi / FPS
        for sd in sides:
            sd.hits_this_frame = 0
        for _ in range(SUB):
            for sd in sides:
                sd.step(dt, g, t)
        if winner is None:
            for i, side in enumerate(sides):
                if side.finished_at is not None:
                    winner, win_t = i, side.finished_at
                    break
            if winner is None and render is None and t > duration:
                break
        if render is not None:
            render(fi, t, sides, winner, win_t)
        elif winner is not None:
            return win_t, winner
    return win_t, winner


def main():
    global EXP
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", default="x2_vs_half", choices=list(EXPERIMENTS))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--duration", type=float, default=70)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--finish", type=float, default=62.0, help="moment visé pour l'arrivée du gagnant")
    ap.add_argument("--out", default="out/race.mp4")
    a = ap.parse_args()
    EXP = EXPERIMENTS[a.exp]

    # ---- calibrage : hauteur de rebond (= rythme) ajustée pour que l'arrivée tombe vers --finish
    lo, hi = 0.02, 5000.0
    best = (1e9, 1.0)
    for it in range(14):
        bh = math.sqrt(lo * hi)  # multiplicateur de résistance
        wt, wn = simulate(a.seed, a.duration, a.scale, bh)
        print(f"calib {it}: hp_mul={bh:.4g} -> winner={wn} at {wt}", flush=True)
        err = abs(wt - a.finish) if wt is not None else 1e6
        if err < best[0]:
            best = (err, bh)
        if wt is None or wt > a.finish:
            hi = bh
        else:
            lo = bh
        if err < 1.5:
            break
    hpmul = best[1]

    # ---- rendu
    S = a.scale
    W, H = int(1080 * S), int(1920 * S)
    bg = gradient_bg(W, H, (8, 6, 22), (20, 8, 40))
    fb = lambda px: ImageFont.truetype(FONT, int(px * S))
    nl = len(EXP["lanes"])
    k_ = {2: 1.0, 3: 0.72, 4: 0.56}[nl]
    f_title, f_q, f_cnt, f_lab, f_sub, f_hp, f_win = fb(92), fb(38), fb(84 * k_), fb(36 * max(k_, .7)), fb(28 * max(k_, .75)), fb(40 * max(k_, .7)), fb(64)
    enc = Encoder(a.out, W, H)
    mx = Mixer(a.duration, root=110.0)
    rng = np.random.default_rng(a.seed + 99)
    sprites = {}
    shake = [0.0]
    last_note = [-1.0] * nl
    note_idx = [3 * i for i in range(nl)]
    state = {"breaks": [0] * nl, "won": False}
    hues = [l["hue"] for l in EXP["lanes"]]

    def draw_side(dr, img, side, name, t):
        hue = hues[name]
        c_main = hsv(hue, 0.7, 1.0)
        # puits
        dr.rounded_rectangle([side.x0 - 6 * S, side.top - 6 * S, side.x1 + 6 * S, side.floor_tops[-1] + side.floor_h + 6 * S],
                             14 * S, outline=(*c_main, 120), width=max(1, int(4 * S)))
        # étages restants
        for i in range(side.level, len(side.floor_tops)):
            y0 = side.floor_tops[i]; y1 = y0 + side.floor_h - 6 * S
            frac = side.hp[i] / side.hp_max[i]
            base = hsv(hue + 0.015 * (i - 3), 0.55 + 0.03 * i, 0.30 + 0.05 * (i % 2) + 0.02 * i)
            fl = side.flash if i == side.level else 0
            col = tuple(min(255, int(c + 70 * fl)) for c in base)
            dr.rounded_rectangle([side.x0, y0, side.x1, y1], 8 * S, fill=(*col, 255))
            if i == side.level and frac < 1:
                # barre de vie de l'étage courant
                dr.rounded_rectangle([side.x0 + 10 * S, y1 - 16 * S, side.x0 + 10 * S + (side.x1 - side.x0 - 20 * S) * frac, y1 - 8 * S],
                                     4 * S, fill=(*c_main, 255))
            txt = fmt(math.ceil(side.hp[i]))
            tw = dr.textlength(txt, font=f_hp)
            dr.text(((side.x0 + side.x1 - tw) / 2, (y0 + y1) / 2 - 26 * S), txt, font=f_hp, fill=(255, 255, 255, 235))
        side.flash = max(0, side.flash - 0.25)
        # billes
        key = name
        if key not in sprites:
            sprites[key] = ball_sprite(side.r, hsv(hue, 0.55, 1.0))
        sp = sprites[key]
        for (x, y) in side.pos:
            if y < H + 30 * S:
                img.paste(sp, (int(x - sp.width / 2), int(y - sp.height / 2)), sp)
        # débris
        keep = []
        for d in side.debris:
            d[3] += 1500 * S / FPS; d[0] += d[2] / FPS; d[1] += d[3] / FPS; d[5] -= 1 / FPS
            if d[5] > 0 and d[1] < H:
                c = hsv(hue, 0.5, 0.8)
                dr.rectangle([d[0], d[1], d[0] + d[4], d[1] + d[4] * 0.7], fill=(*c, int(255 * min(1, d[5]))))
                keep.append(d)
        side.debris = keep
        # compteur + étiquettes
        cx = (side.x0 + side.x1) / 2
        txt = fmt(side.count)
        tw = dr.textlength(txt, font=f_cnt)
        dr.text((cx - tw / 2, 300 * S), txt, font=f_cnt, fill=(*c_main, 255))
        label = f"{fmt(side.start)} BALL" + ("S" if side.start > 1 else "")
        for txt, f, y, a_ in ((label, f_lab, 248 * S, 220), (side.cfg["sub"], f_sub, 400 * S, 200)):
            tw = dr.textlength(txt, font=f)
            dr.text((cx - tw / 2, y), txt, font=f, fill=(255, 255, 255, a_))

    def render(fi, t, sides, winner, win_t):
        # sons
        for name, side in enumerate(sides):
            if side.hits_this_frame and t - last_note[name] > 0.09:
                note_idx[name] += 1
                f = mx.scale_freq(note_idx[name] + 2 * side.level, octaves=2)
                mx.add(t, mx.note(f), 0.22 + 0.05 * min(side.hits_this_frame, 4))
                last_note[name] = t
        for k, side in enumerate(sides):
            while len(side.breaks) > state["breaks"][k]:
                mx.add(side.breaks[state["breaks"][k]], mx.boom(), 0.3 / max(1, nl - 1) ** 0.5)
                state["breaks"][k] += 1
                shake[0] = 0.6
        if winner and not state["won"]:
            state["won"] = True
            for j, semi in enumerate([0, 4, 7, 12, 16]):
                mx.add(t + 0.09 * j, mx.note(mx.root * 2 * 2 ** (semi / 12)), 0.5)
        scene = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(scene, "RGBA")
        for i, sd in enumerate(sides):
            draw_side(dr, scene, sd, i, t)
        # titre
        tw = dr.textlength(EXP["title"], font=f_title)
        dr.text(((W - tw) / 2, 70 * S), EXP["title"], font=f_title, fill=(255, 255, 255, 255))
        q = EXP["question"]
        tw = dr.textlength(q, font=f_q)
        dr.text(((W - tw) / 2, 185 * S), q, font=f_q, fill=(255, 220, 120, 230))
        # gagnant
        if winner is not None:
            side = sides[winner]
            cx = (side.x0 + side.x1) / 2
            pulse = 1 + 0.05 * math.sin((t - win_t) * 8)
            fw = ImageFont.truetype(FONT, int(64 * S * pulse * (1 if nl == 2 else 0.62)))
            tw = dr.textlength("WINNER!", font=fw)
            dr.rounded_rectangle([cx - tw / 2 - 20 * S, 1080 * S, cx + tw / 2 + 20 * S, 1180 * S], 20 * S, fill=(255, 210, 60, 240))
            dr.text((cx - tw / 2, 1092 * S), "WINNER!", font=fw, fill=(30, 10, 40, 255))
        # tremblement d'écran
        img = bg.copy()
        dx = dy = 0
        if shake[0] > 0:
            dx, dy = (rng.normal(0, 14 * S * shake[0], 2)).astype(int)
            shake[0] = max(0, shake[0] - 0.12)
        img.paste(scene, (int(dx), int(dy)), scene)
        enc.frame(img.convert("RGB"))
        if fi % 300 == 0:
            print(f"frame {fi}  " + "  ".join(f"{fmt(sd.count)} lvl{sd.level}" for sd in sides), flush=True)

    win_t, winner = simulate(a.seed, a.duration, a.scale, hpmul, render=render)
    mx.pad([55.0, 82.4])
    enc.finish(mx, a.duration)
    print("OK", a.out, "winner:", winner, "at", win_t)
    return winner, win_t


if __name__ == "__main__":
    main()
