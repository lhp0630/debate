from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml
from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, ConfigDict, Field

# Default config bundled with the package
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "personas.yaml"

# Working config directory (project root / .work)
WORK_DIR = Path.cwd() / ".work"
WORK_CONFIG_PATH = WORK_DIR / "personas.yaml"


class LlmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(default="", description="Model name, e.g. gpt-4o-mini")
    base_url: str = Field(default="", description="API base URL for custom providers")
    api_key: str = Field(default="", description="API key (falls back to env OPENAI_API_KEY)")


class Persona(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Display name of the persona")
    role: str = Field(description="Job title or office role")
    personality: str = Field(description="Core personality traits")
    speaking_style: str = Field(default="", description="How this persona talks")
    stance: str = Field(default="", description="Typical stance on issues")
    expertise: str = Field(default="", description="Domain expertise")
    avatar: str = Field(default="👤", description="Emoji avatar")
    llm: LlmConfig = Field(default_factory=LlmConfig, description="Per-persona model config")

    def system_prompt(self) -> str:
        prompt_parts = [
            f"You are {self.name}, a {self.role} in an office.",
            f"Personality: {self.personality}",
        ]
        if self.speaking_style:
            prompt_parts.append(f"Speaking style: {self.speaking_style}")
        if self.expertise:
            prompt_parts.append(f"Expertise: {self.expertise}")
        if self.stance:
            prompt_parts.append(f"Stance: {self.stance}")
        prompt_parts.append(
            "You are in a debate with other colleagues. "
            "Respond to the previous speaker's arguments with your own perspective. "
            "Keep your response under 200 words. Be engaged and conversational."
        )
        return "\n".join(prompt_parts)


class Moderator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="Dr. Morgan Lee", description="Moderator display name")
    role: str = Field(default="Moderator / Host", description="Role title")
    personality: str = Field(
        default="Sharp-witted, fair-minded, keeps things on track",
        description="Core personality traits",
    )
    speaking_style: str = Field(default="Concise, authoritative but friendly")
    expertise: str = Field(default="Facilitation, topic curation, debate framing")
    avatar: str = Field(default="🎙️")
    topic_directions: list[str] = Field(
        default_factory=lambda: [
            "Company policy and strategy",
            "Technology adoption",
            "Work culture and lifestyle",
            "Ethics and governance",
        ],
        description="Suggested focus areas for topic generation",
    )
    llm: LlmConfig = Field(default_factory=LlmConfig, description="Per-moderator model config")

    def system_prompt(self) -> str:
        return (
            f"You are {self.name}, the {self.role} of an office debate show.\n"
            f"Personality: {self.personality}\n"
            f"Speaking style: {self.speaking_style}\n\n"
            "Your job is to come up with a single debate topic that would spark "
            "an interesting, multi-perspective argument among the office staff.\n\n"
            "The topic should be:\n"
            "- Specific enough to be debatable (not too vague)\n"
            "- Relevant to a modern workplace\n"
            "- Something reasonable people could disagree on\n\n"
            "IMPORTANT: Return ONLY the topic text, nothing else. No quotes, no explanation."
        )


class DebateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moderator: Moderator = Field(default_factory=Moderator)
    topic: str = Field(default="", description="Fixed topic (empty = moderator generates)")
    personas: list[Persona] = Field(default_factory=list)
    max_rounds: int = Field(default=5, ge=1, description="Number of debate rounds")
    llm: LlmConfig = Field(
        default_factory=LlmConfig,
        description="Global model config (fallback for all personas/moderator)",
    )
    temperature: float = Field(default=0.8, ge=0.0, le=2.0)


def _ensure_work_config() -> Path:
    """Ensure .work/ directory and personas.yaml exist, copy defaults if missing."""
    if not WORK_DIR.exists():
        WORK_DIR.mkdir(parents=True, exist_ok=True)

    if not WORK_CONFIG_PATH.exists():
        if DEFAULT_CONFIG_PATH.exists():
            shutil.copy2(DEFAULT_CONFIG_PATH, WORK_CONFIG_PATH)
        else:
            raise FileNotFoundError(
                f"Default config not found: {DEFAULT_CONFIG_PATH}\n"
                f"Cannot initialize {WORK_CONFIG_PATH}"
            )

    return WORK_CONFIG_PATH


def load_config(path: str | Path | None = None) -> DebateConfig:
    env_file = find_dotenv(usecwd=True)
    load_dotenv(env_file)

    path = _ensure_work_config() if path is None else Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f) or {}
    # yaml: llm: with all keys commented out produces None
    if data.get("llm") is None:
        data["llm"] = {}
    config = DebateConfig(**data)

    # Env vars fill empty values (lower priority than yaml)
    env_model = os.getenv("OPENAI_MODEL", "")
    env_base_url = os.getenv("OPENAI_BASE_URL", "")
    env_api_key = os.getenv("OPENAI_API_KEY", "")

    if not config.llm.model and env_model:
        config.llm.model = env_model
    if not config.llm.base_url and env_base_url:
        config.llm.base_url = env_base_url
    if not config.llm.api_key and env_api_key:
        config.llm.api_key = env_api_key

    return config
