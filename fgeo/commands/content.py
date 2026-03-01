"""fgeo content — Register, list, and manage content assets (v0.2 SQLite)."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fgeo.database import get_db

console = Console()
content_app = typer.Typer(help="Manage content assets — atomic pieces of platform-native content.")


def _extract_frontmatter(path: Path) -> dict:
    """Extract frontmatter fields from a markdown file."""
    result: dict = {}
    try:
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        if lines and lines[0].strip() == "---":
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip().lower()
                    value = value.strip().strip("\"'")
                    if key == "tags":
                        value = value.strip("[]")
                        result[key] = [t.strip().strip("\"'") for t in value.split(",") if t.strip()]
                    else:
                        result[key] = value
        if "title" not in result:
            for line in lines:
                if line.startswith("# "):
                    result["title"] = line[2:].strip()
                    break
    except Exception:
        pass
    return result


@content_app.command("register")
def register(
    path: Path = typer.Argument(help="Path to the content file"),
    title: str = typer.Option("", "--title", "-t", help="Override title"),
    project: str = typer.Option("", "--project", "-P", help="Project name"),
    platform: str = typer.Option("", "--platform", help="Platform name"),
    plan: str = typer.Option("", "--plan", help="Plan name"),
    direction: str = typer.Option("", "--direction", "-d", help="Content direction"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
    description: str = typer.Option("", "--desc", help="Content description"),
    content_type: str = typer.Option("", "--type", help="Content type: article, video, slide, thread, short"),
    status: str = typer.Option("draft", "--status", "-s", help="Initial status: planned, draft, review, published"),
) -> None:
    """Register a content file into the fgeo database."""
    if not path.exists():
        console.print(f"[red]File not found: {path}[/red]")
        raise typer.Exit(1)

    path = path.resolve()

    # Extract from frontmatter for markdown files
    if path.suffix.lower() in (".md", ".markdown", ".mdx"):
        fm = _extract_frontmatter(path)
        if not title:
            title = fm.get("title", "")
        if not description:
            description = fm.get("description", "")
        if not tags:
            fm_tags = fm.get("tags", [])
            if isinstance(fm_tags, list):
                tags = ",".join(fm_tags)

    # Auto-detect content type from extension
    if not content_type:
        suffix = path.suffix.lower()
        if suffix in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            content_type = "video"
        elif suffix in (".pptx", ".key", ".pdf"):
            content_type = "slide"
        else:
            content_type = "article"

    if not title:
        title = path.stem.replace("-", " ").replace("_", " ").strip()

    db = get_db()
    entry = db.register_content(
        source_path=str(path),
        title=title,
        project_name=project,
        platform_name=platform,
        plan_name=plan,
        direction=direction,
        description=description,
        content_type=content_type,
        tags=tags,
        status=status,
    )
    db.close()

    console.print(
        Panel.fit(
            f"[bold green]Content registered![/bold green]\n\n"
            f"  ID:        [cyan]{entry['id']}[/cyan]\n"
            f"  Title:     {entry['title'] or '[dim](untitled)[/dim]'}\n"
            f"  Source:    {entry['source_path']}\n"
            f"  Type:      {entry['content_type']}\n"
            f"  Project:   {project or '[dim](none)[/dim]'}\n"
            f"  Platform:  {platform or '[dim](none)[/dim]'}\n"
            f"  Direction: {direction or '[dim](none)[/dim]'}\n"
            f"  Status:    {entry['status']}",
            title="📄 fgeo content",
            border_style="green",
        )
    )


@content_app.command("list")
def list_content(
    project: str = typer.Option("", "--project", "-P", help="Filter by project"),
    platform: str = typer.Option("", "--platform", help="Filter by platform (requires --project)"),
    status: str = typer.Option("", "--status", "-s", help="Filter by status: planned, draft, review, published"),
    direction: str = typer.Option("", "--direction", "-d", help="Filter by direction"),
    no_plan: bool = typer.Option(False, "--no-plan", help="Show only content not assigned to any plan"),
) -> None:
    """List content assets."""
    db = get_db()
    entries = db.list_contents(
        project_name=project,
        platform_name=platform,
        status=status,
        direction=direction,
        no_plan=no_plan,
    )
    db.close()

    if not entries:
        console.print("[yellow]No content found matching filters.[/yellow]")
        console.print("  Run: [cyan]fgeo content register <file>[/cyan]")
        return

    table = Table(title=f"📚 Content ({len(entries)} items)")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Type", style="magenta")
    table.add_column("Project", style="blue")
    table.add_column("Platform", style="green")
    table.add_column("Direction")
    table.add_column("Status", style="yellow")
    table.add_column("Created", style="dim")

    for e in entries:
        table.add_row(
            e["id"],
            (e["title"][:30] + "...") if len(e["title"] or "") > 30 else (e["title"] or ""),
            e["content_type"],
            e.get("project_name") or "-",
            e.get("platform_name") or "-",
            e["direction"] or "-",
            e["status"],
            e["created_at"][:10],
        )

    console.print(table)


@content_app.command("show")
def show(
    content_id: str = typer.Argument(help="Content ID"),
) -> None:
    """Show content details."""
    db = get_db()
    entry = db.get_content(content_id)
    db.close()

    if not entry:
        console.print(f"[red]Content not found: {content_id}[/red]")
        raise typer.Exit(1)

    source_exists = Path(entry["source_path"]).exists() if entry["source_path"] else False

    console.print(
        Panel.fit(
            f"  ID:          [cyan]{entry['id']}[/cyan]\n"
            f"  Title:       [bold]{entry['title'] or '(untitled)'}[/bold]\n"
            f"  Description: {entry['description'] or '(none)'}\n"
            f"  Source:      {entry['source_path'] or '(none)'} {'✓' if source_exists else '✗'}\n"
            f"  Type:        {entry['content_type']}\n"
            f"  Direction:   {entry['direction'] or '(none)'}\n"
            f"  Tags:        {entry['tags'] or '(none)'}\n"
            f"  Status:      {entry['status']}\n"
            f"  URL:         {entry['published_url'] or '(none)'}\n"
            f"  Published:   {entry['published_at'] or '-'}\n"
            f"  Created:     {entry['created_at']}\n"
            f"  Updated:     {entry['updated_at']}",
            title="📄 Content Detail",
            border_style="blue",
        )
    )


@content_app.command("set")
def set_field(
    content_id: str = typer.Argument(help="Content ID"),
    field: str = typer.Argument(help="Field to update: title, description, direction, tags, status, published_url, etc."),
    value: str = typer.Argument(help="New value"),
) -> None:
    """Update a content field."""
    db = get_db()
    result = db.update_content(content_id, field, value)
    db.close()

    if not result:
        console.print(f"[red]Failed to update. Check content ID and field name ({field}).[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Content {content_id}: {field} → {value}")


@content_app.command("assign-plan")
def assign_plan(
    project: str = typer.Argument(help="Project name"),
    plan: str = typer.Argument(help="Plan name"),
    platform: list[str] = typer.Option([], "--platform", "-p", help="Filter by platform name (repeatable). Omit to target all platforms."),
    status: str = typer.Option("", "--status", "-s", help="Filter by content status (draft, published, planned, …). Omit to target all."),
) -> None:
    """Batch-assign a plan to all matching content in a project.

    Examples:
      fgeo content assign-plan myproj gtm-v1
      fgeo content assign-plan myproj gtm-v1 --platform devto --platform medium
      fgeo content assign-plan myproj gtm-v1 --platform twitter --status published
    """
    db = get_db()
    try:
        count = db.assign_plan_to_contents(
            project_name=project,
            plan_name=plan,
            platform_names=list(platform) or None,
            status=status,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    finally:
        db.close()

    filters: list[str] = []
    if platform:
        filters.append(f"platform: {', '.join(platform)}")
    if status:
        filters.append(f"status: {status}")
    filter_str = f"  [dim]({', '.join(filters)})[/dim]" if filters else ""
    console.print(f"[green]✓[/green] Assigned plan [bold]{plan}[/bold] to {count} content(s).{filter_str}")


@content_app.command("remove")
def remove(
    content_id: str = typer.Argument(help="Content ID to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove a content entry from the registry."""
    db = get_db()
    entry = db.get_content(content_id)

    if not entry:
        console.print(f"[red]Content not found: {content_id}[/red]")
        db.close()
        raise typer.Exit(1)

    if not force:
        console.print(f"  Removing: [bold]{entry['title'] or content_id}[/bold]")
        if not typer.confirm("Are you sure?", default=False):
            db.close()
            raise typer.Abort()

    db.remove_content(content_id)
    db.close()
    console.print(f"[green]✓[/green] Removed content: {content_id}")
