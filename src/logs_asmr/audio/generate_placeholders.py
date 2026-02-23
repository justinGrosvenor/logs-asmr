"""Generate placeholder WAV audio files for testing the audio pipeline."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

_AUDIO_DIR = Path(__file__).parent.parent / "resources" / "audio"


def _write_wav(path: Path, samples: list[int], sample_rate: int = 44100) -> None:
    """Write 16-bit mono WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        data = struct.pack(f"<{len(samples)}h", *samples)
        w.writeframes(data)


def generate_white_noise_loop(filename: str, duration_s: float = 5.0) -> None:
    """Generate a short white noise loop (ambient placeholder)."""
    import random

    sample_rate = 44100
    n_samples = int(sample_rate * duration_s)
    # Low-amplitude white noise
    samples = [random.randint(-800, 800) for _ in range(n_samples)]

    # Fade in/out for looping
    fade = int(sample_rate * 0.1)
    for i in range(fade):
        factor = i / fade
        samples[i] = int(samples[i] * factor)
        samples[-(i + 1)] = int(samples[-(i + 1)] * factor)

    _write_wav(_AUDIO_DIR / filename, samples, sample_rate)


def generate_sine_beep(filename: str, freq: float = 880.0, duration_s: float = 0.3) -> None:
    """Generate a short sine wave beep (alert placeholder)."""
    sample_rate = 44100
    n_samples = int(sample_rate * duration_s)
    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        # Envelope: attack-sustain-release
        if t < 0.01:
            env = t / 0.01
        elif t > duration_s - 0.05:
            env = (duration_s - t) / 0.05
        else:
            env = 1.0
        value = int(8000 * env * math.sin(2 * math.pi * freq * t))
        samples.append(max(-32767, min(32767, value)))

    _write_wav(_AUDIO_DIR / filename, samples, sample_rate)


def generate_all() -> None:
    """Generate all placeholder audio files."""
    print("Generating placeholder audio files...")
    generate_white_noise_loop("noise_floor.wav", duration_s=5.0)
    print("  noise_floor.wav")
    generate_white_noise_loop("beach.wav", duration_s=5.0)
    print("  beach.wav")
    generate_white_noise_loop("rain_thunder.wav", duration_s=5.0)
    print("  rain_thunder.wav")
    generate_sine_beep("thunderstorm.wav", freq=220.0, duration_s=0.5)
    print("  thunderstorm.wav")
    print("Done.")


if __name__ == "__main__":
    generate_all()
