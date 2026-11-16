"""Gera os efeitos sonoros e as músicas do jogo (estilo chiptune) só com a stdlib.

    python tools/make_sfx.py

Saída: assets/audio/sfx/*.wav e assets/audio/music/*.wav (mono, 16 bits, 22050 Hz).
Os arquivos são versionados no repositório; rode de novo só se quiser mudar os sons.
Para trocar um som, basta colocar outro arquivo com o mesmo nome (ou apontar em game.json -> audio).
"""
import array
import math
import random
import wave
from pathlib import Path

RATE = 22050
OUT = Path(__file__).resolve().parent.parent / "assets" / "audio"


def _write(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = max(1e-9, max(abs(x) for x in samples))
    gain = min(1.0, 0.92 / peak) if peak > 0.92 else 1.0
    data = array.array("h", (int(max(-1, min(1, x * gain)) * 32000) for x in samples))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


def env(i: int, n: int, attack: float = 0.01, release: float = 0.6) -> float:
    t = i / n
    a = min(1.0, t / max(attack, 1e-6))
    r = min(1.0, (1 - t) / max(release, 1e-6))
    return a * r


def tone(freq: float, dur: float, shape: str = "square", vol: float = 0.5, slide: float = 0.0,
         attack: float = 0.01, release: float = 0.7, duty: float = 0.5) -> list[float]:
    n = int(RATE * dur)
    out, phase = [], 0.0
    for i in range(n):
        f = freq * (1 + slide * i / n)
        phase += f / RATE
        p = phase % 1.0
        if shape == "square":
            v = 1.0 if p < duty else -1.0
        elif shape == "tri":
            v = 4 * abs(p - 0.5) - 1
        elif shape == "saw":
            v = 2 * p - 1
        else:
            v = math.sin(math.tau * p)
        out.append(v * vol * env(i, n, attack, release))
    return out


def noise(dur: float, vol: float = 0.5, release: float = 0.9, lp: float = 1.0) -> list[float]:
    n = int(RATE * dur)
    out, last = [], 0.0
    for i in range(n):
        last += (random.uniform(-1, 1) - last) * lp
        out.append(last * vol * env(i, n, 0.002, release))
    return out


def mix(*tracks: list[float]) -> list[float]:
    n = max(len(t) for t in tracks)
    out = [0.0] * n
    for t in tracks:
        for i, v in enumerate(t):
            out[i] += v
    return out


def cat(*tracks: list[float]) -> list[float]:
    out: list[float] = []
    for t in tracks:
        out += t
    return out


def silence(dur: float) -> list[float]:
    return [0.0] * int(RATE * dur)


def vary(base_freq: float, k: int) -> float:
    return base_freq * (1 + (k - 1) * 0.06)


# --- efeitos -------------------------------------------------------------------------------
def sfx() -> dict[str, list[float]]:
    random.seed(7)
    s: dict[str, list[float]] = {}
    for k in range(3):   # 3 variações de cada golpe comum (o jogo sorteia)
        s[f"hit{k + 1}"] = mix(noise(0.13, 0.55, 0.9, 0.5), tone(vary(150, k), 0.13, "square", 0.45, -0.6))
        s[f"block{k + 1}"] = mix(noise(0.08, 0.35, 0.8, 0.9), tone(vary(520, k), 0.1, "tri", 0.5, -0.2))
        s[f"whoosh{k + 1}"] = noise(0.18, 0.35, 0.95, 0.12 + 0.03 * k)
    s["crit"] = mix(noise(0.2, 0.6, 0.9, 0.6), tone(110, 0.2, "square", 0.5, -0.7),
                    cat(silence(0.04), tone(880, 0.16, "square", 0.3, 0.3)))
    s["parry"] = mix(tone(1320, 0.25, "square", 0.35, 0.0, 0.003, 0.95), tone(1980, 0.2, "sine", 0.3, 0.0, 0.003, 0.95),
                     noise(0.06, 0.4, 0.9, 0.9))
    s["miss"] = noise(0.16, 0.28, 0.95, 0.1)
    s["coin"] = cat(tone(988, 0.07, "square", 0.35, 0.0, 0.003, 0.3), tone(1319, 0.2, "square", 0.35, 0.0, 0.003, 0.9))
    s["levelup"] = cat(*(tone(f, 0.11, "square", 0.35, 0.0, 0.005, 0.5) for f in (523, 659, 784, 1047)),
                       tone(1319, 0.3, "square", 0.35, 0.0, 0.005, 0.9))
    s["click"] = tone(660, 0.04, "square", 0.3, 0.0, 0.002, 0.9)
    s["hover"] = tone(440, 0.03, "tri", 0.18, 0.0, 0.002, 0.9)
    s["confirm"] = cat(tone(660, 0.06, "square", 0.3, 0.0, 0.002, 0.4), tone(880, 0.1, "square", 0.3, 0.0, 0.002, 0.9))
    s["back"] = cat(tone(520, 0.06, "square", 0.28, 0.0, 0.002, 0.4), tone(390, 0.1, "square", 0.28, 0.0, 0.002, 0.9))
    s["ko"] = mix(noise(0.45, 0.6, 0.95, 0.3), tone(160, 0.5, "saw", 0.45, -0.85, 0.005, 0.95))
    s["warning"] = cat(tone(740, 0.09, "square", 0.3, 0.0, 0.003, 0.5), tone(740, 0.09, "square", 0.3, 0.0, 0.003, 0.5))
    s["pause"] = cat(tone(440, 0.07, "tri", 0.3), tone(330, 0.1, "tri", 0.3))
    s["save"] = cat(tone(784, 0.05, "tri", 0.2), tone(1047, 0.09, "tri", 0.2, 0.0, 0.005, 0.9))
    return s


# --- músicas (loops curtos) -----------------------------------------------------------------
NOTE = {n: 440 * 2 ** ((i - 9) / 12) for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(note: str, octave: int) -> float:
    return NOTE[note] * 2 ** (octave - 4)


def track(bpm: int, prog: list[tuple[str, str]], bars: int, lead_pattern: list[int], shape: str = "square",
          drums: bool = True, bass_oct: int = 2, lead_oct: int = 4) -> list[float]:
    """prog: lista de (nota raiz, 'maj'|'min') — um acorde por compasso. Padrão de 8 colcheias por compasso."""
    beat = 60 / bpm
    step = beat / 2
    total = int(RATE * step * 8 * bars)
    out = [0.0] * total
    pos = 0
    for bar in range(bars):
        root, kind = prog[bar % len(prog)]
        third = 3 if kind == "min" else 4
        names = list(NOTE)
        ri = names.index(root)
        chord = [names[(ri + o) % 12] for o in (0, third, 7)]
        for s in range(8):
            t0 = int((bar * 8 + s) * step * RATE)
            parts = []
            if s % 2 == 0:
                parts.append(tone(hz(root, bass_oct), step * 1.6, "tri", 0.33, 0.0, 0.01, 0.6))
            idx = lead_pattern[(bar * 8 + s) % len(lead_pattern)]
            if idx >= 0:
                n = chord[idx % 3]
                parts.append(tone(hz(n, lead_oct + idx // 3), step * 0.9, shape, 0.17, 0.0, 0.01, 0.7, 0.25))
            if drums:
                if s % 4 == 0:
                    parts.append(mix(tone(90, 0.1, "sine", 0.4, -0.6), noise(0.04, 0.2, 0.9, 0.4)))
                if s % 2 == 1:
                    parts.append(noise(0.04, 0.12, 0.9, 0.9))
            for p in parts:
                for i, v in enumerate(p):
                    if t0 + i < total:
                        out[t0 + i] += v
    return out


def music() -> dict[str, list[float]]:
    return {
        "menu": track(104, [("A", "min"), ("F", "maj"), ("C", "maj"), ("G", "maj")], 8,
                      [0, 2, 4, 2, 3, 2, 1, 2], "square", True),
        "hub": track(96, [("C", "maj"), ("G", "maj"), ("A", "min"), ("F", "maj")], 8,
                     [0, -1, 2, -1, 4, 2, 1, -1], "tri", False, 2, 4),
        "training": track(132, [("D", "min"), ("A#", "maj"), ("F", "maj"), ("C", "maj")], 8,
                          [0, 1, 2, 4, 2, 1, 2, 5], "square", True),
        "arena": track(148, [("E", "min"), ("C", "maj"), ("D", "maj"), ("B", "min")], 8,
                       [0, 2, 4, 5, 4, 2, 3, 5], "saw", True),
    }


def main() -> None:
    for name, data in sfx().items():
        _write(OUT / "sfx" / f"{name}.wav", data)
    for name, data in music().items():
        _write(OUT / "music" / f"{name}.wav", data)
    total = sum(p.stat().st_size for p in OUT.rglob("*.wav"))
    print(f"OK: {len(list(OUT.rglob('*.wav')))} arquivos, {total / 1048576:.1f} MB em {OUT}")


if __name__ == "__main__":
    main()
