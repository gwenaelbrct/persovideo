"""Template 1 : roue + trou noir qui double les billes.

Usage: python3 wheel_blackhole.py --seed 1 --duration 70 --scale 1.0 --out out/v1.mp4
"""
import argparse, colorsys, math, subprocess, wave, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FPS = 30
SUB = 4                      # sous-pas de physique par image
SR = 44100
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

PALETTES = {
    "neon":   dict(bg1=(8, 6, 24), bg2=(26, 8, 48), hues=(0.50, 0.58, 0.75, 0.88, 0.95), ring=(120, 90, 255), hole=(190, 80, 255)),
    "sunset": dict(bg1=(20, 6, 14), bg2=(48, 12, 30), hues=(0.0, 0.05, 0.10, 0.92, 0.85), ring=(255, 120, 90), hole=(255, 60, 140)),
    "toxic":  dict(bg1=(4, 14, 10), bg2=(8, 36, 28), hues=(0.30, 0.38, 0.45, 0.15, 0.55), ring=(90, 255, 170), hole=(200, 255, 60)),
}
SCALE_NOTES = [0, 2, 4, 7, 9]  # pentatonique majeure


def make_sprites(r, hues, glow=2.2):
    """Sprites de billes avec halo, un par teinte."""
    sprites = {}
    size = int(r * glow * 2) + 2
    for i, h in enumerate(hues):
        base = np.array(colorsys.hsv_to_rgb(h, 0.65, 1.0)) * 255
        yy, xx = np.mgrid[0:size, 0:size]
        d = np.hypot(xx - size / 2, yy - size / 2) / r
        core = np.clip((1.0 - d) * r * 0.9, 0, 1)                 # disque net
        halo = np.exp(-np.maximum(d - 1, 0) * 2.6) * 0.45 * (d > 0.9)
        alpha = np.clip(core + halo * (1 - core), 0, 1)
        hl = np.clip(1 - np.hypot(xx - size / 2 + r * .3, yy - size / 2 + r * .3) / (r * .7), 0, 1)
        rgb = base[None, None, :] * (1 - hl[..., None] * .6) + 255 * hl[..., None] * .6
        arr = np.dstack([rgb, alpha * 255]).astype(np.uint8)
        sprites[i] = Image.fromarray(arr, "RGBA")
    return sprites


def tone(freq, dur, vol=0.5, kind="bell"):
    t = np.arange(int(SR * dur)) / SR
    if kind == "bell":
        s = (np.sin(2 * np.pi * freq * t) + .5 * np.sin(2 * np.pi * freq * 2.01 * t) + .25 * np.sin(2 * np.pi * freq * 3.02 * t))
        env = np.exp(-t * 5.0)
    else:  # tick
        s = np.sin(2 * np.pi * freq * t)
        env = np.exp(-t * 60.0)
    a = np.minimum(t / 0.004, 1)
    return (s * env * a * vol).astype(np.float32)


def run(seed, duration, scale, out, palette_name, cap):
    rng = np.random.default_rng(seed)
    pal = PALETTES[palette_name]
    W, H = int(1080 * scale), int(1920 * scale)
    S = scale
    cx, cy = W / 2, H * 0.52
    R = 450 * S                       # rayon de la roue
    br = 13 * S                       # rayon d'une bille
    hr = 62 * S                       # rayon du trou noir
    g = 900 * S
    spin = rng.choice([-1, 1]) * rng.uniform(0.25, 0.45)   # rad/s
    orbit_r = R * 0.50
    orbit_w = rng.uniform(0.35, 0.6) * rng.choice([-1, 1])
    dt = 1 / (FPS * SUB)
    n_frames = int(duration * FPS)

    # fond dégradé
    yy = np.linspace(0, 1, H)[:, None, None]
    bg = (np.array(pal["bg1"])[None, None, :] * (1 - yy) + np.array(pal["bg2"])[None, None, :] * yy)
    bg = np.repeat(bg, W, axis=1).astype(np.uint8)
    bg_img = Image.fromarray(bg)

    sprites = make_sprites(br, pal["hues"])
    nspr = len(sprites)
    f_big = ImageFont.truetype(FONT, int(150 * S))
    f_mid = ImageFont.truetype(FONT, int(46 * S))

    # état
    pos = np.array([[cx + 5, cy - R * 0.5]], dtype=np.float64)
    vel = np.array([[120 * S, 0.0]])
    col = np.array([0])
    immune = np.array([0.0])
    particles = []                    # [x,y,vx,vy,life,hueidx]
    pulses = []                       # [age, hueidx]
    hole_pulse = 0.0

    events = []                       # (t, kind, value)
    # rythme de croissance : cible exponentielle, on veut atteindre cap vers 85 % de la durée
    ang_wheel = 0.0

    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", out + ".noaudio.mp4"],
        stdin=subprocess.PIPE)

    total_in = 0
    attract = 1.0
    vmin, vmax = 550 * S, 1500 * S
    for fi in range(n_frames):
        t = fi / FPS
        wall_hits = 0
        target = cap ** min(t / (0.85 * duration), 1.0)
        ratio = target / max(len(pos), 1)
        attract = float(np.clip(attract * (1.04 if ratio > 1.3 else 0.97 if ratio < 0.9 else 1.0), 0.3, 25))
        for _ in range(SUB):
            ang_wheel += spin * dt
            hx = cx + orbit_r * math.cos(orbit_w * (t + _ * dt) + 1.0)
            hy = cy + orbit_r * math.sin(orbit_w * (t + _ * dt) + 1.0)
            vel[:, 1] += g * dt
            # léger attracteur vers le trou noir
            d = np.array([hx, hy]) - pos
            dist = np.maximum(np.hypot(d[:, 0], d[:, 1]), 1)
            vel += (d / dist[:, None]) * (9000 * S * S / (dist[:, None] + 60 * S)) * dt * 0.35 * attract
            sp_ = np.hypot(vel[:, 0], vel[:, 1])[:, None]
            vel *= np.clip(vmin / np.maximum(sp_, 1e-6), 1.0, 1.02)
            vel *= np.where(sp_ > vmax, 0.995, 1.0)
            pos += vel * dt
            immune = np.maximum(immune - dt, 0)

            # paroi circulaire
            rel = pos - [cx, cy]
            rd = np.hypot(rel[:, 0], rel[:, 1])
            out_m = rd > R - br
            if out_m.any():
                nrm = rel[out_m] / rd[out_m, None]
                pos[out_m] = np.array([cx, cy]) + nrm * (R - br)
                vn = (vel[out_m] * nrm).sum(1)
                inward = vn > 0
                tang = np.stack([-nrm[:, 1], nrm[:, 0]], 1)
                vel_o = vel[out_m]
                vel_o -= (2.0 * vn * inward)[:, None] * nrm
                vel_o += tang * (spin * R * 0.08)
                vel[out_m] = vel_o
                wall_hits += int(inward.sum())

            # collisions bille-bille
            n = len(pos)
            if n > 1:
                dx = pos[:, None, 0] - pos[None, :, 0]
                dy = pos[:, None, 1] - pos[None, :, 1]
                d2 = dx * dx + dy * dy
                iu, ju = np.where((d2 < (2 * br) ** 2) & (d2 > 1e-9))
                m = iu < ju
                iu, ju = iu[m], ju[m]
                if len(iu):
                    dd = np.sqrt(d2[iu, ju])
                    nx = dx[iu, ju] / dd
                    ny = dy[iu, ju] / dd
                    ov = (2 * br - dd) * 0.5
                    np.add.at(pos[:, 0], iu, nx * ov); np.add.at(pos[:, 1], iu, ny * ov)
                    np.add.at(pos[:, 0], ju, -nx * ov); np.add.at(pos[:, 1], ju, -ny * ov)
                    rvn = (vel[iu, 0] - vel[ju, 0]) * nx + (vel[iu, 1] - vel[ju, 1]) * ny
                    ap = rvn < 0
                    imp = -(1 + 0.95) * rvn * 0.5 * ap
                    np.add.at(vel[:, 0], iu, imp * nx); np.add.at(vel[:, 1], iu, imp * ny)
                    np.add.at(vel[:, 0], ju, -imp * nx); np.add.at(vel[:, 1], ju, -imp * ny)

            # trou noir : une bille entre -> deux ressortent
            dh = np.hypot(pos[:, 0] - hx, pos[:, 1] - hy)
            enter = np.where((dh < hr * 0.8) & (immune <= 0))[0]
            if len(enter):
                keep = np.ones(len(pos), bool)
                new_p, new_v, new_c = [], [], []
                for i in enter:
                    if len(pos) + len(new_p) >= cap:
                        # plafond atteint : la bille est juste recrachée
                        a = rng.uniform(0, 2 * math.pi)
                        vel[i] = [math.cos(a) * 500 * S, math.sin(a) * 500 * S]
                        pos[i] = [hx + math.cos(a) * hr * 1.0, hy + math.sin(a) * hr * 1.0]
                        immune[i] = 0.8
                        continue
                    keep[i] = False
                    h = (col[i] + 1) % nspr
                    for k in range(2):
                        a = rng.uniform(0, 2 * math.pi)
                        sp = rng.uniform(350, 650) * S
                        new_p.append([hx + math.cos(a) * hr * 1.0, hy + math.sin(a) * hr * 1.0])
                        new_v.append([math.cos(a) * sp, math.sin(a) * sp])
                        new_c.append(h)
                    particles += [[hx, hy, *(rng.normal(0, 260 * S, 2)), 0.6, h] for _k in range(10)]
                    pulses.append([0.0, h])
                    total_in += 1
                    events.append((t + _ * dt, "bell", len(pos) + len(new_p)))
                    hole_pulse = 1.0
                pos, vel, col, immune = pos[keep], vel[keep], col[keep], immune[keep]
                if new_p:
                    pos = np.vstack([pos, new_p]); vel = np.vstack([vel, new_v])
                    col = np.concatenate([col, new_c]); immune = np.concatenate([immune, np.full(len(new_p), 0.7)])
        if wall_hits:
            events.append((t, "tick", min(wall_hits, 6)))

        # ---------- rendu ----------
        img = bg_img.copy()
        dr = ImageDraw.Draw(img, "RGBA")
        # roue : anneau + graduations tournantes
        rc = pal["ring"]
        for w, a in ((int(26 * S), 25), (int(14 * S), 55), (int(6 * S), 255)):
            dr.ellipse([cx - R - w / 2, cy - R - w / 2, cx + R + w / 2, cy + R + w / 2], outline=(*rc, a), width=max(1, w))
        for k in range(48):
            a = ang_wheel + k * 2 * math.pi / 48
            r1, r2 = R + 14 * S, R + (34 if k % 4 == 0 else 24) * S
            dr.line([cx + r1 * math.cos(a), cy + r1 * math.sin(a), cx + r2 * math.cos(a), cy + r2 * math.sin(a)],
                    fill=(*rc, 200), width=max(1, int(5 * S)))
        # trou noir
        hx = cx + orbit_r * math.cos(orbit_w * t + 1.0)
        hy = cy + orbit_r * math.sin(orbit_w * t + 1.0)
        hc = pal["hole"]
        hole_pulse = max(hole_pulse - 0.08, 0)
        rr = hr * (1 + 0.15 * hole_pulse)
        for k in range(6, 0, -1):
            dr.ellipse([hx - rr - k * 7 * S, hy - rr - k * 7 * S, hx + rr + k * 7 * S, hy + rr + k * 7 * S], fill=(*hc, 14 + int(hole_pulse * 20)))
        dr.ellipse([hx - rr, hy - rr, hx + rr, hy + rr], fill=(0, 0, 0, 255), outline=(*hc, 255), width=max(1, int(5 * S)))
        for k in range(3):
            a0 = t * (2.2 + k * .7) + k * 2.1
            dr.arc([hx - rr * .7, hy - rr * .7, hx + rr * .7, hy + rr * .7], math.degrees(a0), math.degrees(a0) + 90, fill=(*hc, 150), width=max(1, int(3 * S)))
        # ondes
        for p in pulses:
            p[0] += 1 / FPS
        pulses = [p for p in pulses if p[0] < 0.5]
        for p in pulses:
            rad = rr + p[0] * 500 * S
            dr.ellipse([hx - rad, hy - rad, hx + rad, hy + rad], outline=(*hc, int(200 * (1 - p[0] / 0.5))), width=max(1, int(4 * S)))
        # billes
        order = np.argsort(pos[:, 1])
        for i in order:
            sp = sprites[int(col[i]) % nspr]
            img.paste(sp, (int(pos[i, 0] - sp.width / 2), int(pos[i, 1] - sp.height / 2)), sp)
        # particules
        newp = []
        for p in particles:
            p[0] += p[2] / FPS; p[1] += p[3] / FPS; p[4] -= 1 / FPS
            if p[4] > 0:
                a = int(255 * p[4] / 0.6)
                c = tuple(int(v) for v in np.array(colorsys.hsv_to_rgb(pal["hues"][p[5] % nspr], .4, 1)) * 255)
                dr.ellipse([p[0] - 3 * S, p[1] - 3 * S, p[0] + 3 * S, p[1] + 3 * S], fill=(*c, a))
                newp.append(p)
        particles = newp
        # HUD
        txt = f"x{len(pos)}"
        tw = dr.textlength(txt, font=f_big)
        for off, a in ((4, 90), (0, 255)):
            dr.text(((W - tw) / 2 + off * S, 200 * S + off * S), txt, font=f_big, fill=(255, 255, 255, a) if off == 0 else (*hc, a))
        sub = "WILL IT FILL THE WHEEL?"
        sw = dr.textlength(sub, font=f_mid)
        dr.text(((W - sw) / 2, 380 * S), sub, font=f_mid, fill=(255, 255, 255, 170))
        # barre de progression
        dr.rounded_rectangle([W * .1, H - 120 * S, W * .9, H - 108 * S], 6 * S, fill=(255, 255, 255, 40))
        dr.rounded_rectangle([W * .1, H - 120 * S, W * .1 + W * .8 * (fi / n_frames), H - 108 * S], 6 * S, fill=(*hc, 255))
        proc.stdin.write(img.tobytes())
        if fi % 150 == 0:
            print(f"frame {fi}/{n_frames}  balls={len(pos)}", flush=True)
    proc.stdin.close(); proc.wait()

    # ---------- audio (grave et doux) ----------
    from common import Mixer
    mx = Mixer(duration, root=rng.choice([110.0, 123.5, 130.8]))
    last_tick = -1
    for k, (te, kind, val) in enumerate(events):
        if kind == "bell":
            mx.add(te, mx.note(mx.scale_freq(k, octaves=2)), 0.45)
        elif te - last_tick > 0.06:
            mx.add(te, mx.thud(rng.choice([80, 95, 110])), 0.12 * min(val, 4) ** .5)
            last_tick = te
    mx.pad([mx.root / 2, mx.root / 2 * 1.5])
    wav_path = out + ".wav"
    mx.write(wav_path, duration)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out + ".noaudio.mp4", "-i", wav_path, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "160k", "-shortest", out], check=True)
    os.remove(out + ".noaudio.mp4"); os.remove(wav_path)
    print("OK", out, "balls final:", len(pos), "entries:", total_in)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--duration", type=float, default=70)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--palette", default="neon")
    ap.add_argument("--cap", type=int, default=350)
    ap.add_argument("--out", default="out/test.mp4")
    a = ap.parse_args()
    run(a.seed, a.duration, a.scale, a.out, a.palette, a.cap)
