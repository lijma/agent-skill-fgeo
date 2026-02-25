"""fgeo status — Project dashboard showing overall progress."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fgeo.database import get_db

console = Console()


def status_command(
    project: str = typer.Argument(help="Project name"),
    platform: str = typer.Option("", "--platform", "-p", help="Show details for specific platform"),
) -> None:
    """Show project status dashboard — goals, plans, platforms, content progress."""
    db = get_db()
    data = db.project_status(project)
    db.close()

    if not data:
        console.print(f"[red]Project not found: {project}[/red]")
        raise typer.Exit(1)

    proj = data["project"]

    # If specific platform requested
    if platform:
        plat_data = [p for p in data["platforms"] if p["name"] == platform]
        if not plat_data:
            console.print(f"[red]Platform '{platform}' not found for project '{project}'.[/red]")
            raise typer.Exit(1)
        _show_platform_detail(project, plat_data[0], data["plans"])
        return

    # Project header
    console.print()
    console.print(f"[bold]📦 {proj['name']}[/bold]  [dim]{proj['description']}[/dim]")
    console.print()

    # Goals
    if data["goals"]:
        console.print("[bold]🎯 Goals[/bold]")
        for g in data["goals"]:
            icon = {"active": "● ", "achieved": "✓ ", "paused": "⏸ ", "abandoned": "✗ "}.get(g["status"], "○ ")
            style = "green" if g["status"] == "achieved" else "yellow" if g["status"] == "active" else "dim"
            console.print(f"  [{style}]{icon}{g['title']}[/{style}]")
        console.print()

    # Plans
    if data["plans"]:
        console.print("[bold]📋 Plans[/bold]")
        for p in data["plans"]:
            icon = {"active": "●", "completed": "✓", "draft": "○", "archived": "▪"}.get(p["status"], "?")
            console.print(f"  {icon} [bold]{p['name']}[/bold] [{p['status']}]  {p['strategy'][:50]}")
            if p["assignments"]:
                for a in p["assignments"]:
                    pct = f"{a['done']}/{a['target']}" if a["target"] > 0 else str(a["done"])
                    bar = ""
                    if a["target"] > 0:
                        filled = min(10, int(10 * a["done"] / a["target"]))
                        bar = f" [{'█' * filled}{'░' * (10 - filled)}]"
                    console.print(f"      {a['platform']}/{a['direction'] or '*'}: {pct}{bar}")
        console.print()

    # Platform summary table
    if data["platforms"]:
        table = Table(title="📡 Platform Summary")
        table.add_column("Platform", style="bold")
        table.add_column("Directions", style="blue")
        table.add_column("Pace", style="magenta")
        table.add_column("Published", style="green", justify="right")
        table.add_column("Draft", style="yellow", justify="right")
        table.add_column("Planned", style="dim", justify="right")
        table.add_column("Total", justify="right")
        table.add_column("Last", style="dim")

        for p in data["platforms"]:
            table.add_row(
                p["name"],
                p["directions"] or "-",
                p["pace"] or "-",
                str(p["published"]),
                str(p["draft"]),
                str(p["planned"]),
                str(p["total"]),
                p["last_published_at"][:10] if p["last_published_at"] else "-",
            )

        console.print(table)


def _show_platform_detail(project: str, plat: dict, plans: list) -> None:
    """Show detailed view for a single platform."""
    info = (
        f"  [bold]{plat['name']}[/bold] — {project}\n"
        f"  Directions: {plat['directions'] or '(none)'}\n"
        f"  Pace:       {plat['pace'] or '(none)'}\n\n"
        f"  Published: [green]{plat['published']}[/green]  "
        f"Draft: [yellow]{plat['draft']}[/yellow]  "
        f"Planned: [dim]{plat['planned']}[/dim]  "
        f"Total: {plat['total']}\n"
    )

    # Show related plan assignments
    related_plans = []
    for p in plans:
        for a in p.get("assignments", []):
            if a["platform"] == plat["name"]:
                related_plans.append({"plan": p["name"], "direction": a["direction"], "target": a["target"], "done": a["done"]})

    if related_plans:
        info += "\n  [bold]Plan Assignments:[/bold]\n"
        for rp in related_plans:
            pct = f"{rp['done']}/{rp['target']}" if rp["target"] > 0 else str(rp["done"])
            info += f"    • {rp['plan']} / {rp['direction'] or '*'}: {pct}\n"

    console.print(Panel.fit(info, title=f"📡 Platform Detail", border_style="blue"))
