from __future__ import annotations

from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ConfigDict, Field

from .personas import DebateConfig, LlmConfig

_llm_cache: dict[str, Any] = {}


def make_llm(llm_config: LlmConfig, config: DebateConfig):
    model = llm_config.model or config.llm.model
    if not model:
        raise ValueError(
            "No model configured. Set OPENAI_MODEL in .env, "
            "or configure llm.model in personas.yaml."
        )
    base_url = llm_config.base_url or config.llm.base_url or ""
    api_key = llm_config.api_key or config.llm.api_key or ""

    cache_key = f"{model}|{base_url}|{api_key}"
    if cache_key not in _llm_cache:
        kwargs: dict[str, Any] = {
            "model": model,
            "model_provider": "openai",
            "temperature": config.temperature,
        }
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        _llm_cache[cache_key] = init_chat_model(**kwargs)
    return _llm_cache[cache_key]


class HealthCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Entity name")
    model: str = Field(description="Model name")
    base_url: str = Field(default="", description="Base URL")
    ok: bool = Field(description="Whether the model responded successfully")
    error: str = Field(default="", description="Error message if failed")


async def check_model_health(config: DebateConfig) -> list[HealthCheckResult]:
    results: list[HealthCheckResult] = []

    seen: set[str] = set()
    entities: list[tuple[str, LlmConfig]] = []

    for p in config.personas:
        m = p.llm.model or config.llm.model
        b = p.llm.base_url or config.llm.base_url or ""
        k = p.llm.api_key or config.llm.api_key or ""
        key = f"{m}|{b}|{k}"
        if key not in seen:
            seen.add(key)
            entities.append((f"{p.name} ({p.role})", p.llm))

    mm = config.moderator.llm.model or config.llm.model
    mb = config.moderator.llm.base_url or config.llm.base_url or ""
    mk = config.moderator.llm.api_key or config.llm.api_key or ""
    m_key = f"{mm}|{mb}|{mk}"
    if m_key not in seen:
        seen.add(m_key)
        entities.append(
            (f"{config.moderator.name} ({config.moderator.role})", config.moderator.llm)
        )

    for name, llm_c in entities:
        try:
            llm = make_llm(llm_c, config)
            resp = await llm.ainvoke([HumanMessage(content="Reply with exactly: ok")])
            ok = bool(resp.content.strip())
            resolved_model = llm_c.model or config.llm.model
            resolved_base = llm_c.base_url or config.llm.base_url or ""
            results.append(
                HealthCheckResult(
                    name=name,
                    model=resolved_model,
                    base_url=resolved_base,
                    ok=ok,
                    error="" if ok else "Empty response",
                )
            )
        except Exception as e:
            resolved_model = llm_c.model or config.llm.model
            resolved_base = llm_c.base_url or config.llm.base_url or ""
            results.append(
                HealthCheckResult(
                    name=name,
                    model=resolved_model,
                    base_url=resolved_base,
                    ok=False,
                    error=str(e),
                )
            )

    return results
