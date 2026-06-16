"""fgeo CLI — Generative Engine Optimization CLI

AI-powered content asset management and multi-platform distribution.
"""

from __future__ import annotations

import typer
from rich.console import Console

from fgeo import __version__
from fgeo.commands.brand import brand_app
from fgeo.commands.content import content_app
from fgeo.commands.project import project_app
from fgeo.commands.goal import goal_app
from fgeo.commands.platform import platform_app
from fgeo.commands.plan import plan_app
from fgeo.commands.publish import publish_app
from fgeo.commands.status import status_command
from fgeo.commands.style import style_app
from fgeo.commands.enable import SUPPORTED_AGENTS

console = Console()

app = typer.Typer(
    name="fgeo",
    help="fgeo — Generative Engine Optimization CLI.\n\nAI-powered content asset management and multi-platform distribution.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Sub-command groups
app.add_typer(brand_app, name="brand")
app.add_typer(project_app, name="project")
app.add_typer(goal_app, name="goal")
app.add_typer(platform_app, name="platform")
app.add_typer(plan_app, name="plan")
app.add_typer(content_app, name="content")
app.add_typer(publish_app, name="publish")
app.add_typer(style_app, name="style")

# Top-level commands
app.command("status")(status_command)


@app.command()
def init() -> None:
    """Initialize fgeo — create ~/.fgeo global directory with config and database."""
    from fgeo.commands.init import init as _init

    _init()


@app.command()
def enable(
    agent: str = typer.Argument(help=f"Agent to enable: {', '.join(SUPPORTED_AGENTS)} (or 'list')"),
) -> None:
    """Enable AI agent integration — sets up fcontext + fgeo skill instructions."""
    from fgeo.commands.enable import enable as _enable

    _enable(agent)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
) -> None:
    if version:
        console.print(f"fgeo {__version__}")
        raise typer.Exit()
