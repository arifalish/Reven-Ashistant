from pathlib import Path

from workers.youtube_pipeline import save_production_pack, render_storyboard_draft, upload_to_youtube


def test_production_pack_writes_script_storyboard_and_metadata(tmp_path):
    result = save_production_pack(
        str(tmp_path),
        "Funny Test Video",
        "Hello world. This is a test script.",
        [{"scene": 1, "narration": "Hello", "visual": "A cat", "on_screen_text": "Oops"}],
        {"description": "A test"},
    )
    assert result["status"] == "prepared"
    assert Path(result["script_path"]).read_text().startswith("Hello world")
    assert Path(result["storyboard_path"]).is_file()
    assert Path(result["metadata_path"]).is_file()


def test_video_renderer_reports_missing_ffmpeg_truthfully(tmp_path, monkeypatch):
    import workers.youtube_pipeline as pipeline
    monkeypatch.setattr(pipeline.shutil, "which", lambda _: None)
    result = render_storyboard_draft(str(tmp_path), "Test", [{"visual": "Scene"}])
    assert result["status"] == "blocked"
    assert "ffmpeg" in result["reason"]


def test_upload_requires_oauth_token_file(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_OAUTH_TOKEN_FILE", raising=False)
    result = upload_to_youtube(str(tmp_path / "missing.mp4"), {"title": "Test"})
    assert result["status"] == "blocked"
    assert "YOUTUBE_OAUTH_TOKEN_FILE" in result["reason"]
