"""fgeo project — Create and manage projects."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fgeo.database import get_db

console = Console()
project_app = typer.Typer(help="Manage projects — the targets of your content promotion.")


@project_app.command("create")
def create(
    name: str = typer.Argument(help="Project name (e.g. fcontext)"),
    description: str = typer.Option("", "--desc", "-d", help="Project description"),
    workspace: str = typer.Option("", "--workspace", "-w", help="Workspace path for this project"),
) -> None:
    """Create a new project."""
    db = get_db()
    try:
        proj = db.create_project(name=name, description=description, workspace=workspace)
    except Exception as e:
        if "UNIQUE" in str(e):
            console.print(f"[red]Project '{name}' already exists.[/red]")
            raise typer.Exit(1)
        raise  # pragma: no cover
    finally:
        db.close()

    console.print(
        Panel.fit(
            f"[bold green]Project created![/bold green]\n\n"
            f"  ID:   [cyan]{proj['id']}[/cyan]\n"
            f"  Name: [bold]{proj['name']}[/bold]\n"
            f"  Desc: {proj['description'] or '[dim](none)[/dim]'}",
            title="📦 fgeo project",
            border_style="green",
        )
    )


@project_app.command("list")
def list_projects(
    status: str = typer.Option("", "--status", "-s", help="Filter by status: active, archived"),
) -> None:
    """List all projects."""
    db = get_db()
    projects = db.list_projects(status=status)
    db.close()

    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        console.print("  Run: [cyan]fgeo project create <name>[/cyan]")
        return

    table = Table(title=f"📦 Projects ({len(projects)})")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Status", style="magenta")
    table.add_column("Created", style="dim")

    for p in projects:
        table.add_row(
            p["id"],
            p["name"],
            p["description"][:40] if p["description"] else "",
            p["status"],
            p["created_at"][:10],
        )

    console.print(table)


@project_app.command("show")
def show(
    name: str = typer.Argument(help="Project name or ID"),
) -> None:
    """Show project details."""
    db = get_db()
    proj = db.get_project(name)
    goals = db.list_goals(name) if proj else []
    platforms = db.list_platforms(name) if proj else []
    plans = db.list_plans(name) if proj else []
    db.close()

    if not proj:
        console.print(f"[red]Project not found: {name}[/red]")
        raise typer.Exit(1)

    info = (
        f"  ID:          [cyan]{proj['id']}[/cyan]\n"
        f"  Name:        [bold]{proj['name']}[/bold]\n"
        f"  Description: {proj['description'] or '[dim](none)[/dim]'}\n"
        f"  Workspace:   {proj['workspace'] or '[dim](none)[/dim]'}\n"
        f"  Status:      {proj['status']}\n"
        f"  Created:     {proj['created_at'][:10]}\n"
    )

    if goals:
        info += "\n  [bold]Goals:[/bold]\n"
        for g in goals:
            icon = "●" if g["status"] == "active" else "✓" if g["status"] == "achieved" else "○"
            info += f"    {icon} {g['title']} [{g['status']}]\n"

    if platforms:
        info += "\n  [bold]Platforms:[/bold]\n"
        for pl in platforms:
            info += f"    • {pl['name']} — {pl['directions'] or '(no directions)'}\n"

    if plans:
        info += "\n  [bold]Plans:[/bold]\n"
        for p in plans:
            icon = "●" if p["status"] == "active" else "✓" if p["status"] == "completed" else "○"
            info += f"    {icon} {p['name']} [{p['status']}]\n"

    console.print(Panel.fit(info, title="📦 Project Detail", border_style="blue"))


@project_app.command("set")
def set_field(
    name: str = typer.Argument(help="Project name or ID"),
    field: str = typer.Argument(help="Field to update: description, workspace, status"),
    value: str = typer.Argument(help="New value"),
) -> None:
    """Update a project field."""
    db = get_db()
    result = db.update_project(name, field, value)
    db.close()

    if not result:
        console.print(f"[red]Failed to update. Check project name and field ({field}).[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] {result['name']}: {field} → {value}")


@project_app.command("remove")
def remove(
    name: str = typer.Argument(help="Project name or ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove a project and all related data (goals, platforms, plans, content)."""
    db = get_db()
    proj = db.get_project(name)

    if not proj:
        console.print(f"[red]Project not found: {name}[/red]")
        db.close()
        raise typer.Exit(1)

    if not force:
        console.print(f"  Removing project: [bold]{proj['name']}[/bold] ({proj['id']})")
        console.print("  [yellow]This will delete ALL related goals, platforms, plans, and content.[/yellow]")
        if not typer.confirm("Are you sure?", default=False):
            db.close()
            raise typer.Abort()

    counts = db.delete_project(proj["id"])
    db.close()

    console.print(f"[green]✓[/green] Removed project: [bold]{proj['name']}[/bold]")
    if counts:
        parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
        if parts:
            console.print(f"  Cleaned up: {', '.join(parts)}")
