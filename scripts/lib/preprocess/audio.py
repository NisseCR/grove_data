"""
Audio preprocessing.

Loudness-normalises to -16 LUFS and resamples to 48 kHz. Output is always
WebM/Opus. Requires ffmpeg on PATH.

All audio is normalised identically. Volume balance between music and ambience
is handled at playback time by the audio engine (see app/src/lib/config/audio.ts).
"""

import json
import subprocess
from pathlib import Path

SAMPLE_RATE = 48000
LUFS_TARGET = -16.0
TRUE_PEAK = -1.5
LRA = 11


def _loudnorm_filter(extra: str = "") -> str:
    """Build an ffmpeg loudnorm filter string, optionally with measured values appended."""
    return f"loudnorm=I={LUFS_TARGET}:TP={TRUE_PEAK}:LRA={LRA}{extra}"


def _measure_loudness(input_path: Path) -> dict:
    """Run the loudnorm first pass and parse JSON loudness measurements from stderr."""
    result = subprocess.run(
        ["ffmpeg", "-i", str(input_path), "-af", _loudnorm_filter(":print_format=json"), "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    stderr = result.stderr
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Could not parse loudnorm measurements for {input_path.name}")
    return json.loads(stderr[start : end + 1])


def _apply_normalization(input_path: Path, output_path: Path, measured: dict) -> None:
    """Apply loudness normalisation and resampling using pre-measured loudness values."""
    extra = (
        f":measured_I={measured['input_i']}"
        f":measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}"
        f":measured_thresh={measured['input_thresh']}"
        f":linear=true"
    )
    subprocess.run(
        [
            "ffmpeg", "-i", str(input_path),
            "-map", "0:a",
            "-af", _loudnorm_filter(extra),
            "-ar", str(SAMPLE_RATE),
            "-c:a", "libopus",
            "-b:a", "128k",
            "-y", str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )


def process_audio(source: Path, dest: Path) -> None:
    """Convert a source audio file to OGG and write it to dest, normalised to LUFS_TARGET."""
    measured = _measure_loudness(source)
    _apply_normalization(source, dest, measured)
