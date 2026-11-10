"""Moteur générique « arène » : formes, ouvertures, anneaux, trous noirs, effets au rebond.

Un concept = un dict de paramètres (voir concepts.py). Exemple :
    python3 arena.py --concept escape_circle --seed 3 --scale 0.5 --out out/a.mp4
"""
import argparse, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from common import FPS, FONT, Mixer, Encoder, ball_sprite, gradient_bg, hsv, fmt

PALETTES = [
    dict(bg=((8, 6, 24), (26, 8, 48)), ring=0.72, hues=(0.50, 0.58, 0.75, 0.88, 0.95)),
    dict(bg=((20, 6, 14), (48, 12, 30)), ring=0.02, hues=(0.0, 0.05, 0.10, 0.92, 0.85)),
    dict(bg=((4, 14, 10), (8, 36, 28)), ring=0.40, hues=(0.30, 0.38, 0.45, 0.15, 0.55)),
    dict(bg=((4, 8, 22), (6, 22, 44)), ring=0.55, hues=(0.52, 0.56, 0.60, 0.48, 0.65)),
    dict(bg=((18, 10, 2), (40, 22, 4)), ring=0.11, hues=(0.08, 0.12, 0.15, 0.03, 0.95)),
    dict(bg=((14, 4, 24), (6, 4, 12)), ring=0.83, hues=(0.80, 0.86, 0.92, 0.70, 0.50)),
    dict(bg=((2, 2, 2), (16, 16, 22)), ring=0.0, hues=(0.0, 0.12, 0.33, 0.55, 0.75)),   # arc-en-ciel sur noir
    dict(bg=((6, 16, 24), (2, 6, 10)), ring=0.47, hues=(0.47, 0.50, 0.95, 0.12, 0.60)),
]


class Ring:
    def __init__(self, shape, R, spin, gap_w=0.0, gap_at=0.0, theta=0.0):
        self.shape, self.R, self.spin, self.gap_w, self.gap_at, self.theta = shape, R, spin, gap_w, gap_at, theta
        self.alive = True

    def points(self, cx, cy, n=240):
        """Points du contour (pour le dessin), et masque « dans l'ouverture »."""
        a = np.linspace(0, 2 * math.pi, n, endpoint=False)
        if self.shape == "circle":
            r = np.full(n, self.R)
        else:
            k = self.shape
            loc = (a - self.theta) % (2 * math.pi / k) - math.pi / k
            r = self.R * math.cos(math.pi / k) / np.cos(loc)
        pts = np.column_stack([cx + r * np.cos(a), cy + r * np.sin(a)])
        return pts, self.in_gap_angle(a, 0)

    def in_gap_angle(self, ang, half_margin):
        if self.gap_w <= 0:
            return np.zeros_like(ang, bool)
        d = (ang - self.theta - self.gap_at + math.pi) % (2 * math.pi) - math.pi
        return np.abs(d) < self.gap_w / 2 - half_margin

    def collide(self, pos, vel, rad, cx, cy, margin):
        """Rebond à l'intérieur de l'anneau. Retourne le masque des billes qui ont touché la paroi."""
        rel = pos - (cx, cy)
        d = np.hypot(rel[:, 0], rel[:, 1]) + 1e-9
        ang = np.arctan2(rel[:, 1], rel[:, 0])
        gap = self.in_gap_angle(ang, rad / np.maximum(d, 1))
        hit = np.zeros(len(pos), bool)
        if self.shape == "circle":
            normals = [(rel / d[:, None], self.R - rad, d, np.ones(len(pos), bool))]
        else:
            k = self.shape
            normals = []
            apo, half = self.R * math.cos(math.pi / k), self.R * math.sin(math.pi / k)
            for i in range(k):
                phi = self.theta + (i + 0.5) * 2 * math.pi / k
                u = np.array([math.cos(phi), math.sin(phi)]); tv = np.array([-u[1], u[0]])
                pu = rel @ u; pt = rel @ tv
                normals.append((np.broadcast_to(u, rel.shape), apo - rad, pu, np.abs(pt) < half + rad))
        for u, lim, proj, along in normals:
            m = (proj > lim) & (proj < lim + 2 * rad + margin) & along & ~gap
            if not m.any():
                continue
            pos[m] -= u[m] * (proj[m] - lim[m] if np.ndim(lim) else proj[m] - lim)[:, None]
            r2 = pos[m] - (cx, cy)
            vw = self.spin * np.column_stack([-r2[:, 1], r2[:, 0]])
            vn = ((vel[m] - vw) * u[m]).sum(1)
            out = vn > 0
            vel_m = vel[m]
            vel_m -= (2 * vn * out)[:, None] * u[m]
            vel[m] = vel_m
            hit[np.nonzero(m)[0][out]] = True
        return hit

    def outside(self, pos, rad, cx, cy):
        rel = pos - (cx, cy)
        if self.shape == "circle":
            return np.hypot(rel[:, 0], rel[:, 1]) > self.R + rad
        k = self.shape
        apo = self.R * math.cos(math.pi / k)
        o = np.zeros(len(pos), bool)
        for i in range(k):
            phi = self.theta + (i + 0.5) * 2 * math.pi / k
            o |= rel @ np.array([math.cos(phi), math.sin(phi)]) > apo + rad
        return o


def run(c, seed, duration, scale, out):
    """c : dict du concept."""
    rng = np.random.default_rng(seed)
    pal = PALETTES[c.get("palette", seed) % len(PALETTES)]
    S = scale
    W, H = int(1080 * S), int(1920 * S)
    cx, cy = W / 2, H * 0.55
    sub = c.get("sub", 4)
    dt = 1 / (FPS * sub)
    n_frames = int(duration * FPS)
    g = c.get("gravity", 900) * S
    vmin, vmax = c.get("vmin", 500) * S, c.get("vmax", 1500) * S
    r0 = c.get("ball_r", 13) * S
    cap = c.get("cap", 350)
    spin_dir = rng.choice([-1, 1])

    # ---- anneaux
    rings = []
    if c.get("rings"):
        nr = c["rings"]
        Rin, Rout = c.get("ring_in", 90) * S, c.get("ring_out", 470) * S
        for i in range(nr):
            R = Rin + (Rout - Rin) * i / max(nr - 1, 1)
            sp = spin_dir * c.get("ring_spin", 0.9) * (1 if i % 2 == 0 else -1) * (1 + 0.3 * rng.random())
            rings.append(Ring(c.get("shape", "circle"), R, sp, gap_w=c.get("ring_gap", 0.55), gap_at=rng.uniform(0, 2 * math.pi)))
    else:
        rings.append(Ring(c.get("shape", "circle"), c.get("size", 450) * S, spin_dir * c.get("spin", 0.35),
                          gap_w=c.get("gap", 0.0), gap_at=rng.uniform(0, 2 * math.pi)))
    holes = [dict(h) for h in c.get("holes", [])]
    for h in holes:
        h["phase"] = rng.uniform(0, 2 * math.pi); h["w"] = h.get("w", 0.5) * rng.choice([-1, 1])

    # ---- billes
    teams = c.get("teams")
    n0 = c.get("start", 1)
    pos = np.column_stack([cx + rng.uniform(-60, 60, n0) * S, cy + rng.uniform(-60, 60, n0) * S])
    if c.get("rings"):
        pos[:] = (cx, cy)
    ang0 = rng.uniform(0, 2 * math.pi, n0)
    vel = np.column_stack([np.cos(ang0), np.sin(ang0)]) * vmin * 1.1
    rad = np.full(n0, r0)
    col = (np.arange(n0) % 2) if teams else np.zeros(n0, int)
    cd = np.zeros(n0)
    trail_pts = []          # (x, y, hue)
    hist = []               # positions récentes (traînée de vitesse)
    escaped = []            # billes sorties qui tombent
    particles = []
    pulses = []
    stats = dict(bounces=0, broken=0, escapes=0)

    bg = gradient_bg(W, H, *pal["bg"])
    f_big, f_mid, f_small = (ImageFont.truetype(FONT, int(p * S)) for p in (140, 44, 34))
    enc = Encoder(out, W, H)
    mx = Mixer(duration, root=float(rng.choice([98.0, 110.0, 123.5, 130.8])))
    note_i, last_note, last_thud = 0, -1.0, -1.0
    sprites = {}

    def sprite(r, hue_idx):
        key = (int(r), hue_idx)
        if key not in sprites:
            hh = pal["hues"][hue_idx % len(pal["hues"])] if not teams else (0.0, 0.58)[hue_idx]
            sprites[key] = ball_sprite(max(2, int(r)), hsv(hh, 0.62, 1.0), glow=1.6 if r > 40 * S else 2.2)
        return sprites[key]

    def play_note(t, vol=0.4):
        nonlocal note_i, last_note
        if t - last_note > 0.07:
            note_i += 1
            mx.add(t, mx.note(mx.scale_freq(note_i if c.get("melody", "up") == "up" else int(rng.integers(0, 10)), octaves=2)), vol)
            last_note = t

    def spawn(p, n, speed=None):
        nonlocal pos, vel, rad, col, cd
        if n <= 0:
            return
        a = rng.uniform(0, 2 * math.pi, n)
        sp = speed if speed is not None else vmin * rng.uniform(1.0, 1.3, n)
        pos = np.vstack([pos, np.array(p, float) + np.column_stack([np.cos(a), np.sin(a)]) * 4 * S])
        vel = np.vstack([vel, np.column_stack([np.cos(a), np.sin(a)]) * np.reshape(sp, (-1, 1))])
        rad = np.concatenate([rad, np.full(n, r0)])
        col = np.concatenate([col, (col.max() + 1 if len(col) else 0) * np.ones(n, int) % 5 if not teams else np.zeros(n, int)])
        cd = np.concatenate([cd, np.full(n, 0.5)])

    def keep(mask):
        nonlocal pos, vel, rad, col, cd
        pos, vel, rad, col, cd = pos[mask], vel[mask], rad[mask], col[mask], cd[mask]

    wall_fx = c.get("wall")
    for fi in range(n_frames):
        t = fi / FPS
        frac = min(t / (0.85 * duration), 1.0)
        target = n0 * (cap / max(n0, 1)) ** frac
        allow = len(pos) < target * 1.15
        events_mult = 0
        events_hit = 0
        for k in range(sub):
            tt = t + k * dt
            for r_ in rings:
                r_.theta += r_.spin * dt
            if g:
                vel[:, 1] += g * dt
            sp = np.hypot(vel[:, 0], vel[:, 1])[:, None]
            vel *= np.clip(vmin / np.maximum(sp, 1e-6), 1.0, 1.02)
            vel *= np.where(sp > vmax, 0.99, 1.0)
            # léger attracteur vers les trous noirs
            for h in holes:
                hx = cx + h["orbit"] * S * math.cos(h["w"] * tt + h["phase"]); hy = cy + h["orbit"] * S * math.sin(h["w"] * tt + h["phase"])
                h["x"], h["y"] = hx, hy
                dvec = np.array([hx, hy]) - pos
                dist = np.hypot(dvec[:, 0], dvec[:, 1]) + 1
                vel += dvec / dist[:, None] * (h.get("pull", 1.0) * 2500 * S * S / (dist[:, None] + 60 * S)) * dt
            pos += vel * dt
            cd -= dt
            # collisions bille-bille
            n = len(pos)
            if n > 1:
                dx = pos[:, None, 0] - pos[None, :, 0]; dy = pos[:, None, 1] - pos[None, :, 1]
                d2 = dx * dx + dy * dy
                rr = rad[:, None] + rad[None, :]
                iu, ju = np.nonzero(np.triu((d2 < rr * rr) & (d2 > 1e-9), 1))
                if len(iu):
                    dd = np.sqrt(d2[iu, ju]); nx = dx[iu, ju] / dd; ny = dy[iu, ju] / dd
                    ov = (rr[iu, ju] - dd) * 0.5
                    np.add.at(pos[:, 0], iu, nx * ov); np.add.at(pos[:, 1], iu, ny * ov)
                    np.add.at(pos[:, 0], ju, -nx * ov); np.add.at(pos[:, 1], ju, -ny * ov)
                    rvn = (vel[iu, 0] - vel[ju, 0]) * nx + (vel[iu, 1] - vel[ju, 1]) * ny
                    imp = -rvn * (rvn < 0)
                    np.add.at(vel[:, 0], iu, imp * nx); np.add.at(vel[:, 1], iu, imp * ny)
                    np.add.at(vel[:, 0], ju, -imp * nx); np.add.at(vel[:, 1], ju, -imp * ny)
                    if teams:
                        diff = (col[iu] != col[ju]) & (cd[iu] <= 0) & (cd[ju] <= 0)
                        for a_, b_ in zip(iu[diff], ju[diff]):
                            # la bille la plus lente adopte la couleur de l'autre
                            sa, sb = np.hypot(*vel[a_]), np.hypot(*vel[b_])
                            loser, winner = (a_, b_) if sa < sb else (b_, a_)
                            col[loser] = col[winner]; cd[loser] = 0.3
                            events_mult += 1
            # paroi : anneau actif le plus intérieur
            active = [r_ for r_ in rings if r_.alive]
            if active:
                ring = active[0]
                margin = float(np.max(np.hypot(vel[:, 0], vel[:, 1]))) * dt * 2 if len(vel) else 0
                hit = ring.collide(pos, vel, rad, cx, cy, margin)
                nh = int(hit.sum())
                if nh:
                    stats["bounces"] += nh
                    events_hit += nh
                    idx = np.nonzero(hit & (cd <= 0))[0]
                    if wall_fx == "grow" and len(idx):
                        tgt = r0 + (c.get("grow_max", 0.9) * ring.R * math.cos(math.pi / ring.shape if ring.shape != "circle" else 0) - r0) * frac ** 1.2
                        rad[idx] = np.maximum(rad[idx] + c.get("grow_min", 1.0) * S, rad[idx] + (tgt - rad[idx]) * 0.35)
                        cd[idx] = 0.05
                        if c.get("split_at"):
                            big = idx[rad[idx] > c["split_at"] * S]
                            for b in big:
                                if len(pos) < cap and allow:
                                    rad[b] = r0
                                    spawn(pos[b], 1)
                                    events_mult += 1
                                else:
                                    rad[b] = c["split_at"] * S
                    elif wall_fx == "speed" and len(idx):
                        vel[idx] *= c.get("speed_mul", 1.035)
                        cd[idx] = 0.05
                    elif wall_fx == "trail" and len(idx):
                        for i in idx:
                            trail_pts.append((pos[i, 0], pos[i, 1], len(trail_pts)))
                        cd[idx] = 0.05
                    elif wall_fx == "double" and len(idx) and allow:
                        idx = idx[: max(0, cap - len(pos))]
                        cd[idx] = 0.6
                        for i in idx:
                            spawn(pos[i], 1)
                        events_mult += len(idx)
                # sortie par l'ouverture
                outm = ring.outside(pos, rad, cx, cy)
                if outm.any():
                    oi = np.nonzero(outm)[0]
                    if c.get("rings"):
                        ring.alive = False
                        stats["broken"] += 1
                        pts, _ = ring.points(cx, cy, 60)
                        for p in pts[::2]:
                            particles.append([p[0], p[1], rng.normal(0, 200) * S, rng.normal(-100, 200) * S, 0.8, stats["broken"] % 5])
                        pulses.append([0.0, ring.R])
                        mx.add(tt, mx.note(mx.scale_freq(stats["broken"], octaves=3) * 0.5), 0.5)
                        if c.get("ring_double") and allow and len(pos) < cap:
                            for i in oi[:1]:
                                spawn(pos[i], 1)
                            events_mult += 1
                    else:
                        for i in oi:
                            escaped.append([pos[i, 0], pos[i, 1], vel[i, 0], vel[i, 1], float(rad[i]), int(col[i]), 1.5])
                        stats["escapes"] += len(oi)
                        keep(~outm)
                        if c.get("escape") == "spawn2":
                            for _ in oi:
                                nb = 2 if (allow and len(pos) + 2 <= cap) else 1
                                spawn((cx, cy), nb)
                                events_mult += 1
                                pulses.append([0.0, 30 * S])
            # trous noirs
            for h in holes:
                if not len(pos):
                    break
                dh = np.hypot(pos[:, 0] - h["x"], pos[:, 1] - h["y"])
                inn = np.nonzero((dh < h["r"] * S * 0.8) & (cd <= 0))[0]
                if not len(inn):
                    continue
                eff = h["effect"]
                if eff == "kill":
                    inn = inn[: max(0, len(pos) - 1)]   # on garde toujours au moins une bille
                    if not len(inn):
                        continue
                    m = np.ones(len(pos), bool); m[inn] = False; keep(m)
                    mx.add(tt, mx.thud(60), 0.25)
                    h["pulse"] = 1.0
                    continue
                mult = 3 if eff == "x3" else 2
                m = np.ones(len(pos), bool)
                for i in inn:
                    if not allow or len(pos) + (mult - 1) > cap:
                        a = rng.uniform(0, 2 * math.pi)
                        pos[i] = (h["x"] + math.cos(a) * h["r"] * S, h["y"] + math.sin(a) * h["r"] * S)
                        vel[i] = (math.cos(a) * vmin, math.sin(a) * vmin); cd[i] = 0.7
                        continue
                    m[i] = False
                    spawn((h["x"], h["y"]), mult, speed=None)
                    events_mult += 1
                m = np.concatenate([m, np.ones(len(pos) - len(m), bool)])
                keep(m)
                h["pulse"] = 1.0
                pulses.append([0.0, h["r"] * S, h["x"], h["y"]])
            # pilotage de l'ouverture des anneaux : rythme cible (dernier anneau vers 90 % de la durée)
            if c.get("rings"):
                done = stats["broken"] / len(rings)
                aim = min(t / (0.9 * duration), 1.0)
                for r_ in rings:
                    base = c.get("ring_gap", 0.55)
                    r_.gap_w = float(np.clip(base * (1 + 3 * (aim - done)), base * 0.4, base * 2.5))
        if events_mult:
            play_note(t, 0.42)
        if events_hit:
            if c.get("note_on_bounce"):
                play_note(t, 0.38)
            elif t - last_thud > 0.08:
                mx.add(t, mx.thud(int(rng.choice([80, 95, 110]))), 0.10 * min(events_hit, 4) ** 0.5); last_thud = t

        # ---------------- rendu
        img = bg.copy()
        dr = ImageDraw.Draw(img, "RGBA")
        rc = hsv(pal["ring"], 0.6, 1.0)
        # fils (string art)
        if trail_pts and len(pos):
            bx, by = pos[0]
            for (x, y, j) in trail_pts[-700:]:
                hc = hsv(pal["hues"][j % len(pal["hues"])] + j * 0.004, 0.6, 1)
                dr.line([x, y, bx, by], fill=(*hc, 110), width=max(1, int(2 * S)))
        # anneaux
        for i, r_ in enumerate(rings):
            if not r_.alive:
                continue
            pts, gm = r_.points(cx, cy, 360)
            hue = pal["ring"] + (i * 0.025 if c.get("rings") else 0)
            col_r = hsv(hue, 0.6, 1.0)
            runs, cur = [], []
            start = int(np.argmax(gm)) if gm.any() else 0
            order = np.roll(np.arange(len(pts)), -start)
            for j in order:
                if gm[j]:
                    if len(cur) > 1: runs.append(cur)
                    cur = []
                else:
                    cur.append(tuple(pts[j]))
            if len(cur) > 1: runs.append(cur)
            if not gm.any() and runs:
                runs = [runs[0] + [runs[0][0]]]
            wbase = (5 if c.get("rings") else 7) * S
            for w, a in ((wbase * 4, 22), (wbase * 2, 50), (wbase, 255)):
                for run_ in runs:
                    dr.line(run_, fill=(*col_r, a), width=max(1, int(w)), joint="curve")
        # trous noirs
        for h in holes:
            if "x" not in h:
                continue
            hp = h.get("pulse", 0.0); h["pulse"] = max(0, hp - 0.08)
            rr_ = h["r"] * S * (1 + 0.15 * hp)
            hc = (255, 60, 60) if h["effect"] == "kill" else hsv(pal["ring"] + 0.1, 0.7, 1)
            for kk in range(5, 0, -1):
                dr.ellipse([h["x"] - rr_ - kk * 7 * S, h["y"] - rr_ - kk * 7 * S, h["x"] + rr_ + kk * 7 * S, h["y"] + rr_ + kk * 7 * S], fill=(*hc, 16))
            dr.ellipse([h["x"] - rr_, h["y"] - rr_, h["x"] + rr_, h["y"] + rr_], fill=(0, 0, 0, 255), outline=(*hc, 255), width=max(1, int(5 * S)))
            lab = {"x2": "×2", "x3": "×3", "kill": "☠"}.get(h["effect"], "")
            if lab:
                fw = ImageFont.truetype(FONT, int(h["r"] * S * 0.7))
                tw = dr.textlength(lab, font=fw)
                dr.text((h["x"] - tw / 2, h["y"] - h["r"] * S * 0.42), lab, font=fw, fill=(*hc, 230))
        # ondes
        for p in pulses:
            p[0] += 1 / FPS
        pulses = [p for p in pulses if p[0] < 0.5]
        for p in pulses:
            px, py = (p[2], p[3]) if len(p) > 2 else (cx, cy)
            rr_ = p[1] + p[0] * 400 * S
            dr.ellipse([px - rr_, py - rr_, px + rr_, py + rr_], outline=(*rc, int(180 * (1 - p[0] / 0.5))), width=max(1, int(4 * S)))
        # traînée (mode vitesse)
        if wall_fx == "speed" and len(pos):
            hist.append(tuple(pos[0])); hist[:] = hist[-14:]
            for j, (x, y) in enumerate(hist[:-1]):
                a = int(200 * (j + 1) / len(hist)); rr_ = rad[0] * (0.4 + 0.6 * j / len(hist))
                hc = hsv(pal["hues"][0], 0.5, 1)
                dr.ellipse([x - rr_, y - rr_, x + rr_, y + rr_], fill=(*hc, a // 2))
        # billes sorties qui tombent
        keep_e = []
        for e in escaped:
            e[3] += 1800 * S / FPS; e[0] += e[2] / FPS; e[1] += e[3] / FPS; e[6] -= 1 / FPS
            if e[6] > 0 and e[1] < H + 50:
                sp_ = sprite(e[4], e[5]); img.paste(sp_, (int(e[0] - sp_.width / 2), int(e[1] - sp_.height / 2)), sp_)
                keep_e.append(e)
        escaped = keep_e
        # billes
        for i in np.argsort(pos[:, 1]) if len(pos) else []:
            sp_ = sprite(rad[i], int(col[i]))
            img.paste(sp_, (int(pos[i, 0] - sp_.width / 2), int(pos[i, 1] - sp_.height / 2)), sp_)
        # particules
        keep_p = []
        for p in particles:
            p[3] += 900 * S / FPS; p[0] += p[2] / FPS; p[1] += p[3] / FPS; p[4] -= 1 / FPS
            if p[4] > 0:
                hc = hsv(pal["hues"][p[5] % len(pal["hues"])], 0.5, 1)
                dr.ellipse([p[0] - 4 * S, p[1] - 4 * S, p[0] + 4 * S, p[1] + 4 * S], fill=(*hc, int(255 * min(1, p[4] / 0.5))))
                keep_p.append(p)
        particles = keep_p
        # HUD
        hud = c.get("hud", "count")
        if hud == "count":
            big = f"x{fmt(len(pos))}"
        elif hud == "rings":
            big = f"{stats['broken']}/{len(rings)}"
        elif hud == "bounces":
            big = fmt(stats["bounces"])
        elif hud == "size":
            big = f"{int(100 * float(rad.max()) / (rings[0].R)) if len(rad) else 0}%"
        elif hud == "speed":
            big = f"{int(float(np.hypot(*vel[0])) / S / 10) if len(vel) else 0} km/h"
        elif hud == "teams":
            a_ = int((col == 0).sum()); b_ = int((col == 1).sum())
            big = f"{a_} vs {b_}"
            tot = max(a_ + b_, 1)
            dr.rounded_rectangle([W * .1, 330 * S, W * .9, 352 * S], 8 * S, fill=(80, 140, 255, 255))
            dr.rounded_rectangle([W * .1, 330 * S, W * .1 + W * .8 * a_ / tot, 352 * S], 8 * S, fill=(255, 80, 80, 255))
        else:
            big = ""
        tw = dr.textlength(big, font=f_big)
        dr.text(((W - tw) / 2, 150 * S), big, font=f_big, fill=(255, 255, 255, 255))
        subl = c.get("subtitle", "")
        if subl:
            tw = dr.textlength(subl, font=f_mid)
            dr.text(((W - tw) / 2, 375 * S), subl, font=f_mid, fill=(*rc, 235))
        dr.rounded_rectangle([W * .1, H - 90 * S, W * .9, H - 78 * S], 6 * S, fill=(255, 255, 255, 40))
        dr.rounded_rectangle([W * .1, H - 90 * S, W * .1 + W * .8 * (fi / n_frames), H - 78 * S], 6 * S, fill=(*rc, 255))
        enc.frame(img)
        if fi % 300 == 0:
            print(f"frame {fi}/{n_frames} balls={len(pos)} {stats}", flush=True)
    mx.pad([mx.root / 2, mx.root / 2 * 1.5])
    enc.finish(mx, duration)
    print("OK", out, "balls", len(pos), stats)


if __name__ == "__main__":
    from concepts import CONCEPTS
    ap = argparse.ArgumentParser()
    ap.add_argument("--concept", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--duration", type=float, default=70)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", default="out/arena.mp4")
    a = ap.parse_args()
    run(CONCEPTS[a.concept]["params"], a.seed, a.duration, a.scale, a.out)
