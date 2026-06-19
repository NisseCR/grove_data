"""
Parse a story markdown file into a ParsedChapter JSON file.

Input  — source/stories/{story}/{chapter}.md
Output — {OUTPUT_PATH}/stories/{story}/{chapter}.json

The output JSON matches the ParsedChapter TypeScript interface:
  { frontmatter: ChapterFrontmatter, segments: ChapterSegment[] }
"""

import json
import re
from pathlib import Path
from typing import Any

import frontmatter

_TRIGGER_RE = re.compile(r"<!--\s*trigger\r?\n(.*?)-->", re.DOTALL)
_DIVIDER_RE = re.compile(r"<!--\s*divider\s*-->", re.IGNORECASE)


def _parse_audio_ref(s: str) -> dict[str, Any]:
    """Parse "id" or "id@volume" into an AudioRef dict. Volume defaults to 0.5."""
    s = s.strip()
    at = s.rfind("@")
    if at == -1:
        return {"id": s, "volume": 0.5}
    try:
        vol = float(s[at + 1 :])
    except ValueError:
        vol = 0.5
    return {"id": s[:at], "volume": vol}


def _parse_ambience_refs(value: Any) -> list[dict[str, Any]] | None:
    """Parse a comma-separated ambience string or None/null into a list of AudioRefs."""
    if value is None:
        return None
    v = str(value).strip()
    if not v or v.lower() == "null":
        return None
    return [_parse_audio_ref(t) for t in v.split(",") if t.strip()]


def _parse_playlist_ref(value: Any) -> dict[str, Any] | None:
    """Parse a playlist string or None/null into an AudioRef, or None."""
    if value is None:
        return None
    v = str(value).strip()
    if not v or v.lower() == "null":
        return None
    return _parse_audio_ref(v)


def _parse_trigger(block: str) -> dict[str, Any]:
    """Parse trigger comment body into a ChapterTrigger dict."""
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return {
        "ambiences": _parse_ambience_refs(fields.get("ambiences")),
        "playlist": _parse_playlist_ref(fields.get("playlist")),
    }


_INLINE_RE = re.compile(
    r"\*\*\*(.*?)\*\*\*"  # ***bold+italic***
    r"|\*\*_(.*?)_\*\*"   # **_bold+italic_**
    r"|\*\*(.*?)\*\*"     # **bold**
    r"|\*(.*?)\*"         # *italic*
    r"|_(.*?)_"           # _italic_
)
_PARA_SPLIT_RE = re.compile(r"\r?\n\r?\n+")


def _parse_inline(text: str) -> list[dict[str, Any]]:
    """Parse bold/italic markdown markers into a list of inline span objects."""
    spans: list[dict[str, Any]] = []
    last = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > last:
            spans.append({"text": text[last : m.start()]})
        if m.group(1) is not None:                                    # ***text***
            spans.append({"text": m.group(1), "bold": True, "italic": True})
        elif m.group(2) is not None:                                   # **_text_**
            spans.append({"text": m.group(2), "bold": True, "italic": True})
        elif m.group(3) is not None:                                   # **text**
            spans.append({"text": m.group(3), "bold": True})
        elif m.group(4) is not None:                                   # *text*
            spans.append({"text": m.group(4), "italic": True})
        else:                                                          # _text_
            spans.append({"text": m.group(5), "italic": True})
        last = m.end()
    if last < len(text):
        spans.append({"text": text[last:]})
    return spans


def _to_blocks(text: str) -> list[dict[str, Any]]:
    """Split text on divider comments, then each prose chunk into paragraph spans."""
    parts = _DIVIDER_RE.split(text)
    blocks: list[dict[str, Any]] = []
    for i, part in enumerate(parts):
        prose = part.strip()
        if prose:
            paragraphs = [
                _parse_inline(p.strip())
                for p in _PARA_SPLIT_RE.split(prose)
                if p.strip()
            ]
            if paragraphs:
                blocks.append({"type": "prose", "paragraphs": paragraphs})
        if i < len(parts) - 1:
            blocks.append({"type": "divider"})
    return blocks


def process_story(source_file: Path, out_path: Path) -> None:
    """Parse a chapter markdown file and write a ParsedChapter JSON to out_path."""
    post = frontmatter.load(str(source_file))
    meta = post.metadata

    fm = {
        "title": str(meta.get("title", "")),
        "scene": str(meta.get("scene", "")),
        "ambiences": _parse_ambience_refs(meta.get("ambiences")),
        "playlist": _parse_playlist_ref(meta.get("playlist")),
    }

    body: str = post.content
    trigger_matches = list(_TRIGGER_RE.finditer(body))
    segments: list[dict[str, Any]] = []

    if not trigger_matches:
        segments.append({"blocks": _to_blocks(body.strip())})
    else:
        pre_text = body[: trigger_matches[0].start()].strip()
        if pre_text:
            segments.append({"blocks": _to_blocks(pre_text)})

        for i, match in enumerate(trigger_matches):
            end = trigger_matches[i + 1].start() if i + 1 < len(trigger_matches) else len(body)
            text = body[match.end() : end].strip()
            segments.append({
                "blocks": _to_blocks(text),
                "trigger": _parse_trigger(match.group(1)),
            })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"frontmatter": fm, "segments": segments}, f, ensure_ascii=False, indent=2)
