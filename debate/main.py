from __future__ import annotations

import asyncio

import fire
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .debate import DebateEngine, DebateState, Turn
from .llm import check_model_health
from .personas import DebateConfig, load_config

console = Console()


def print_moderator(config: DebateConfig) -> None:
    m = config.moderator
    model_info = m.llm.model or config.llm.model or "default"
    console.print(
        Panel(
            f"[bold]{m.name}[/bold] — {m.role}\n"
            f"{m.personality}\n"
            f"Focus areas: {', '.join(m.topic_directions)}\n"
            f"Model: [dim]{model_info}[/dim]",
            title=f"{m.avatar} Moderator",
            border_style="magenta",
        )
    )
    console.print()


def print_personas(config: DebateConfig) -> None:
    table = Table(title="Office Participants", show_header=True, header_style="bold cyan")
    table.add_column("", style="bold")
    table.add_column("Name", style="green")
    table.add_column("Role", style="yellow")
    table.add_column("Personality")
    table.add_column("Model", style="dim")
    for p in config.personas:
        model = p.llm.model or config.llm.model or "default"
        table.add_row(p.avatar, p.name, p.role, p.personality[:50], model)
    console.print(table)
    console.print()


def print_turn(turn: Turn) -> None:
    header = f"{turn.persona.avatar} {turn.persona.name} ({turn.persona.role})"
    console.print(
        Panel(
            Markdown(turn.content),
            title=f"[bold]{header}[/bold]",
            subtitle=f"Round {turn.round_num}",
            border_style="blue",
        )
    )
    console.print()


def print_summary(state: DebateState) -> None:
    console.rule("[bold green]Debate Complete[/bold green]")
    console.print(f"\n[bold]Topic:[/bold] {state.topic}")
    console.print(f"[bold]Total rounds:[/bold] {state.current_round}")
    console.print(f"[bold]Total statements:[/bold] {len(state.turns)}\n")

    table = Table(title="Participation Summary", show_header=True)
    table.add_column("Participant", style="green")
    table.add_column("Statements", justify="right")
    table.add_column("Avg Length", justify="right")
    for persona in {t.persona.name for t in state.turns}:
        turns = [t for t in state.turns if t.persona.name == persona]
        avg_len = sum(len(t.content) for t in turns) // len(turns)
        table.add_row(f"{turns[0].persona.avatar} {persona}", str(len(turns)), f"{avg_len} chars")
    console.print(table)


async def _async_run(config_path: str | None):
    config = load_config(config_path)

    console.rule("[bold magenta]Office Debate[/bold magenta]")
    console.print(f"[bold]Model (global):[/bold] {config.llm.model or 'default'}")
    console.print(f"[bold]Rounds:[/bold] {config.max_rounds}\n")

    # Health check
    console.print("[bold yellow]Checking model connectivity...[/bold yellow]\n")
    results = await check_model_health(config)
    table = Table(title="Model Health Check", show_header=True, header_style="bold cyan")
    table.add_column("Entity", style="green")
    table.add_column("Model", style="dim")
    table.add_column("Base URL", style="dim")
    table.add_column("Status")
    for r in results:
        status = "[green]OK[/green]" if r.ok else f"[red]FAIL[/red] — {r.error[:60]}"
        table.add_row(r.name, r.model, r.base_url or "default", status)
    console.print(table)
    console.print()

    failed = [r for r in results if not r.ok]
    if failed:
        console.print("[bold red]Some models are unreachable. Aborting.[/bold red]")
        raise SystemExit(1)

    print_moderator(config)
    print_personas(config)

    engine = DebateEngine(config)

    console.print("[bold yellow]Generating debate topic...[/bold yellow]\n")

    state: DebateState | None = None
    current_round = 0

    async for item in engine.astream({"topic": ""}):
        if isinstance(item, DebateState):
            state = item
            console.print(
                Panel(
                    Markdown(f"**{state.topic}**"),
                    title=f"{config.moderator.avatar} {config.moderator.name} announces the topic",
                    border_style="magenta",
                )
            )
            console.print()
        elif isinstance(item, Turn):
            if item.round_num != current_round:
                current_round = item.round_num
                console.rule(f"[bold yellow]Round {current_round}[/bold yellow]")
            print_turn(item)

    if state is None:
        state = DebateState(topic="", config=config)

    print_summary(state)


def run(config: str | None = None):
    """Run the office debate.

    Args:
        config: Path to personas.yaml config file.
                If not provided, uses .work/personas.yaml (auto-created from defaults).
    """
    asyncio.run(_async_run(config))


def main():
    fire.Fire(run)
