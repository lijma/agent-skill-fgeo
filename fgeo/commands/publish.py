"""fgeo publish — Publish content to platforms."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fgeo.constants import FGEO_HOME
from fgeo.database import get_db

console = Console()
publish_app = typer.Typer(help="Publish content to platforms.")
task_app = typer.Typer(help="Manage publish tasks (git PR workflow).")
publish_app.add_typer(task_app, name="task")

# Platform names with built-in publishing support
BLOG_PLATFORM = "blog"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _date_prefix() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _with_date_prefix(filename: str) -> str:
    """Add YYYY-MM-DD- prefix if not already present."""
    if re.match(r"^\d{4}-\d{2}-\d{2}-", filename):
        return filename
    return f"{_date_prefix()}-{filename}"


def _resolve_platform_row(db, platform_id: str | None) -> dict:
    """Return the full platform row (name, publish_url, …) or empty dict."""
    if not platform_id:
        return {}
    row = db.conn.execute("SELECT * FROM platforms WHERE id=?", (platform_id,)).fetchone()
    return dict(row) if row else {}


def _run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)


def _make_task_id(content_id: str) -> str:
    h = hashlib.sha256(f"{content_id}-{datetime.now().isoformat()}".encode()).hexdigest()[:8]
    return f"ptask-{h}"


def _git_remote_to_web_url(remote: str) -> str:
    """Convert a git remote URL to its GitHub web base URL.

    git@github.com:user/repo.git  →  https://github.com/user/repo
    https://github.com/user/repo.git  →  https://github.com/user/repo
    """
    remote = remote.strip()
    m = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", remote)
    if m:
        return f"https://{m.group(1)}/{m.group(2)}"
    if remote.endswith(".git"):
        return remote[:-4]
    return remote


# ── Blog git-PR flow ──────────────────────────────────────────────────────────

def _publish_blog_git(
    db,
    content: dict,
    content_id: str,
    title: str,
    src: Path,
    publish_url: str,
    now_iso: str,
    force: bool = False,
) -> None:
    """Clone the blog repo, push a branch, open a PR, and create a publish task."""
    task_id = _make_task_id(content_id)
    task_dir = FGEO_HOME / "publish" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = task_dir / "repo"
    branch = f"fgeo/{content_id}"

    console.print(f"[dim]Cloning {publish_url} …[/dim]")
    clone = _run_git(["clone", publish_url, str(repo_dir)])
    if clone.returncode != 0:
        console.print(f"[red]git clone failed:[/red]\n{clone.stderr}")
        raise typer.Exit(1)

    # Use -B to reset the branch if it already exists (needed when --force)
    _run_git(["checkout", "-B", branch], cwd=repo_dir)

    # Copy article into docs/posts/
    posts_dir = repo_dir / "docs" / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)
    dest_name = _with_date_prefix(src.name)
    shutil.copy2(src, posts_dir / dest_name)

    _run_git(["add", "-A"], cwd=repo_dir)
    _run_git(["commit", "-m", f"publish: {title}"], cwd=repo_dir)

    console.print("[dim]Pushing branch …[/dim]")
    push_args = ["push", "-u", "origin", branch]
    if force:
        push_args.append("--force-with-lease")
    push = _run_git(push_args, cwd=repo_dir)
    if push.returncode != 0:
        console.print(f"[red]git push failed:[/red]\n{push.stderr}")
        raise typer.Exit(1)

    # Try gh pr create (optional — falls back to compare URL if gh not installed/configured)
    pr_url = ""
    compare_url = f"{_git_remote_to_web_url(publish_url)}/compare/{branch}?expand=1"
    if not shutil.which("gh"):
        console.print(
            "[yellow]GitHub CLI (gh) not found.[/yellow] "
            "Install it to create PRs automatically:\n"
            "  [bold]brew install gh[/bold]  (macOS)\n"
            "  [bold]winget install --id GitHub.cli[/bold]  (Windows)\n"
            "  [bold]https://cli.github.com[/bold]"
        )
    else:
        gh = subprocess.run(
            ["gh", "pr", "create",
             "--title", f"publish: {title}",
             "--body", f"Published via fgeo\n\nContent ID: `{content_id}`",
             "--head", branch],
            cwd=repo_dir, capture_output=True, text=True,
        )
        if gh.returncode == 0 and gh.stdout.strip():
            pr_url = gh.stdout.strip().splitlines()[-1]

    # Record task
    db.create_publish_task(
        task_id=task_id,
        content_id=content_id,
        platform_id=content.get("platform_id") or "",
        repo_url=publish_url,
        branch=branch,
        task_dir=str(task_dir),
        pr_url=pr_url,
        status="pr_open",
    )

    body = (
        f"[bold]Branch:[/bold]    {branch}\n"
        f"[bold]Task ID:[/bold]   {task_id}\n"
    )
    if pr_url:
        body += f"[bold]PR URL:[/bold]    {pr_url}\n"
    else:
        body += (
            f"[bold]Open PR:[/bold]   {compare_url}\n"
            f"[dim](gh not available — click the link above to create the PR on GitHub)[/dim]\n"
        )
    body += f"\nAfter merging, run: [bold]fgeo publish task done {task_id}[/bold]"
    console.print(Panel(body, title=f"[green]✓ PR ready[/green] — {title}"))


# ── Blog local-copy flow (fallback when publish_url not set) ─────────────────

def _publish_blog_local(
    db,
    content_id: str,
    title: str,
    src: Path,
    blog_dir: str,
    force: bool,
    workspace: str,
    now_iso: str,
) -> None:
    """Copy article directly into the local blog posts directory."""
    if blog_dir:
        posts_dir = Path(blog_dir)
    elif workspace:
        posts_dir = Path(workspace) / "platforms" / "blog" / "docs" / "posts"
    else:
        console.print("[red]Cannot determine blog posts directory.[/red]")
        console.print("Use [bold]--blog-dir[/bold] to specify the destination folder.")
        raise typer.Exit(1)

    posts_dir.mkdir(parents=True, exist_ok=True)
    dest_name = _with_date_prefix(src.name)
    dest = posts_dir / dest_name

    if dest.exists() and not force:
        console.print(f"[yellow]Destination already exists:[/yellow] {dest}")
        console.print("Use [bold]--force[/bold] to overwrite.")
        raise typer.Exit(1)

    shutil.copy2(src, dest)
    db.update_content(content_id, "status", "published")
    db.update_content(content_id, "published_at", now_iso)
    db.update_content(content_id, "published_url", str(dest))

    console.print(Panel(
        f"[bold]Source:[/bold]  {src}\n"
        f"[bold]Dest:[/bold]    {dest}\n"
        f"[bold]Status:[/bold]  draft → [green]published[/green]",
        title=f"[green]✓ Published to blog (local)[/green] — {title}",
    ))


# ── publish content ───────────────────────────────────────────────────────────

@publish_app.command("content")
def publish_content(
    content_id: str = typer.Argument(help="Content ID to publish"),
    blog_dir: str = typer.Option("", "--blog-dir", help="(local mode) Override blog posts directory"),
    url: str = typer.Option("", "--url", help="Published URL to record (non-blog platforms)"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite destination file (local mode) / force-push branch (git mode)"),
) -> None:
    """Publish a content item to its platform.

    Blog with publish_url set: git clone → branch → commit → push → PR → task.
    Blog without publish_url: copy file locally (--blog-dir or workspace path).
    Other platforms: mark published and record URL.
    """
    db = get_db()
    content = db.get_content(content_id)
    if not content:
        console.print(f"[red]Content not found:[/red] {content_id}")
        raise typer.Exit(1)

    if content["status"] == "published":
        console.print(f"[yellow]Already published:[/yellow] {content_id}")
        raise typer.Exit(0)

    platform = _resolve_platform_row(db, content.get("platform_id"))
    platform_name = platform.get("name") or ""
    publish_url = platform.get("publish_url") or ""
    source_path = content.get("source_path") or ""
    workspace = content.get("workspace") or ""
    now_iso = datetime.now().isoformat(timespec="seconds")
    title = content.get("title") or content_id

    if platform_name == BLOG_PLATFORM:
        if not source_path:
            console.print("[red]No source file path recorded for this content.[/red]")
            console.print(f"Run: [bold]fgeo content set {content_id} source_path <path>[/bold]")
            raise typer.Exit(1)

        src = Path(source_path)
        if not src.exists():
            console.print(f"[red]Source file not found:[/red] {source_path}")
            raise typer.Exit(1)

        if publish_url:
            _publish_blog_git(db, content, content_id, title, src, publish_url, now_iso, force=force)
        else:
            _publish_blog_local(db, content_id, title, src, blog_dir, force, workspace, now_iso)

    else:
        db.update_content(content_id, "status", "published")
        db.update_content(content_id, "published_at", now_iso)
        if url:
            db.update_content(content_id, "published_url", url)

        body = f"[bold]Platform:[/bold] {platform_name or 'unknown'}\n"
        body += f"[bold]Status:[/bold]  draft → [green]published[/green]\n"
        if url:
            body += f"[bold]URL:[/bold]     {url}"
        else:
            body += "[dim]Tip: use --url to record the published URL.[/dim]"

        console.print(Panel(body, title=f"[green]✓ Marked as published[/green] — {title}"))


# ── publish list ──────────────────────────────────────────────────────────────

@publish_app.command("list")
def list_publishable(
    project: str = typer.Option("", "--project", "-p", help="Filter by project name"),
    platform: str = typer.Option("", "--platform", help="Filter by platform name"),
    status: str = typer.Option("draft", "--status", "-s", help="Status filter (default: draft)"),
) -> None:
    """List content items ready to publish."""
    db = get_db()
    items = db.list_contents(
        project_name=project,
        platform_name=platform if project else "",
        status=status,
    )

    if not items:
        console.print(f"[yellow]No content with status '{status}'.[/yellow]")
        return

    table = Table(title=f"📋 Publishable Content — status={status}")
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Platform")
    table.add_column("Project")
    table.add_column("Source File")

    for item in items:
        src = item.get("source_path") or ""
        table.add_row(
            item["id"],
            (item.get("title") or "")[:42],
            item.get("platform_name") or "—",
            item.get("project_name") or "—",
            Path(src).name if src else "—",
        )
    console.print(table)


# ── publish task subcommands ──────────────────────────────────────────────────

@task_app.command("list")
def task_list(
    status: str = typer.Option("", "--status", "-s", help="Filter: pr_open, merged, failed"),
    content_id: str = typer.Option("", "--content", "-c", help="Filter by content ID"),
) -> None:
    """List publish tasks."""
    db = get_db()
    tasks = db.list_publish_tasks(status=status, content_id=content_id)

    if not tasks:
        msg = f"No publish tasks{' with status ' + status if status else ''}."
        console.print(f"[yellow]{msg}[/yellow]")
        return

    STATUS_COLOR = {"pr_open": "yellow", "merged": "green", "failed": "red"}
    table = Table(title="📬 Publish Tasks")
    table.add_column("Task ID", style="dim")
    table.add_column("Content")
    table.add_column("Branch")
    table.add_column("Status")
    table.add_column("PR URL")
    table.add_column("Created")

    for t in tasks:
        color = STATUS_COLOR.get(t["status"], "white")
        table.add_row(
            t["id"],
            (t.get("content_title") or t.get("content_id") or "")[:36],
            (t.get("branch") or "")[:40],
            f"[{color}]{t['status']}[/{color}]",
            t.get("pr_url") or "—",
            (t.get("created_at") or "")[:16],
        )
    console.print(table)


@task_app.command("show")
def task_show(
    task_id: str = typer.Argument(help="Publish task ID"),
) -> None:
    """Show details of a publish task."""
    db = get_db()
    task = db.get_publish_task(task_id)
    if not task:
        console.print(f"[red]Task not found:[/red] {task_id}")
        raise typer.Exit(1)

    info = (
        f"[bold]ID:[/bold]         {task['id']}\n"
        f"[bold]Content:[/bold]    {task['content_id']}\n"
        f"[bold]Status:[/bold]     {task['status']}\n"
        f"[bold]Branch:[/bold]     {task.get('branch') or '—'}\n"
        f"[bold]Repo URL:[/bold]   {task.get('repo_url') or '—'}\n"
        f"[bold]PR URL:[/bold]     {task.get('pr_url') or '—'}\n"
        f"[bold]Task Dir:[/bold]   {task.get('task_dir') or '—'}\n"
        f"[bold]Created:[/bold]    {task.get('created_at') or '—'}\n"
    )
    if task["status"] == "pr_open":
        info += f"\n[dim]After merging, run:[/dim] [bold]fgeo publish task done {task_id}[/bold]"
    console.print(Panel(info, title=f"Publish Task — {task_id}"))


@task_app.command("done")
def task_done(
    task_id: str = typer.Argument(help="Task ID to mark as merged/published"),
) -> None:
    """Mark a publish task as merged and update content status to published."""
    db = get_db()
    task = db.get_publish_task(task_id)
    if not task:
        console.print(f"[red]Task not found:[/red] {task_id}")
        raise typer.Exit(1)

    if task["status"] == "merged":
        console.print(f"[yellow]Task already merged:[/yellow] {task_id}")
        raise typer.Exit(0)

    db.update_publish_task(task_id, "status", "merged")

    content_id = task["content_id"]
    now_iso = datetime.now().isoformat(timespec="seconds")
    db.update_content(content_id, "status", "published")
    db.update_content(content_id, "published_at", now_iso)
    if task.get("pr_url"):
        db.update_content(content_id, "published_url", task["pr_url"])

    console.print(Panel(
        f"[bold]Task:[/bold]     {task_id}\n"
        f"[bold]Content:[/bold]  {content_id}\n"
        f"[bold]Status:[/bold]   pr_open → [green]merged[/green]\n"
        f"[bold]Content:[/bold]  → [green]published[/green]",
        title="[green]✓ Task done — content published[/green]",
    ))
