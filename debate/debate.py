from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from .llm import make_llm
from .personas import DebateConfig, Persona


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona: Persona
    content: str
    round_num: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DebateState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = ""
    config: DebateConfig = Field(default_factory=DebateConfig)
    turns: list[Turn] = Field(default_factory=list)
    current_round: int = 0
    is_finished: bool = False


class DebateEngine(Runnable[dict[str, Any], DebateState]):
    """A LangChain Runnable that orchestrates a multi-persona debate.

    Input: {"topic": "optional topic", "config": "optional DebateConfig override"}
    Output: DebateState with all turns
    """

    def __init__(self, config: DebateConfig | None = None):
        self.config = config or DebateConfig()

    def _make_topic_chain(self) -> Runnable:
        moderator = self.config.moderator

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are {name}, the {role}.\n"
                        "{personality}\n\n"
                        "Come up with ONE debate topic for the office staff to argue about.\n"
                        "Focus areas (pick one or combine):\n"
                        "{directions}\n\n"
                        "Return ONLY the topic text, nothing else."
                    ),
                ),
                ("human", "Generate a debate topic now."),
            ]
        )

        return (
            prompt
            | make_llm(moderator.llm, self.config)
            | StrOutputParser()
            | (lambda s: s.strip().strip('"').strip("'"))
        ).with_config(run_name="generate_topic")

    def _make_persona_chain(self, persona: Persona) -> Runnable:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                (
                    "human",
                    (
                        "The debate topic is: {topic}\n\n"
                        "Here is the conversation so far:\n{context}\n\n"
                        "Now respond as {name} ({role})."
                    ),
                ),
            ]
        ).partial(
            system_prompt=persona.system_prompt(),
            name=persona.name,
            role=persona.role,
        )

        return (prompt | make_llm(persona.llm, self.config) | StrOutputParser()).with_config(
            run_name=f"persona_{persona.name}",
        )

    def _build_context(self, state: DebateState) -> str:
        if not state.turns:
            return "The debate has just started. Be the first to speak."
        lines = []
        for t in state.turns:
            p = t.persona
            header = f"[Round {t.round_num}] {p.avatar} {p.name} ({p.role})"
            lines.append(f"{header}:\n{t.content}\n")
        return "\n".join(lines)

    # --- Runnable protocol ---

    def invoke(self, input: dict[str, Any], config: RunnableConfig | None = None) -> DebateState:
        return asyncio_run(self.ainvoke(input, config))

    async def ainvoke(
        self, input: dict[str, Any], config: RunnableConfig | None = None
    ) -> DebateState:
        topic = input.get("topic", "")
        state = DebateState(topic=topic, config=self.config)

        # Generate topic if not provided
        if not state.topic:
            moderator = self.config.moderator
            chain = self._make_topic_chain()
            state.topic = await chain.ainvoke(
                {
                    "name": moderator.name,
                    "role": moderator.role,
                    "personality": moderator.personality,
                    "directions": "\n".join(f"- {d}" for d in moderator.topic_directions),
                }
            )

        # Run rounds
        for _ in range(self.config.max_rounds):
            state.current_round += 1
            context = self._build_context(state)

            for persona in self.config.personas:
                chain = self._make_persona_chain(persona)
                content = await chain.ainvoke(
                    {
                        "topic": state.topic,
                        "context": context,
                    }
                )
                turn = Turn(
                    persona=persona,
                    content=content,
                    round_num=state.current_round,
                )
                state.turns.append(turn)
                header = (
                    f"[Round {state.current_round}] "
                    f"{persona.avatar} {persona.name} ({persona.role})"
                )
                context += f"\n\n{header}:\n{content}\n"

        state.is_finished = True
        return state

    def batch(
        self,
        inputs: list[dict[str, Any]],
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> list[DebateState]:
        return asyncio_run(self.abatch(inputs, config, **kwargs))

    async def abatch(
        self,
        inputs: list[dict[str, Any]],
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> list[DebateState]:
        import asyncio

        return list(await asyncio.gather(*(self.ainvoke(inp, config) for inp in inputs)))

    def stream(
        self, input: dict[str, Any], config: RunnableConfig | None = None, **kwargs: Any
    ) -> Iterator[Turn]:
        return asyncio_run(self.astream(input, config, **kwargs))

    async def astream(
        self, input: dict[str, Any], config: RunnableConfig | None = None, **kwargs: Any
    ):
        topic = input.get("topic", "")
        state = DebateState(topic=topic, config=self.config)

        if not state.topic:
            moderator = self.config.moderator
            chain = self._make_topic_chain()
            state.topic = await chain.ainvoke(
                {
                    "name": moderator.name,
                    "role": moderator.role,
                    "personality": moderator.personality,
                    "directions": "\n".join(f"- {d}" for d in moderator.topic_directions),
                }
            )
            yield state

        for _ in range(self.config.max_rounds):
            state.current_round += 1
            context = self._build_context(state)

            for persona in self.config.personas:
                chain = self._make_persona_chain(persona)
                content = await chain.ainvoke(
                    {
                        "topic": state.topic,
                        "context": context,
                    }
                )
                turn = Turn(
                    persona=persona,
                    content=content,
                    round_num=state.current_round,
                )
                state.turns.append(turn)
                header = (
                    f"[Round {state.current_round}] "
                    f"{persona.avatar} {persona.name} ({persona.role})"
                )
                context += f"\n\n{header}:\n{content}\n"
                yield turn

        state.is_finished = True


def asyncio_run(coro):
    """Run an async coroutine from sync context."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)
