"""Artifact-first YouTube production helpers.

This module prepares auditable script/storyboard files and renders a simple
MP4 draft only when ffmpeg is installed. It never pretends this draft is a
finished narrated video or that it was uploaded.
"""
from __future__ import annotations
import json, shutil, subprocess
from pathlib import Path
from typing import Any

def _safe_slug(value: str) -> str:
    import re
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")[:60] or "youtube-task"

def save_production_pack(output_dir: str, title: str, script: str, storyboard: list[dict[str, Any]], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(output_dir).resolve() / _safe_slug(title)
    root.mkdir(parents=True, exist_ok=True)
    (root / "script.md").write_text(script.strip() + "\n", encoding="utf-8")
    (root / "storyboard.json").write_text(json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "metadata.json").write_text(json.dumps(metadata or {}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "prepared", "artifact_dir": str(root), "script_path": str(root / "script.md"), "storyboard_path": str(root / "storyboard.json"), "metadata_path": str(root / "metadata.json")}

def render_storyboard_draft(output_dir: str, title: str, storyboard: list[dict[str, Any]], seconds_per_scene: int = 5) -> dict[str, Any]:
    """Render readable scene cards into an MP4 when ffmpeg is available."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"status": "blocked", "reason": "ffmpeg is not installed; MP4 was not rendered."}
    root = Path(output_dir).resolve() / _safe_slug(title)
    root.mkdir(parents=True, exist_ok=True)
    scenes = storyboard or [{"narration": title, "visual": "Title card"}]
    # Generate portable SRT captions and a concat list using PPM images (no Pillow dependency).
    frames = []
    for i, scene in enumerate(scenes, 1):
        text = (str(scene.get("on_screen_text") or scene.get("visual") or scene.get("narration") or f"Scene {i}"))[:180]
        # PPM plain-text frames with simple black background; draw text via ffmpeg drawtext
        # is intentionally avoided because host fonts/escaping vary. Use a generated SVG.
        import html
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect width="100%" height="100%" fill="#111827"/><text x="640" y="300" fill="#ffffff" font-size="46" text-anchor="middle">{html.escape(title[:90])}</text><foreignObject x="100" y="350" width="1080" height="250"><div xmlns="http://www.w3.org/1999/xhtml" style="font:32px sans-serif;color:white;text-align:center">{html.escape(text)}</div></foreignObject></svg>'
        frame = root / f"scene-{i:03d}.svg"
        frame.write_text(svg, encoding="utf-8")
        frames.append(frame)
    concat = root / "frames.txt"
    concat.write_text("".join(f"file '{p.as_posix()}'\nduration {max(1, int(seconds_per_scene))}\n" for p in frames) + f"file '{frames[-1].as_posix()}'\n", encoding="utf-8")
    mp4 = root / "video-draft.mp4"
    try:
        proc = subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-vf", "format=yuv420p", "-r", "24", "-pix_fmt", "yuv420p", str(mp4)], capture_output=True, text=True, timeout=180)
        if proc.returncode != 0 or not mp4.is_file() or mp4.stat().st_size == 0:
            return {"status": "failed", "reason": (proc.stderr or "ffmpeg failed")[-1500:]}
        return {"status": "rendered_draft", "video_path": str(mp4), "bytes": mp4.stat().st_size, "note": "Silent storyboard-card draft; not a narrated final video."}
    except Exception as exc:
        return {"status": "failed", "reason": type(exc).__name__}
