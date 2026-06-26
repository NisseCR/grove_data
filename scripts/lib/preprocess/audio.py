"""
Audio preprocessing.

Loudness-normalises to -16 LUFS and resamples to 48 kHz. Output is always
WebM/Opus. Requires ffmpeg on PATH.

All audio is normalised identically. Volume balance between music and ambience
is handled at playback time by the audio engine (see app/src/lib/config/audio.ts).

Files longer than LOOP_TARGET_DURATION are trimmed and given a baked crossfade
loop point so they loop seamlessly in Tone.js without audible clicks.
"""

import json
import subprocess
import tempfile
from pathlib import Path

SAMPLE_RATE = 48000
LUFS_TARGET = -16.0
TRUE_PEAK = -1.5
LRA = 11

LOOP_TARGET_DURATION = 60  # seconds — files longer than this get crossfade-looped
LOOP_CROSSFADE = 3          # seconds — overlap baked at the loop point


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


def _get_duration(path: Path) -> float:
    """Return the duration of an audio file in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    for stream in json.loads(result.stdout).get("streams", []):
        if "duration" in stream:
            return float(stream["duration"])
    raise ValueError(f"Could not determine duration of {path.name}")


def _apply_crossfade_loop(input_path: Path, output_path: Path) -> None:
    """Trim input and bake a seamless crossfade loop point.

    Opens the source twice: body (LOOP_TARGET_DURATION seconds) and head (the
    first LOOP_CROSSFADE seconds). acrossfade blends the tail of the body into
    the head; the first LOOP_CROSSFADE seconds are then stripped so the file
    starts exactly where the head ends. Result: (LOOP_TARGET_DURATION -
    LOOP_CROSSFADE) seconds that loop without a click — the end fades into
    source second LOOP_CROSSFADE, and the file also starts at source second
    LOOP_CROSSFADE.
    Output is uncompressed PCM so loudnorm can process it in a subsequent pass.
    """
    subprocess.run(
        [
            "ffmpeg",
            "-t", str(LOOP_TARGET_DURATION), "-i", str(input_path),
            "-t", str(LOOP_CROSSFADE),        "-i", str(input_path),
            "-filter_complex",
            (
                f"[0:a][1:a]acrossfade=d={LOOP_CROSSFADE}:c1=qsin:c2=qsin[cf];"
                f"[cf]atrim=start={LOOP_CROSSFADE},asetpts=PTS-STARTPTS[out]"
            ),
            "-map", "[out]",
            "-c:a", "pcm_s16le",
            "-y", str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )


def process_audio(source: Path, dest: Path, *, loop: bool = False) -> None:
    """Convert a source audio file to WebM/Opus, normalised to LUFS_TARGET.

    When loop=True, long files (> LOOP_TARGET_DURATION) are first trimmed and
    given a baked crossfade loop point before normalisation.
    """
    duration = _get_duration(source)
    if loop and duration > LOOP_TARGET_DURATION:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            _apply_crossfade_loop(source, tmp_path)
            measured = _measure_loudness(tmp_path)
            _apply_normalization(tmp_path, dest, measured)
        finally:
            tmp_path.unlink(missing_ok=True)
    else:
        measured = _measure_loudness(source)
        _apply_normalization(source, dest, measured)
