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
    """Render a silent, readable scene-card MP4 when ffmpeg with drawtext is installed."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"status": "blocked", "reason": "ffmpeg is not installed; MP4 was not rendered."}
    root = Path(output_dir).resolve() / _safe_slug(title)
    root.mkdir(parents=True, exist_ok=True)
    scenes = storyboard or [{"narration": title, "visual": "Title card"}]
    clips = []
    try:
        for i, scene in enumerate(scenes, 1):
            scene_text = str(scene.get("on_screen_text") or scene.get("visual") or scene.get("narration") or f"Scene {i}")
            textfile = root / f"scene-{i:03d}.txt"
            textfile.write_text((title[:90] + "\\n\\n" + scene_text[:180]).replace("\\r", " "), encoding="utf-8")
            clip = root / f"clip-{i:03d}.mp4"
            vf = f"drawtext=textfile='{textfile.as_posix()}':fontcolor=white:fontsize=36:line_spacing=14:x=(w-text_w)/2:y=(h-text_h)/2"
            proc = subprocess.run(
                [ffmpeg, "-y", "-f", "lavfi", "-i", f"color=c=0x111827:s=1280x720:d={max(1,int(seconds_per_scene))}",
                 "-vf", vf, "-r", "24", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-an", str(clip)],
                capture_output=True, text=True, timeout=120
            )
            if proc.returncode != 0 or not clip.is_file() or clip.stat().st_size == 0:
                return {"status": "failed", "reason": (proc.stderr or "ffmpeg scene render failed")[-1200:]}
            clips.append(clip)
        concat = root / "clips.txt"
        concat.write_text("".join(f"file '{p.as_posix()}'\\n" for p in clips), encoding="utf-8")
        mp4 = root / "video-draft.mp4"
        proc = subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(mp4)], capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not mp4.is_file() or mp4.stat().st_size == 0:
            return {"status": "failed", "reason": (proc.stderr or "ffmpeg concat failed")[-1200:]}
        return {"status": "rendered_draft", "video_path": str(mp4), "bytes": mp4.stat().st_size, "scenes": len(clips), "note": "Silent storyboard-card draft; not a narrated final video."}
    except Exception as exc:
        return {"status": "failed", "reason": type(exc).__name__}
