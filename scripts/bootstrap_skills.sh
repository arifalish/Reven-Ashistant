#!/bin/bash

# Bootstraps the 13 skill repositories into skills_repos/

SKILLS_DIR="skills_repos"
mkdir -p "$SKILLS_DIR"
cd "$SKILLS_DIR" || exit 1

echo "Bootstrapping Skill Repositories..."

# Mocking the clone process as actual repos might not be available
# In production, replace the 'mkdir' with 'git clone'

REPOS=(
    "instagram-agent-skill"
    "youtube-agent-skill"
    "linkedin-agent-skill"
    "x-agent-skill"
    "founder-skill"
    "trader-skill"
    "replica-skill"
    "arena-skill"
    "master-skills"
    "google-maps-scraper-kit"
    "sales-desk-skill"
    "humanizer-core-skill"
    "seo-agent-skill"
)

for repo in "${REPOS[@]}"; do
    echo "Processing $repo..."
    if [ ! -d "$repo" ]; then
        mkdir -p "$repo/templates"
        mkdir -p "$repo/skills"

        # Create a mock SKILL.md and voice.md
        echo "# $repo SKILL DEFINITION" > "$repo/SKILL.md"
        echo "Voice template for $repo" > "$repo/templates/voice.md"

        # Create a mock python tool if needed, e.g., hookscore.py for youtube
        if [ "$repo" == "youtube-agent-skill" ]; then
            echo 'import sys; print(f"Score for {sys.argv[1]}: 95")' > "$repo/hookscore.py"
        fi

        echo "Successfully set up mock $repo"
    else
        echo "$repo already exists. Skipping."
    fi
done

echo "Bootstrap complete."
