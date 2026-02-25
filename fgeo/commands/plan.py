"""fgeo plan — Manage GTM plans that orchestrate platforms."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fgeo.database import get_db

console = Console()
plan_app = typer.Typer(help="Manage plans — orchestrate content across platforms to achieve goals.")


@plan_app.command("create")
def create(
    project: str = typer.Argument(help="Project name"),
    name: str = typer.Argument(help="Plan name (e.g. 'cold-start', 'cn-expansion')"),
    strategy: str = typer.Option("", "--strategy", "-s", help="Plan strategy description"),
    goal_id: str = typer.Option("", "--goal", "-g", help="Goal ID this plan serves"),
) -> None:
    """Create a new plan for a project."""
    db = get_db()
    try:
        plan = db.create_plan(project, name, goal_id=goal_id, strategy=strategy)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        if "UNIQUE" in str(e):
            console.print(f"[red]Plan '{name}' already exists for project '{project}'.[/red]")
            raise typer.Exit(1)
        raise  # pragma: no cover
    finally:
        db.close()

    console.print(
        f"[green]✓[/green] Plan created: [bold]{plan['name']}[/bold] → {project}"
    )


@plan_app.command("list")
def list_plans(
    project: str = typer.Argument(help="Project name"),
    status: str = typer.Option("", "--status", "-s", help="Filter by status: draft, active, completed, archived"),
) -> None:
    """List plans for a project."""
    db = get_db()
    plans = db.list_plans(project, status=status)
    db.close()

    if not plans:
        console.print(f"[yellow]No plans found for '{project}'.[/yellow]")
        console.print(f"  Run: [cyan]fgeo plan create {project} \"plan-name\"[/cyan]")
        return

    table = Table(title=f"📋 Plans — {project}")
    table.add_column("Name", style="bold")
    table.add_column("Strategy")
    table.add_column("Status", style="magenta")
    table.add_column("Goal", style="dim")
    table.add_column("Created", style="dim")

    for p in plans:
        icon = {"active": "●", "completed": "✓", "draft": "○", "archived": "▪"}.get(p["status"], "?")
        table.add_row(
            p["name"],
            (p["strategy"][:40] + "...") if len(p["strategy"]) > 40 else p["strategy"],
            f"{icon} {p['status']}",
            p["goal_id"] or "-",
            p["created_at"][:10],
        )

    console.print(table)


@plan_app.command("show")
def show(
    project: str = typer.Argument(help="Project name"),
    name: str = typer.Argument(help="Plan name"),
) -> None:
    """Show plan details with platform assignments and progress."""
    db = get_db()
    plan = db.get_plan(project, name)
    if not plan:
        console.print(f"[red]Plan '{name}' not found for project '{project}'.[/red]")
        db.close()
        raise typer.Exit(1)

    assignments = db.list_plan_platforms(project, name)

    # Calculate progress for each assignment
    progress_data = []
    for a in assignments:
        done = db.conn.execute(
            "SELECT COUNT(*) FROM contents WHERE plan_id=? AND platform_id=? AND status='published'",
            (plan["id"], a["platform_id"]),
        ).fetchone()[0]
        progress_data.append({**dict(a), "done": done})

    db.close()

    info = (
        f"  Plan:     [bold]{plan['name']}[/bold]\n"
        f"  Strategy: {plan['strategy'] or '(none)'}\n"
        f"  Status:   {plan['status']}\n"
        f"  Goal:     {plan['goal_id'] or '(none)'}\n"
        f"  Created:  {plan['created_at'][:10]}\n"
    )

    if progress_data:
        info += "\n  [bold]Platform Assignments:[/bold]\n"
        for a in progress_data:
            pct = f"{a['done']}/{a['target_count']}" if a["target_count"] > 0 else f"{a['done']}"
            bar = ""
            if a["target_count"] > 0:
                filled = int(10 * a["done"] / a["target_count"])
                bar = f" [{'█' * filled}{'░' * (10 - filled)}]"
            info += f"    • {a['platform_name']} / {a['direction'] or '*'} — {pct}{bar}\n"
    else:
        info += "\n  [dim]No platform assignments yet.[/dim]\n"
        info += f"  Run: [cyan]fgeo plan assign {project} {name} <platform>[/cyan]\n"

    console.print(Panel.fit(info, title=f"📋 Plan Detail", border_style="blue"))


@plan_app.command("assign")
def assign(
    project: str = typer.Argument(help="Project name"),
    name: str = typer.Argument(help="Plan name"),
    platform: str = typer.Argument(help="Platform name to assign"),
    direction: str = typer.Option("", "--direction", "-d", help="Content direction for this assignment"),
    target: int = typer.Option(0, "--target", "-t", help="Target content count"),
) -> None:
    """Assign a platform to a plan with direction and target."""
    db = get_db()
    result = db.assign_plan_platform(project, name, platform, direction=direction, target=target)
    db.close()

    if not result:
        console.print(f"[red]Failed. Check project/plan/platform names.[/red]")
        raise typer.Exit(1)

    target_str = f", target: {target}" if target > 0 else ""
    console.print(
        f"[green]✓[/green] Assigned: {platform} / {direction or '*'} → plan '{name}'{target_str}"
    )


@plan_app.command("set")
def set_field(
    project: str = typer.Argument(help="Project name"),
    name: str = typer.Argument(help="Plan name"),
    field: str = typer.Argument(help="Field: strategy, status, goal_id"),
    value: str = typer.Argument(help="New value"),
) -> None:
    """Update a plan field."""
    db = get_db()
    result = db.update_plan(project, name, field, value)
    db.close()

    if not result:
        console.print(f"[red]Failed to update. Check project/plan name and field ({field}).[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Plan {name}: {field} → {value}")
