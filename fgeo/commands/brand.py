"""fgeo brand — Global author brand profile management."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fgeo.database import get_db

console = Console()
brand_app = typer.Typer(help="Manage global author brand profile (user-level, applies across all projects).")

BRAND_FIELDS = ["name", "positioning", "voice", "core_values", "topics"]
FIELD_LABELS = {
    "name":        "Author Name",
    "positioning": "Positioning",
    "voice":       "Voice & Tone",
    "core_values": "Core Values",
    "topics":      "Topic Domains",
}
FIELD_HINTS = {
    "name":        "e.g. Marvin Ma · MarvinTalk",
    "positioning": "e.g. 产品技术人 × AI工具链布道者",
    "voice":       "e.g. 直接、有观点、技术感强、偶尔幽默",
    "core_values": "e.g. 工具驱动生产力、AI Native、持续输出",
    "topics":      "e.g. AI工具、GEO/SEO、系统设计、Developer Tools",
}


@brand_app.command("show")
def show() -> None:
    """Show current brand profile."""
    db = get_db()
    brand = db.get_brand()
    db.close()

    is_empty = all(not brand.get(f) for f in BRAND_FIELDS)

    if is_empty:
        console.print(Panel(
            "[yellow]Brand profile not set up yet.[/yellow]\n\n"
            "Run [cyan]fgeo brand set <field> <value>[/cyan] to fill in your profile.\n"
            "Fields: " + ", ".join(BRAND_FIELDS),
            title="🎨 Brand Profile",
            border_style="yellow",
        ))
        return

    table = Table(title="🎨 Brand Profile", show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="dim", min_width=14)
    table.add_column("Value", style="bold")

    for field in BRAND_FIELDS:
        val = brand.get(field, "")
        label = FIELD_LABELS[field]
        table.add_row(label, val if val else "[dim](not set)[/dim]")

    console.print(table)
    if brand.get("updated_at"):
        console.print(f"  [dim]Last updated: {brand['updated_at'][:19]}[/dim]")


@brand_app.command("set")
def set_field(
    field: str = typer.Argument(help=f"Field to set: {', '.join(BRAND_FIELDS)}"),
    value: str = typer.Argument(help="New value"),
) -> None:
    """Set a brand profile field."""
    if field not in BRAND_FIELDS:
        console.print(f"[red]Unknown field '{field}'. Choose from: {', '.join(BRAND_FIELDS)}[/red]")
        raise typer.Exit(1)

    db = get_db()
    result = db.set_brand(field, value)
    db.close()

    if not result:
        console.print(f"[red]Failed to set brand field '{field}'.[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] brand.[cyan]{field}[/cyan] → {value}")


@brand_app.command("init")
def init() -> None:
    """Print brand setup guide for AI-assisted onboarding."""
    console.print(Panel(
        "[bold]Brand onboarding guide[/bold]\n\n"
        "This command is intended to be called by AI agents during onboarding.\n"
        "The AI should interview the user and then call [cyan]fgeo brand set[/cyan] for each field.\n\n"
        "[bold]Fields to fill:[/bold]\n"
        + "\n".join(
            f"  [cyan]fgeo brand set {f} \"...\"[/cyan]  — {FIELD_HINTS[f]}"
            for f in BRAND_FIELDS
        ),
        title="🎨 Brand Init",
        border_style="cyan",
    ))
