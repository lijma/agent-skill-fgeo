"""fgeo init — Initialize ~/.fgeo global directory and workspace integration."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from fgeo.constants import FGEO_HOME, FGEO_SKILLS_DIR
from fgeo.config import save_config, get_default_config, FGEO_CONFIG_FILE
from fgeo.database import get_db, FGEO_DB_FILE

console = Console()


def init() -> None:
    """Initialize fgeo — create ~/.fgeo global directory with config and database."""

    if FGEO_HOME.exists():
        console.print(f"[yellow]~/.fgeo already exists at {FGEO_HOME}[/yellow]")
        if not typer.confirm("Reinitialize?", default=False):
            raise typer.Abort()

    # Create directory structure
    FGEO_HOME.mkdir(parents=True, exist_ok=True)
    FGEO_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    # Write default config
    if not FGEO_CONFIG_FILE.exists():
        save_config(get_default_config())
        console.print(f"  [green]✓[/green] created {FGEO_CONFIG_FILE}")

    # Initialize SQLite database
    db = get_db()
    db.close()
    console.print(f"  [green]✓[/green] created {FGEO_DB_FILE}")

    console.print()
    console.print(
        Panel.fit(
            "[bold green]fgeo initialized![/bold green]\n\n"
            f"  Home:     [cyan]{FGEO_HOME}[/cyan]\n"
            f"  Config:   [cyan]{FGEO_CONFIG_FILE}[/cyan]\n"
            f"  Database: [cyan]{FGEO_DB_FILE}[/cyan]\n\n"
            "Next steps:\n"
            "  1. [bold]fgeo enable copilot[/bold]  — activate AI agent integration\n"
            "  2. [bold]fgeo project create <name>[/bold] — create your first project",
            title="🚀 fgeo",
            border_style="green",
        )
    )
