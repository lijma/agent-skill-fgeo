"""fgeo goal — Manage project goals."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from fgeo.database import get_db

console = Console()
goal_app = typer.Typer(help="Manage goals — what you want to achieve for a project.")


@goal_app.command("add")
def add(
    project: str = typer.Argument(help="Project name"),
    title: str = typer.Argument(help="Goal title (e.g. '让所有人了解fcontext')"),
) -> None:
    """Add a goal to a project."""
    db = get_db()
    try:
        goal = db.add_goal(project, title)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        db.close()

    console.print(f"[green]✓[/green] Goal added: [bold]{goal['title']}[/bold]  (ID: {goal['id']})")


@goal_app.command("list")
def list_goals(
    project: str = typer.Argument(help="Project name"),
) -> None:
    """List goals for a project."""
    db = get_db()
    goals = db.list_goals(project)
    db.close()

    if not goals:
        console.print(f"[yellow]No goals found for '{project}'.[/yellow]")
        console.print(f"  Run: [cyan]fgeo goal add {project} \"your goal\"[/cyan]")
        return

    table = Table(title=f"🎯 Goals — {project}")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Status", style="magenta")
    table.add_column("Created", style="dim")

    for g in goals:
        status_icon = {"active": "●", "achieved": "✓", "paused": "⏸", "abandoned": "✗"}.get(g["status"], "○")
        table.add_row(g["id"], g["title"], f"{status_icon} {g['status']}", g["created_at"][:10])

    console.print(table)


@goal_app.command("set")
def set_field(
    goal_id: str = typer.Argument(help="Goal ID"),
    field: str = typer.Argument(help="Field to update: title, status"),
    value: str = typer.Argument(help="New value (status: active|achieved|abandoned|paused)"),
) -> None:
    """Update a goal field."""
    db = get_db()
    result = db.update_goal(goal_id, field, value)
    db.close()

    if not result:
        console.print(f"[red]Failed to update. Check goal ID and field ({field}).[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Goal {goal_id}: {field} → {value}")
