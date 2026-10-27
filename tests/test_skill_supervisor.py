import pytest

from core.skill_supervisor import (
    SKILL_REGISTRY,
    _parse_plan,
    _ready_waves,
    deterministic_skill_plan,
)


def test_registry_contains_all_fifteen_workers():
    assert len(SKILL_REGISTRY) == 15
    assert "google-maps-scraper-kit" in SKILL_REGISTRY
    assert "opendots-coworker-skill" in SKILL_REGISTRY


def test_compound_lead_research_and_outreach_plan_contains_dependencies():
    plan = deterministic_skill_plan(
        "Scrape Delhi IT companies, check their latest website news, and write personalized cold emails"
    )
    assert "google-maps-scraper-kit" in plan
    assert "browser-agent-skill" in plan
    assert "sales-desk-skill" in plan
    assert plan.index("google-maps-scraper-kit") < plan.index("browser-agent-skill")
    assert plan.index("browser-agent-skill") < plan.index("sales-desk-skill")
    assert plan[-1] == "humanizer-core-skill"


def test_parallel_social_request_selects_multiple_skills():
    plan = deterministic_skill_plan(
        "Create an Instagram Reel script, a YouTube video script, and a LinkedIn post"
    )
    assert {"instagram-agent-skill", "youtube-agent-skill", "linkedin-agent-skill"}.issubset(plan)


def test_unknown_skill_ids_are_rejected():
    assert _parse_plan('{"selected_skills":["seo-agent-skill","made-up-agent"]}') == ["seo-agent-skill"]


def test_skill_waves_parallelize_independent_content_workers():
    waves = _ready_waves(["instagram-agent-skill", "youtube-agent-skill", "linkedin-agent-skill"])
    assert len(waves) == 1
    assert set(waves[0]) == {"instagram-agent-skill", "youtube-agent-skill", "linkedin-agent-skill"}


def test_dependency_waves_order_scrape_browser_sales():
    waves = _ready_waves(["google-maps-scraper-kit", "browser-agent-skill", "sales-desk-skill"])
    assert waves[0] == ["google-maps-scraper-kit"]
    assert waves[1] == ["browser-agent-skill"]
    assert waves[2] == ["sales-desk-skill"]


@pytest.mark.asyncio
async def test_execute_plan_records_failures_without_losing_other_artifacts(monkeypatch):
    from core import skill_supervisor

    async def fake_execute(skill_id, task, context=None):
        if skill_id == "youtube-agent-skill":
            raise RuntimeError("model unavailable")
        return f"output for {skill_id}"

    monkeypatch.setattr(skill_supervisor.skill_registry, "execute_skill", fake_execute)
    result = await skill_supervisor.execute_skill_plan(
        "Create a YouTube video and Instagram Reel",
        ["youtube-agent-skill", "instagram-agent-skill"],
    )
    assert result["skills"]["instagram-agent-skill"]["status"] == "completed"
    assert result["skills"]["youtube-agent-skill"]["status"] == "failed"
    assert len(result["execution_waves"]) == 1
