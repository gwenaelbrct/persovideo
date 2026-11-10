"""Briques communes : audio doux, sprites de billes, encodeur ffmpeg."""
import colorsys, math, os, subprocess, wave
import numpy as np
from PIL import Image

SR = 44100
FPS = 30
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
PENTA = [0, 2, 4, 7, 9]


# ---------------------------------------------------------------- audio
def _lowpass(x, cutoff):
    a = math.exp(-2 * math.pi * cutoff / SR)
    y = np.empty_like(x); acc = 0.0
    # filtre 1 pôle vectorisé par blocs (suffisant pour des sons courts)
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


class Mixer:
    """Accumule des événements sonores puis écrit un WAV. Sons graves et doux."""

    def __init__(self, duration, root=130.8):  # Do3
        self.track = np.zeros(int(SR * (duration + 2)), np.float32)
        self.root = root
        self.cache = {}

    def _get(self, key, fn):
        if key not in self.cache:
            self.cache[key] = fn()
        return self.cache[key]

    def note(self, freq):
        """Marimba / pluck doux : sinus + petite harmonique, décroissance rapide."""
        def make():
            t = np.arange(int(SR * 0.7)) / SR
            s = np.sin(2 * np.pi * freq * t) + 0.18 * np.sin(2 * np.pi * freq * 4 * t) * np.exp(-t * 25)
            env = np.exp(-t * 6) * np.minimum(t / 0.006, 1)
            return (s * env).astype(np.float32)
        return self._get(("note", round(freq, 1)), make)

    def thud(self, f0=90):
        def make():
            t = np.arange(int(SR * 0.18)) / SR
            f = f0 * (1 + 1.5 * np.exp(-t * 40))
            ph = 2 * np.pi * np.cumsum(f) / SR
            return (np.sin(ph) * np.exp(-t * 22) * np.minimum(t / 0.002, 1)).astype(np.float32)
        return self._get(("thud", f0), make)

    def boom(self):
        def make():
            rng = np.random.default_rng(0)
            t = np.arange(int(SR * 1.2)) / SR
            f = 55 * (1 + 2 * np.exp(-t * 12))
            body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4)
            noise = _lowpass(rng.normal(0, 1, len(t)).astype(np.float32), 900) * np.exp(-t * 9) * 2.5
            return ((body + noise) * np.minimum(t / 0.003, 1)).astype(np.float32)
        return self._get(("boom",), make)

    def scale_freq(self, idx, octaves=2):
        """Note de la gamme pentatonique, bouclée sur `octaves` octaves (jamais trop aiguë)."""
        idx = idx % (5 * octaves)
        return self.root * 2 ** ((PENTA[idx % 5] + 12 * (idx // 5)) / 12)

    def add(self, t, snd, vol=1.0, pan_dummy=None):
        i0 = int(t * SR)
        if i0 >= len(self.track):
            return
        n = min(len(snd), len(self.track) - i0)
        self.track[i0:i0 + n] += snd[:n] * vol

    def pad(self, freqs, vol=0.035):
        tt = np.arange(len(self.track)) / SR
        for f in freqs:
            self.track += (vol * np.sin(2 * np.pi * f * tt) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * tt + f))).astype(np.float32)

    def write(self, path, duration):
        tr = self.track[: int(SR * duration)]
        # compresseur très simple : soft clip
        peak = np.percentile(np.abs(tr), 99.9) + 1e-6
        tr = np.tanh(tr / peak * 1.2) * 0.8
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
            wf.writeframes((tr * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- visuel
def ball_sprite(r, rgb, glow=2.2):
    size = int(r * glow * 2) + 2
    yy, xx = np.mgrid[0:size, 0:size]
    d = np.hypot(xx - size / 2, yy - size / 2) / r
    core = np.clip((1.0 - d) * r * 0.9, 0, 1)
    halo = np.exp(-np.maximum(d - 1, 0) * 2.6) * 0.45 * (d > 0.9) * np.clip((glow - d) / (glow - 1), 0, 1)
    alpha = np.clip(core + halo * (1 - core), 0, 1)
    hl = np.clip(1 - np.hypot(xx - size / 2 + r * .3, yy - size / 2 + r * .3) / (r * .7), 0, 1)
    base = np.array(rgb, float)
    col = base[None, None, :] * (1 - hl[..., None] * .6) + 255 * hl[..., None] * .6
    return Image.fromarray(np.dstack([col, alpha * 255]).astype(np.uint8), "RGBA")


def hsv(h, s=0.65, v=1.0):
    return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h % 1, s, v))


def gradient_bg(W, H, c1, c2):
    yy = np.linspace(0, 1, H)[:, None, None]
    bg = np.array(c1)[None, None, :] * (1 - yy) + np.array(c2)[None, None, :] * yy
    return Image.fromarray(np.repeat(bg, W, axis=1).astype(np.uint8))


class Encoder:
    def __init__(self, out, W, H):
        self.out, self.tmp = out, out + ".noaudio.mp4"
        self.p = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
             "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", self.tmp],
            stdin=subprocess.PIPE)

    def frame(self, img):
        self.p.stdin.write(img.tobytes())

    def finish(self, mixer, duration):
        self.p.stdin.close(); self.p.wait()
        wav = self.out + ".wav"
        mixer.write(wav, duration)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", self.tmp, "-i", wav, "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "160k", "-shortest", self.out], check=True)
        os.remove(self.tmp); os.remove(wav)


def fmt(n):
    n = int(round(n))
    for div, suf in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if n >= div:
            v = n / div
            return (f"{v:.1f}".rstrip("0").rstrip(".") if v < 10 else f"{int(v)}") + suf
    return str(n)
