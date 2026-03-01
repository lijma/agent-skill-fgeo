"""fgeo style — Platform writing style management."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fgeo.database import get_db

console = Console()
style_app = typer.Typer(help="Manage platform writing styles (applies across all projects).")

STYLE_FIELDS = ["desc", "formula", "tone", "format"]
FIELD_LABELS = {
    "desc":    "Description",
    "formula": "Writing Formula",
    "tone":    "Tone & Voice",
    "format":  "Format Rules",
}
ALIASES = {"x": "twitter", "wechat": "公众号", "bilibili": "B站"}


def _resolve(platform: str) -> str:
    return ALIASES.get(platform.lower(), platform)


@style_app.command("add")
def add(
    platform: str = typer.Argument(help="Platform name (e.g. twitter, devto, 公众号). Aliases: x→twitter, wechat→公众号, bilibili→B站"),
    desc: str = typer.Option("", "--desc", help="Short description of the platform and its audience"),
    formula: str = typer.Option("", "--formula", help="Content structure formula (e.g. hook→problem→solution→CTA)"),
    tone: str = typer.Option("", "--tone", help="Tone and voice rules"),
    fmt: str = typer.Option("", "--format", help="Format requirements (word count, tags, images, etc.)"),
) -> None:
    """Add a writing style for a platform."""
    db = get_db()
    try:
        style = db.add_style(platform, desc=desc, formula=formula, tone=tone, fmt=fmt)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        db.close()

    console.print(f"[green]✓[/green] Style added for platform [cyan]{style['platform']}[/cyan]")
    _print_style(style)


@style_app.command("show")
def show(
    platform: str = typer.Argument(help="Platform name (or alias: x, wechat, bilibili)"),
) -> None:
    """Show writing style for a platform."""
    db = get_db()
    style = db.get_style(platform)
    db.close()

    resolved = _resolve(platform)
    if not style:
        console.print(Panel(
            f"[yellow]No writing style found for '{resolved}'.[/yellow]\n\n"
            f"Run: [cyan]fgeo style add {resolved} --desc \"...\" --formula \"...\"[/cyan]",
            title=f"📝 Style — {resolved}",
            border_style="yellow",
        ))
        return

    _print_style(style)


@style_app.command("list")
def list_styles() -> None:
    """List all platform writing styles."""
    db = get_db()
    styles = db.list_styles()
    db.close()

    if not styles:
        console.print("[yellow]No styles defined yet.[/yellow]")
        console.print("  Run: [cyan]fgeo style add <platform> --desc \"...\"[/cyan]")
        return

    table = Table(title="📝 Writing Styles")
    table.add_column("Platform", style="cyan", no_wrap=True)
    table.add_column("Description", style="bold")
    table.add_column("Formula", style="dim")
    table.add_column("Updated", style="dim")

    for s in styles:
        table.add_row(
            s["platform"],
            s["desc"] or "[dim](not set)[/dim]",
            s["formula"] or "[dim](not set)[/dim]",
            s["updated_at"][:10],
        )

    console.print(table)


@style_app.command("set")
def set_field(
    platform: str = typer.Argument(help="Platform name (or alias)"),
    field: str = typer.Argument(help=f"Field to update: {', '.join(STYLE_FIELDS)}"),
    value: str = typer.Argument(help="New value"),
) -> None:
    """Update a field in a platform's writing style."""
    if field not in STYLE_FIELDS:
        console.print(f"[red]Unknown field '{field}'. Choose from: {', '.join(STYLE_FIELDS)}[/red]")
        raise typer.Exit(1)

    db = get_db()
    result = db.update_style(platform, field, value)
    db.close()

    if not result:
        resolved = _resolve(platform)
        console.print(f"[red]Style not found for '{resolved}'. Run 'fgeo style add {resolved}' first.[/red]")
        raise typer.Exit(1)

    resolved = _resolve(platform)
    console.print(f"[green]✓[/green] style[cyan][{resolved}].{field}[/cyan] → {value}")


def _print_style(style: dict) -> None:
    table = Table(
        title=f"📝 Style — {style['platform']}",
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    table.add_column("Field", style="dim", min_width=12)
    table.add_column("Value", style="bold")

    for field in STYLE_FIELDS:
        val = style.get(field, "")
        table.add_row(FIELD_LABELS[field], val if val else "[dim](not set)[/dim]")

    console.print(table)
    if style.get("updated_at"):
        console.print(f"  [dim]Last updated: {style['updated_at'][:19]}[/dim]")
