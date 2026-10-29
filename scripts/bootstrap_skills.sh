#!/usr/bin/env bash
set -euo pipefail

# Creates runnable skill packages for the centralized skill registry.
# Skill execution is model-backed; external scraping/browser actions still require
# their respective service credentials and endpoints to be configured.
SKILLS_DIR="${SKILLS_DIR:-skills_repos}"
mkdir -p "$SKILLS_DIR"

write_skill() {
  local slug="$1"
  local title="$2"
  local purpose="$3"
  local workflow="$4"
  local guardrails="$5"
  local dir="$SKILLS_DIR/$slug"
  mkdir -p "$dir/templates" "$dir/skills"
  if [[ ! -f "$dir/SKILL.md" ]]; then
  cat > "$dir/SKILL.md" <<EOF
# $title

## Mission
$purpose

## Workflow
$workflow

## Output contract
- Return a concrete deliverable, not generic advice.
- State assumptions and missing inputs explicitly.
- Separate verified facts from suggestions and estimates.
- Reuse relevant prior artifacts from the shared blackboard.
- Do not claim an external action, scrape, browser visit, deployment, or message send occurred unless a configured tool returned a successful result.

## Safety and quality
$guardrails
EOF
  fi
  if [[ ! -f "$dir/templates/voice.md" ]]; then
  cat > "$dir/templates/voice.md" <<EOF
Use concise, specific, professional language. Prefer structured outputs and actionable next steps. Never invent evidence, metrics, sources, or completed actions.
EOF
  fi
}

write_skill "instagram-agent-skill" "Instagram Content Agent" "Create Instagram Reels and posts that fit the target audience and objective." "Identify audience and hook; write a short script, caption, CTA and relevant hashtag suggestions; note any assumptions." "Avoid engagement bait, misleading claims and unlicensed content."
write_skill "youtube-agent-skill" "YouTube Agent" "Create retention-aware YouTube scripts and packaging ideas." "Provide title options, opening hook, outline/script, thumbnail concepts and a clear CTA." "Do not invent analytics or promise a specific view count."
write_skill "linkedin-agent-skill" "LinkedIn Agent" "Create professional LinkedIn posts, carousel outlines and ethical B2B outreach." "Match audience and tone; provide a strong opening, useful insight, CTA and optional carousel structure." "Do not fabricate personal relationships or pretend the sender knows the recipient."
write_skill "x-agent-skill" "X Social Agent" "Create concise X posts, threads and campaign hooks." "Draft a strong first post, logically sequenced thread, concise close and optional variants." "Respect factual accuracy and platform character constraints."
write_skill "founder-skill" "Founder Strategy Agent" "Validate business ideas and build practical go-to-market and unit-economics plans." "Define customer, problem, offer, alternatives, risks, experiments, pricing assumptions and measurable milestones." "Clearly label estimates and do not present simulated buyer feedback as real research."
write_skill "trader-skill" "Trading Research Agent" "Explain market, portfolio and company fundamentals with risk-aware analysis." "State timeframe, assumptions, key drivers, downside scenarios and questions needing current data." "Do not fabricate live prices, trades, filings or guarantee returns."
write_skill "replica-skill" "Software Engineering Agent" "Design and implement software, API, website and application features." "Clarify requirements; propose architecture; deliver code, tests, setup steps and known limitations." "Never claim code was run or deployed unless execution evidence is available."
write_skill "arena-skill" "Engineering Review Arena" "Review technical approaches and compare alternatives as a code-review tournament." "Produce independent solution options, compare correctness, maintainability, security and tests, then recommend one." "Do not claim parallel external agents ran unless the runtime confirms it."
write_skill "master-skills" "Master Coordinator Agent" "Coordinate cross-functional work and synthesize complex tasks into an executable plan." "Break the request into workstreams, dependencies, owners, deliverables and acceptance checks." "Do not override domain-specific constraints or conceal uncertainty."
write_skill "google-maps-scraper-kit" "Local Business Lead Research" "Organize local business lead collection using a configured scraper service." "Extract target city, business category and filters; use supplied scraper artifacts; return normalized CSV/JSON and source/status metadata." "Never invent phone numbers, emails, ratings or businesses. If no scraper endpoint is configured, report that limitation and provide a ready-to-run query plan."
write_skill "sales-desk-skill" "B2B Sales Desk" "Create personalized B2B cold emails and follow-up sequences from available lead records." "Use each lead's actual company and available context; produce subject, email, follow-up timing and personalization evidence." "Never pretend a website was visited or a prospect was contacted when no tool confirms it."
write_skill "humanizer-core-skill" "Humanizer and Quality Editor" "Improve clarity and naturalness without changing the underlying meaning." "Remove robotic phrasing and stray invisible characters; preserve facts, names, IDs, code, citations and data." "Do not promise text is 100% human or undetectable."
write_skill "seo-agent-skill" "SEO Research Agent" "Build keyword clusters, search-intent mapping and on-page SEO recommendations." "Group topics by intent; suggest page targets, titles, internal links and validation metrics." "Do not claim live rankings or competitor data without a configured source."
write_skill "browser-agent-skill" "Browser Automation Agent" "Plan and, when configured, execute browser workflows and website research." "Define URLs, steps, extracted fields and evidence; use connected browser tools where available; report action status." "Do not claim a site was opened or data scraped unless a browser tool returned evidence. Require approval before irreversible external actions."
write_skill "opendots-coworker-skill" "OpenDots Autonomous Coworker" "Coordinate longer-running workspace and shell tasks through configured coworker/container tools." "Break work into milestones, commands, expected outputs, retries and checkpoints." "Do not claim a persistent container or command exists unless the configured tool confirms it."

if [[ -f "$SKILLS_DIR/youtube-agent-skill/hookscore.py" ]]; then
  : # Preserve an existing local hook-scoring tool.
else
  cat > "$SKILLS_DIR/youtube-agent-skill/hookscore.py" <<'PY'
import sys
draft = " ".join(sys.argv[1:])
score = 50
if draft:
    score += min(25, len(draft) // 8)
    if any(word in draft.lower() for word in ("how", "why", "secret", "mistake", "stop")):
        score += 15
print(f"Score for draft: {min(score, 95)}")
PY
fi

echo "Bootstrapped 15 skill packages in $SKILLS_DIR"
