"""fgeo platform — Manage platform task queues per project."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fgeo.database import get_db

console = Console()
platform_app = typer.Typer(help="Manage platforms — independent content channels per project.")


@platform_app.command("add")
def add(
    project: str = typer.Argument(help="Project name"),
    name: str = typer.Argument(help="Platform name (e.g. twitter, devto, 公众号)"),
    directions: str = typer.Option("", "--directions", "-d", help="Comma-separated content directions"),
    pace: str = typer.Option("", "--pace", "-p", help="Publishing pace (e.g. '3/周', '2/月')"),
) -> None:
    """Add a platform to a project."""
    db = get_db()
    try:
        plat = db.add_platform(project, name, directions=directions, pace=pace)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        if "UNIQUE" in str(e):
            console.print(f"[red]Platform '{name}' already exists for project '{project}'.[/red]")
            raise typer.Exit(1)
        raise  # pragma: no cover
    finally:
        db.close()

    console.print(
        f"[green]✓[/green] Platform added: [bold]{plat['name']}[/bold] "
        f"→ {project}  [directions: {plat['directions'] or '(none)'}]"
    )


@platform_app.command("list")
def list_platforms(
    project: str = typer.Argument(help="Project name"),
) -> None:
    """List platforms for a project."""
    db = get_db()
    platforms = db.list_platforms(project)
    db.close()

    if not platforms:
        console.print(f"[yellow]No platforms found for '{project}'.[/yellow]")
        console.print(f"  Run: [cyan]fgeo platform add {project} twitter[/cyan]")
        return

    table = Table(title=f"📡 Platforms — {project}")
    table.add_column("Name", style="bold")
    table.add_column("Directions", style="blue")
    table.add_column("Pace", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Last Published", style="dim")

    for p in platforms:
        table.add_row(
            p["name"],
            p["directions"] or "(none)",
            p["pace"] or "(none)",
            p["status"],
            p["last_published_at"][:10] if p["last_published_at"] else "-",
        )

    console.print(table)


@platform_app.command("show")
def show(
    project: str = typer.Argument(help="Project name"),
    name: str = typer.Argument(help="Platform name"),
) -> None:
    """Show platform details with content summary."""
    db = get_db()
    plat = db.get_platform(project, name)
    if not plat:
        console.print(f"[red]Platform '{name}' not found for project '{project}'.[/red]")
        db.close()
        raise typer.Exit(1)

    contents = db.list_contents(project_name=project, platform_name=name)
    db.close()

    info = (
        f"  Platform:     [bold]{plat['name']}[/bold]\n"
        f"  Directions:   {plat['directions'] or '(none)'}\n"
        f"  Pace:         {plat['pace'] or '(none)'}\n"
        f"  Status:       {plat['status']}\n"
        f"  Last Publish: {plat['last_published_at'] or '-'}\n"
        f"  Publish URL:  {plat.get('publish_url') or '(not set)'}\n"
    )

    # Content breakdown
    total = len(contents)
    published = sum(1 for c in contents if c["status"] == "published")
    draft = sum(1 for c in contents if c["status"] == "draft")
    planned = sum(1 for c in contents if c["status"] == "planned")
    info += f"\n  [bold]Content:[/bold] {total} total — {published} published, {draft} draft, {planned} planned\n"

    if contents:
        info += "\n  [bold]Recent:[/bold]\n"
        for c in contents[:5]:
            icon = {"published": "✓", "draft": "✎", "planned": "○", "review": "◉"}.get(c["status"], "?")
            info += f"    {icon} {c['title'] or c['id']}  [{c['status']}]\n"

    console.print(Panel.fit(info, title=f"📡 {name} — {project}", border_style="blue"))


@platform_app.command("set")
def set_field(
    project: str = typer.Argument(help="Project name"),
    name: str = typer.Argument(help="Platform name"),
    field: str = typer.Argument(help="Field: directions, pace, status, publish_url, last_published_at"),
    value: str = typer.Argument(help="New value"),
) -> None:
    """Update a platform field."""
    db = get_db()
    result = db.update_platform(project, name, field, value)
    db.close()

    if not result:
        console.print(f"[red]Failed to update. Check project/platform name and field ({field}).[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] {project}/{name}: {field} → {value}")
