import pytest

from skills.browser_agent import IRREVERSIBLE_PATTERNS, _safe_task


@pytest.mark.parametrize(
    "request",
    [
        "Submit my application form",
        "Send this email to the client",
        "Publish this post on LinkedIn",
        "Pay the invoice",
        "Delete the old account",
        "Place the order",
    ],
)
def test_irreversible_web_actions_require_separate_confirmation(request):
    safe_task, confirmation_required = _safe_task(request)
    assert confirmation_required is True
    assert "Do NOT submit or finalize forms" in safe_task


@pytest.mark.parametrize(
    "request",
    [
        "Open the website and read the about page",
        "Search for the latest product prices",
        "Fill my application form but do not submit it",
        "Download the public brochure",
    ],
)
def test_research_and_reversible_web_tasks_can_run_after_mission_approval(request):
    _, confirmation_required = _safe_task(request)
    assert confirmation_required is False


def test_irreversible_pattern_is_case_insensitive():
    assert IRREVERSIBLE_PATTERNS.search("PLEASE SUBMIT")
