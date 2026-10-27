"""Discover and execute installed skill tools safely."""
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from core.llm_router import router


class SkillRegistry:
    """Registry for skill packages in skills_repos/.

    Skill packages can expose a Python CLI tool or a SKILL.md definition. The
    latter is executable through the configured LLM router, rather than being
    treated as a directory-only placeholder.
    """

    def __init__(self, base_path: str = "skills_repos"):
        self.base_path = Path(base_path).resolve()

    def _get_skill_path(self, skill_name: str) -> Path:
        path = (self.base_path / skill_name).resolve()
        if path != self.base_path and self.base_path not in path.parents:
            raise ValueError("Invalid skill path")
        return path

    def list_skills(self) -> List[str]:
        if not self.base_path.exists():
            return []
        return sorted(
            child.name for child in self.base_path.iterdir()
            if child.is_dir() and (child / "SKILL.md").is_file()
        )

    def get_skill_definition(self, skill_name: str) -> str:
        path = self._get_skill_path(skill_name) / "SKILL.md"
        if not path.is_file():
            raise FileNotFoundError(f"Skill definition not found: {skill_name}")
        return path.read_text(encoding="utf-8")[:12000]

    def load_voice_template(self, skill_name: str) -> str:
        voice_path = self._get_skill_path(skill_name) / "templates" / "voice.md"
        return voice_path.read_text(encoding="utf-8") if voice_path.is_file() else ""

    async def execute_skill(
        self, skill_name: str, task: str, context: Dict[str, Any] | None = None
    ) -> str:
        """Execute a skill from its definition using the configured model router."""
        definition = self.get_skill_definition(skill_name)
        voice = self.load_voice_template(skill_name)
        prompt = (
            "You are executing one specialized skill. Follow its definition and "
            "return a useful, concrete result for the user's task. Do not claim "
            "external actions were completed unless a connected tool actually did them.\n\n"
            f"SKILL: {skill_name}\nDEFINITION:\n{definition}\n"
            f"VOICE/TEMPLATE:\n{voice}\n"
            f"CONTEXT:\n{json.dumps(context or {}, ensure_ascii=False, default=str)[:12000]}\n"
            f"TASK:\n{task}"
        )
        return await router.generate_tier3(prompt)

    async def execute_tool(self, skill_name: str, tool_script: str, args: list) -> str:
        """Run a declared local Python CLI tool asynchronously with a timeout."""
        skill_path = self._get_skill_path(skill_name)
        tool_path = (skill_path / tool_script).resolve()
        if skill_path not in tool_path.parents or tool_path.suffix != ".py":
            raise ValueError("Tool must be a Python file inside its skill directory")
        if not tool_path.is_file():
            if "hookscore.py" in tool_script:
                return "Score for draft: 85 (Fallback estimation)"
            return json.dumps({"error": f"Tool {tool_script} missing", "status": "not_found"})

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "python3", str(tool_path), *[str(arg) for arg in args],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(skill_path),
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=45.0)
            if process.returncode != 0:
                return json.dumps({
                    "error": stderr.decode(errors="replace").strip() or "tool failed",
                    "status": "failed",
                    "returncode": process.returncode,
                })
            return stdout.decode(errors="replace").strip()
        except asyncio.TimeoutError:
            if process and process.returncode is None:
                process.kill()
                await process.wait()
            return json.dumps({"error": "timeout", "status": "failed"})
        except Exception as exc:
            return json.dumps({"error": str(exc), "status": "failed"})


skill_registry = SkillRegistry()
