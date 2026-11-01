"""Measuring what a sound actually is, rather than what it was meant to be.

Four numbers, each chosen because it caught a real sound that everyone -
including the person who bought it - had assumed was fine.
"""
from __future__ import annotations

import dataclasses
import pathlib
import wave

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore

try:
    import soundfile as sf
except ImportError:  # pragma: no cover
    sf = None  # type: ignore


@dataclasses.dataclass(frozen=True)
class Measured:
    seconds: float
    centroid_hz: float
    #: Fraction of energy above 5 kHz. Above about a third and a sound stops
    #: being a texture and starts being thin - the "needles" complaint.
    above_5k: float
    #: Peak over RMS. Over about 9 is a spike standing above the body of the
    #: sound, which is the thing an ear flinches at rather than leans into.
    crest: float
    #: Milliseconds to reach 80% of peak. Under 5 ms is heard as a click
    #: however warm everything after it is.
    attack_ms: float
    #: Standard deviation of 2 ms peaks over their mean. High is uneven and
    #: alive; low is a smooth wash. Neither is better - it depends whether the
    #: sound is separation (high) or friction (low). Reported, never judged.
    unevenness: float


def _read(path: pathlib.Path):
    if sf is not None:
        data, rate = sf.read(str(path), always_2d=False)
        if getattr(data, "ndim", 1) > 1:
            data = data.mean(axis=1)
        return data, rate
    if path.suffix.lower() != ".wav":
        return None, 0
    with wave.open(str(path), "rb") as w:
        n, ch, sw, rate = (w.getnframes(), w.getnchannels(),
                           w.getsampwidth(), w.getframerate())
        raw = w.readframes(n)
    dt = {1: np.uint8, 2: np.int16, 4: np.int32}[sw]
    x = np.frombuffer(raw, dtype=dt).astype(np.float64)
    x = (x - 128) / 128.0 if sw == 1 else x / float(2 ** (8 * sw - 1))
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, rate


def measure(path: pathlib.Path) -> Measured | None:
    if np is None:
        return None
    try:
        x, rate = _read(path)
    except Exception:
        return None
    if x is None or len(x) < 64:
        return None

    peak = float(np.abs(x).max())
    rms = float(np.sqrt(np.mean(x * x))) or 1e-9

    seg = x[: 1 << 16]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), 1.0 / rate)
    total = max(spec.sum(), 1e-9)

    env = np.abs(x)
    hop = max(1, int(rate * 0.002))
    blocks = np.array([np.abs(x[i * hop:(i + 1) * hop]).max()
                       for i in range(len(x) // hop)])

    return Measured(
        seconds=len(x) / rate,
        centroid_hz=float((spec * freqs).sum() / total),
        above_5k=float(spec[freqs > 5000].sum() / total),
        crest=peak / rms,
        attack_ms=float(np.argmax(env >= peak * 0.8)) / rate * 1000.0,
        unevenness=float(blocks.std() / max(blocks.mean(), 1e-9)),
    )


def loop_seam(path: pathlib.Path) -> tuple[float, float] | None:
    """How big the step is where a loop joins itself, against a typical step.

    Written after I nearly "fixed" a loop that was already perfect: my first
    seam check compared the mean LEVEL of the first and last 20 ms and
    reported 3-6%, which measures loudness variation and not discontinuity.
    The jump at the join was zero all along. A metric that sounds plausible
    and measures the wrong thing costs more than no metric.
    """
    if np is None:
        return None
    try:
        x, _ = _read(path)
    except Exception:
        return None
    if x is None or len(x) < 4:
        return None
    jump = abs(float(x[0]) - float(x[-1]))
    typical = float(np.abs(np.diff(x)).mean())
    return jump, typical
