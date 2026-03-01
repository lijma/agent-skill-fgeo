"""fgeo database — SQLite data layer for Project/Goal/Platform/Plan/Content."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fgeo.constants import FGEO_HOME

FGEO_DB_FILE = FGEO_HOME / "fgeo.db"

SCHEMA_VERSION = "0.5.0"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    workspace   TEXT DEFAULT '',
    status      TEXT DEFAULT 'active' CHECK(status IN ('active','archived')),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    status      TEXT DEFAULT 'active' CHECK(status IN ('active','achieved','abandoned','paused')),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS platforms (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    directions  TEXT DEFAULT '',
    pace        TEXT DEFAULT '',
    publish_url TEXT DEFAULT '',
    bsky_handle TEXT DEFAULT '',
    platform_secret TEXT DEFAULT '',
    status      TEXT DEFAULT 'active' CHECK(status IN ('active','paused','archived')),
    last_published_at TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS plans (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    goal_id     TEXT DEFAULT NULL REFERENCES goals(id),
    name        TEXT NOT NULL,
    strategy    TEXT DEFAULT '',
    status      TEXT DEFAULT 'active' CHECK(status IN ('draft','active','completed','archived')),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS plan_platforms (
    plan_id     TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    platform_id TEXT NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    direction   TEXT DEFAULT '',
    target_count INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL,
    PRIMARY KEY(plan_id, platform_id, direction)
);

CREATE TABLE IF NOT EXISTS contents (
    id            TEXT PRIMARY KEY,
    project_id    TEXT DEFAULT NULL REFERENCES projects(id),
    platform_id   TEXT DEFAULT NULL REFERENCES platforms(id),
    plan_id       TEXT DEFAULT NULL REFERENCES plans(id),
    direction     TEXT DEFAULT '',
    title         TEXT DEFAULT '',
    description   TEXT DEFAULT '',
    source_path   TEXT DEFAULT '',
    workspace     TEXT DEFAULT '',
    content_type  TEXT DEFAULT 'article' CHECK(content_type IN ('article','video','slide','thread','short')),
    tags          TEXT DEFAULT '',
    status        TEXT DEFAULT 'draft' CHECK(status IN ('planned','draft','review','published','archived')),
    published_url TEXT DEFAULT '',
    published_at  TEXT DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publish_tasks (
    id          TEXT PRIMARY KEY,
    content_id  TEXT NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    platform_id TEXT DEFAULT NULL REFERENCES platforms(id),
    repo_url    TEXT DEFAULT '',
    branch      TEXT DEFAULT '',
    pr_url      TEXT DEFAULT '',
    task_dir    TEXT DEFAULT '',
    status      TEXT DEFAULT 'pr_open' CHECK(status IN ('pr_open','merged','failed')),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS brand (
    id          TEXT PRIMARY KEY DEFAULT 'singleton',
    name        TEXT DEFAULT '',
    positioning TEXT DEFAULT '',
    voice       TEXT DEFAULT '',
    core_values TEXT DEFAULT '',
    topics      TEXT DEFAULT '',
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS styles (
    platform    TEXT PRIMARY KEY,
    desc        TEXT DEFAULT '',
    formula     TEXT DEFAULT '',
    tone        TEXT DEFAULT '',
    format      TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_id(prefix: str, name: str) -> str:
    """Generate a short deterministic ID from prefix + name."""
    import hashlib
    h = hashlib.sha256(name.encode()).hexdigest()[:8]
    return f"{prefix}-{h}"


class Database:
    """SQLite database manager for fgeo."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or FGEO_DB_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init_schema(self) -> None:
        """Create tables if they don't exist. Applies migrations for column additions."""
        self.conn.executescript(SCHEMA_SQL)
        # Migration 0.3.0 → 0.4.0: add publish_url to existing platforms tables
        existing_cols = {
            row[1] for row in self.conn.execute("PRAGMA table_info(platforms)").fetchall()
        }
        if "publish_url" not in existing_cols:
            self.conn.execute("ALTER TABLE platforms ADD COLUMN publish_url TEXT DEFAULT ''")
        if "bsky_handle" not in existing_cols:
            self.conn.execute("ALTER TABLE platforms ADD COLUMN bsky_handle TEXT DEFAULT ''")
        if "platform_secret" not in existing_cols:
            self.conn.execute("ALTER TABLE platforms ADD COLUMN platform_secret TEXT DEFAULT ''")
        self.conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("version", SCHEMA_VERSION),
        )
        self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Projects ──────────────────────────────────────────────────

    def create_project(self, name: str, description: str = "", workspace: str = "") -> dict[str, Any]:
        now = _now()
        pid = _make_id("proj", name)
        self.conn.execute(
            "INSERT INTO projects (id, name, description, workspace, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (pid, name, description, workspace, now, now),
        )
        self.conn.commit()
        return self._get_row("projects", pid)

    def list_projects(self, status: str = "") -> list[dict[str, Any]]:
        if status:
            rows = self.conn.execute("SELECT * FROM projects WHERE status=? ORDER BY created_at", (status,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM projects ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def get_project(self, name_or_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE id=? OR name=?", (name_or_id, name_or_id)
        ).fetchone()
        return dict(row) if row else None

    def update_project(self, name_or_id: str, field: str, value: str) -> dict[str, Any] | None:
        proj = self.get_project(name_or_id)
        if not proj:
            return None
        allowed = {"name", "description", "workspace", "status"}
        if field not in allowed:
            return None
        self.conn.execute(
            f"UPDATE projects SET {field}=?, updated_at=? WHERE id=?",
            (value, _now(), proj["id"]),
        )
        self.conn.commit()
        return self._get_row("projects", proj["id"])

    def delete_project(self, name_or_id: str) -> dict[str, int] | None:
        """Delete a project and all related data. Returns counts of deleted rows, or None if not found."""
        proj = self.get_project(name_or_id)
        if not proj:
            return None
        pid = proj["id"]
        counts: dict[str, int] = {}

        # Count before delete
        counts["contents"] = self.conn.execute(
            "SELECT COUNT(*) FROM contents WHERE project_id=?", (pid,)
        ).fetchone()[0]
        counts["plans"] = self.conn.execute(
            "SELECT COUNT(*) FROM plans WHERE project_id=?", (pid,)
        ).fetchone()[0]
        counts["platforms"] = self.conn.execute(
            "SELECT COUNT(*) FROM platforms WHERE project_id=?", (pid,)
        ).fetchone()[0]
        counts["goals"] = self.conn.execute(
            "SELECT COUNT(*) FROM goals WHERE project_id=?", (pid,)
        ).fetchone()[0]

        # Delete contents first (no ON DELETE CASCADE on contents FKs)
        self.conn.execute("DELETE FROM contents WHERE project_id=?", (pid,))
        # Delete project — cascades to goals, platforms, plans, plan_platforms
        self.conn.execute("DELETE FROM projects WHERE id=?", (pid,))
        self.conn.commit()
        return counts

    # ── Goals ─────────────────────────────────────────────────────

    def add_goal(self, project_name: str, title: str) -> dict[str, Any]:
        proj = self.get_project(project_name)
        if not proj:
            raise ValueError(f"Project not found: {project_name}")
        now = _now()
        gid = _make_id("goal", f"{proj['id']}-{title}")
        self.conn.execute(
            "INSERT INTO goals (id, project_id, title, created_at, updated_at) VALUES (?,?,?,?,?)",
            (gid, proj["id"], title, now, now),
        )
        self.conn.commit()
        return self._get_row("goals", gid)

    def list_goals(self, project_name: str) -> list[dict[str, Any]]:
        proj = self.get_project(project_name)
        if not proj:
            return []
        rows = self.conn.execute(
            "SELECT * FROM goals WHERE project_id=? ORDER BY created_at", (proj["id"],)
        ).fetchall()
        return [dict(r) for r in rows]

    def update_goal(self, goal_id: str, field: str, value: str) -> dict[str, Any] | None:
        allowed = {"title", "status"}
        if field not in allowed:
            return None
        self.conn.execute(
            f"UPDATE goals SET {field}=?, updated_at=? WHERE id=?",
            (value, _now(), goal_id),
        )
        self.conn.commit()
        return self._get_row("goals", goal_id)

    # ── Platforms ─────────────────────────────────────────────────

    def add_platform(
        self, project_name: str, platform_name: str, directions: str = "", pace: str = ""
    ) -> dict[str, Any]:
        proj = self.get_project(project_name)
        if not proj:
            raise ValueError(f"Project not found: {project_name}")
        now = _now()
        plid = _make_id("plat", f"{proj['id']}-{platform_name}")
        self.conn.execute(
            "INSERT INTO platforms (id, project_id, name, directions, pace, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (plid, proj["id"], platform_name, directions, pace, now, now),
        )
        self.conn.commit()
        return self._get_row("platforms", plid)

    def list_platforms(self, project_name: str) -> list[dict[str, Any]]:
        proj = self.get_project(project_name)
        if not proj:
            return []
        rows = self.conn.execute(
            "SELECT * FROM platforms WHERE project_id=? ORDER BY name", (proj["id"],)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_platform(self, project_name: str, platform_name: str) -> dict[str, Any] | None:
        proj = self.get_project(project_name)
        if not proj:
            return None
        row = self.conn.execute(
            "SELECT * FROM platforms WHERE project_id=? AND name=?",
            (proj["id"], platform_name),
        ).fetchone()
        return dict(row) if row else None

    def update_platform(
        self, project_name: str, platform_name: str, field: str, value: str
    ) -> dict[str, Any] | None:
        plat = self.get_platform(project_name, platform_name)
        if not plat:
            return None
        allowed = {"directions", "pace", "status", "last_published_at", "publish_url", "bsky_handle", "platform_secret"}
        if field not in allowed:
            return None
        self.conn.execute(
            f"UPDATE platforms SET {field}=?, updated_at=? WHERE id=?",
            (value, _now(), plat["id"]),
        )
        self.conn.commit()
        return self._get_row("platforms", plat["id"])

    def remove_platform(self, project_name: str, platform_name: str) -> bool:
        plat = self.get_platform(project_name, platform_name)
        if not plat:
            return False
        self.conn.execute("DELETE FROM platforms WHERE id=?", (plat["id"],))
        self.conn.commit()
        return True

    # ── Plans ─────────────────────────────────────────────────────

    def create_plan(
        self, project_name: str, plan_name: str, goal_id: str = "", strategy: str = ""
    ) -> dict[str, Any]:
        proj = self.get_project(project_name)
        if not proj:
            raise ValueError(f"Project not found: {project_name}")
        now = _now()
        plid = _make_id("plan", f"{proj['id']}-{plan_name}")
        self.conn.execute(
            "INSERT INTO plans (id, project_id, goal_id, name, strategy, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (plid, proj["id"], goal_id or None, plan_name, strategy, now, now),
        )
        self.conn.commit()
        return self._get_row("plans", plid)

    def list_plans(self, project_name: str, status: str = "") -> list[dict[str, Any]]:
        proj = self.get_project(project_name)
        if not proj:
            return []
        if status:
            rows = self.conn.execute(
                "SELECT * FROM plans WHERE project_id=? AND status=? ORDER BY created_at",
                (proj["id"], status),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM plans WHERE project_id=? ORDER BY created_at", (proj["id"],)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_plan(self, project_name: str, plan_name: str) -> dict[str, Any] | None:
        proj = self.get_project(project_name)
        if not proj:
            return None
        row = self.conn.execute(
            "SELECT * FROM plans WHERE project_id=? AND name=?",
            (proj["id"], plan_name),
        ).fetchone()
        return dict(row) if row else None

    def update_plan(self, project_name: str, plan_name: str, field: str, value: str) -> dict[str, Any] | None:
        plan = self.get_plan(project_name, plan_name)
        if not plan:
            return None
        allowed = {"name", "strategy", "status", "goal_id"}
        if field not in allowed:
            return None
        self.conn.execute(
            f"UPDATE plans SET {field}=?, updated_at=? WHERE id=?",
            (value, _now(), plan["id"]),
        )
        self.conn.commit()
        return self._get_row("plans", plan["id"])

    def assign_plan_platform(
        self, project_name: str, plan_name: str, platform_name: str, direction: str = "", target: int = 0
    ) -> dict[str, Any] | None:
        plan = self.get_plan(project_name, plan_name)
        plat = self.get_platform(project_name, platform_name)
        if not plan or not plat:
            return None
        now = _now()
        self.conn.execute(
            "INSERT OR REPLACE INTO plan_platforms (plan_id, platform_id, direction, target_count, created_at) "
            "VALUES (?,?,?,?,?)",
            (plan["id"], plat["id"], direction, target, now),
        )
        self.conn.commit()
        return {"plan_id": plan["id"], "platform_id": plat["id"], "direction": direction, "target_count": target}

    def list_plan_platforms(self, project_name: str, plan_name: str) -> list[dict[str, Any]]:
        plan = self.get_plan(project_name, plan_name)
        if not plan:
            return []
        rows = self.conn.execute(
            "SELECT pp.*, p.name as platform_name FROM plan_platforms pp "
            "JOIN platforms p ON pp.platform_id = p.id "
            "WHERE pp.plan_id=?",
            (plan["id"],),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Contents ──────────────────────────────────────────────────

    def register_content(
        self,
        source_path: str = "",
        title: str = "",
        project_name: str = "",
        platform_name: str = "",
        plan_name: str = "",
        direction: str = "",
        description: str = "",
        content_type: str = "article",
        tags: str = "",
        status: str = "draft",
    ) -> dict[str, Any]:
        now = _now()

        # Resolve foreign keys — use None (not "") to satisfy FK constraints
        project_id = None
        platform_id = None
        plan_id = None
        workspace = ""

        if project_name:
            proj = self.get_project(project_name)
            if proj:
                project_id = proj["id"]

        if project_name and platform_name:
            plat = self.get_platform(project_name, platform_name)
            if plat:
                platform_id = plat["id"]

        if project_name and plan_name:
            plan = self.get_plan(project_name, plan_name)
            if plan:
                plan_id = plan["id"]

        if source_path:
            workspace = str(self._detect_workspace(Path(source_path)) or "")

        cid = _make_id("cont", f"{source_path or title}-{now}")

        self.conn.execute(
            "INSERT INTO contents "
            "(id, project_id, platform_id, plan_id, direction, title, description, "
            "source_path, workspace, content_type, tags, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                cid, project_id, platform_id, plan_id, direction, title, description,
                source_path, workspace, content_type, tags, status, now, now,
            ),
        )
        self.conn.commit()
        return self._get_row("contents", cid)

    def list_contents(
        self,
        project_name: str = "",
        platform_name: str = "",
        status: str = "",
        direction: str = "",
        no_plan: bool = False,
    ) -> list[dict[str, Any]]:
        query = "SELECT c.*, p.name as project_name, pl.name as platform_name FROM contents c "
        query += "LEFT JOIN projects p ON c.project_id = p.id "
        query += "LEFT JOIN platforms pl ON c.platform_id = pl.id "
        conditions: list[str] = []
        params: list[str] = []

        if project_name:
            proj = self.get_project(project_name)
            if proj:
                conditions.append("c.project_id=?")
                params.append(proj["id"])

        if platform_name and project_name:
            plat = self.get_platform(project_name, platform_name)
            if plat:
                conditions.append("c.platform_id=?")
                params.append(plat["id"])

        if status:
            conditions.append("c.status=?")
            params.append(status)

        if direction:
            conditions.append("c.direction=?")
            params.append(direction)

        if no_plan:
            conditions.append("(c.plan_id IS NULL OR c.plan_id = '')")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY c.created_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_content(self, content_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM contents WHERE id=?", (content_id,)).fetchone()
        return dict(row) if row else None

    def update_content(self, content_id: str, field: str, value: str) -> dict[str, Any] | None:
        content = self.get_content(content_id)
        if not content:
            return None
        allowed = {
            "title", "description", "direction", "tags", "status",
            "published_url", "published_at", "content_type", "source_path",
            "plan_id",
        }
        if field not in allowed:
            return None
        self.conn.execute(
            f"UPDATE contents SET {field}=?, updated_at=? WHERE id=?",
            (value, _now(), content_id),
        )
        self.conn.commit()
        return self._get_row("contents", content_id)

    def assign_plan_to_contents(
        self,
        project_name: str,
        plan_name: str,
        platform_names: list[str] | None = None,
        status: str = "",
    ) -> int:
        """Batch-assign plan_id to all matching content records. Returns count of affected rows."""
        proj = self.get_project(project_name)
        if not proj:
            raise ValueError(f"Project not found: {project_name}")
        plan = self.get_plan(project_name, plan_name)
        if not plan:
            raise ValueError(f"Plan not found: {plan_name}")

        conditions: list[str] = ["project_id=?"]
        params: list[Any] = [proj["id"]]

        if platform_names:
            plat_ids = [
                plat["id"]
                for pname in platform_names
                if (plat := self.get_platform(project_name, pname)) is not None
            ]
            if not plat_ids:
                return 0
            placeholders = ",".join("?" * len(plat_ids))
            conditions.append(f"platform_id IN ({placeholders})")
            params.extend(plat_ids)

        if status:
            conditions.append("status=?")
            params.append(status)

        where = " AND ".join(conditions)
        cur = self.conn.execute(
            f"UPDATE contents SET plan_id=?, updated_at=? WHERE {where}",
            [plan["id"], _now(), *params],
        )
        self.conn.commit()
        return cur.rowcount

    def remove_content(self, content_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM contents WHERE id=?", (content_id,))
        self.conn.commit()
        return cur.rowcount > 0

    # ── Status / Dashboard ────────────────────────────────────────

    def project_status(self, project_name: str) -> dict[str, Any] | None:
        proj = self.get_project(project_name)
        if not proj:
            return None

        goals = self.list_goals(project_name)
        plans = self.list_plans(project_name)
        platforms = self.list_platforms(project_name)

        # Content stats per platform
        platform_stats = []
        for plat in platforms:
            total = self.conn.execute(
                "SELECT COUNT(*) FROM contents WHERE platform_id=?", (plat["id"],)
            ).fetchone()[0]
            published = self.conn.execute(
                "SELECT COUNT(*) FROM contents WHERE platform_id=? AND status='published'",
                (plat["id"],),
            ).fetchone()[0]
            draft = self.conn.execute(
                "SELECT COUNT(*) FROM contents WHERE platform_id=? AND status='draft'",
                (plat["id"],),
            ).fetchone()[0]
            planned = self.conn.execute(
                "SELECT COUNT(*) FROM contents WHERE platform_id=? AND status='planned'",
                (plat["id"],),
            ).fetchone()[0]
            platform_stats.append({
                "name": plat["name"],
                "directions": plat["directions"],
                "pace": plat["pace"],
                "total": total,
                "published": published,
                "draft": draft,
                "planned": planned,
                "last_published_at": plat["last_published_at"],
            })

        # Plan progress
        plan_stats = []
        for plan in plans:
            pp_rows = self.conn.execute(
                "SELECT pp.*, pl.name as platform_name FROM plan_platforms pp "
                "JOIN platforms pl ON pp.platform_id = pl.id "
                "WHERE pp.plan_id=?",
                (plan["id"],),
            ).fetchall()
            assignments = []
            for pp in pp_rows:
                done = self.conn.execute(
                    "SELECT COUNT(*) FROM contents WHERE plan_id=? AND platform_id=? AND status='published'",
                    (plan["id"], pp["platform_id"]),
                ).fetchone()[0]
                assignments.append({
                    "platform": pp["platform_name"],
                    "direction": pp["direction"],
                    "target": pp["target_count"],
                    "done": done,
                })
            plan_stats.append({
                "name": plan["name"],
                "status": plan["status"],
                "strategy": plan["strategy"],
                "assignments": assignments,
            })

        return {
            "project": proj,
            "goals": goals,
            "plans": plan_stats,
            "platforms": platform_stats,
        }

    # ── Brand ─────────────────────────────────────────────────────

    BRAND_FIELDS = {"name", "positioning", "voice", "core_values", "topics"}

    def get_brand(self) -> dict[str, Any]:
        """Return the brand singleton row, or empty defaults if not yet set."""
        row = self.conn.execute("SELECT * FROM brand WHERE id='singleton'").fetchone()
        if row:
            return dict(row)
        return {"id": "singleton", "name": "", "positioning": "", "voice": "", "core_values": "", "topics": "", "updated_at": ""}

    def set_brand(self, field: str, value: str) -> dict[str, Any] | None:
        """Set a brand field (upserts the singleton row)."""
        if field not in self.BRAND_FIELDS:
            return None
        now = _now()
        existing = self.conn.execute("SELECT id FROM brand WHERE id='singleton'").fetchone()
        if existing:
            self.conn.execute(
                f"UPDATE brand SET {field}=?, updated_at=? WHERE id='singleton'",
                (value, now),
            )
        else:
            # Insert singleton with defaults, then set the field
            self.conn.execute(
                "INSERT INTO brand (id, name, positioning, voice, core_values, topics, updated_at) "
                "VALUES ('singleton','','','','','',?)",
                (now,),
            )
            self.conn.execute(
                f"UPDATE brand SET {field}=?, updated_at=? WHERE id='singleton'",
                (value, now),
            )
        self.conn.commit()
        return self.get_brand()

    # ── Styles ──────────────────────────────────────────────────

    STYLE_FIELDS = {"desc", "formula", "tone", "format"}

    STYLE_ALIASES: dict[str, str] = {
        "x": "twitter",
        "wechat": "公众号",
        "bilibili": "B站",
    }

    def _resolve_platform(self, platform: str) -> str:
        return self.STYLE_ALIASES.get(platform.lower(), platform)

    def add_style(
        self,
        platform: str,
        desc: str = "",
        formula: str = "",
        tone: str = "",
        fmt: str = "",
    ) -> dict[str, Any]:
        """Add a writing style for a platform. Raises ValueError if already exists."""
        platform = self._resolve_platform(platform)
        now = _now()
        try:
            self.conn.execute(
                "INSERT INTO styles (platform, desc, formula, tone, format, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (platform, desc, formula, tone, fmt, now, now),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Style already exists for platform '{platform}'. Use 'fgeo style set' to update.")
        row = self.conn.execute("SELECT * FROM styles WHERE platform=?", (platform,)).fetchone()
        return dict(row)

    def get_style(self, platform: str) -> dict[str, Any] | None:
        platform = self._resolve_platform(platform)
        row = self.conn.execute("SELECT * FROM styles WHERE platform=?", (platform,)).fetchone()
        return dict(row) if row else None

    def list_styles(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM styles ORDER BY platform").fetchall()
        return [dict(r) for r in rows]

    def update_style(self, platform: str, field: str, value: str) -> dict[str, Any] | None:
        platform = self._resolve_platform(platform)
        if field not in self.STYLE_FIELDS:
            return None
        style = self.get_style(platform)
        if not style:
            return None
        self.conn.execute(
            f"UPDATE styles SET {field}=?, updated_at=? WHERE platform=?",
            (value, _now(), platform),
        )
        self.conn.commit()
        return self.get_style(platform)

    # ── Publish Tasks ─────────────────────────────────────────────

    def create_publish_task(
        self,
        task_id: str,
        content_id: str,
        platform_id: str = "",
        repo_url: str = "",
        branch: str = "",
        task_dir: str = "",
        pr_url: str = "",
        status: str = "pr_open",
    ) -> dict[str, Any]:
        now = _now()
        self.conn.execute(
            "INSERT INTO publish_tasks (id, content_id, platform_id, repo_url, branch, task_dir, pr_url, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (task_id, content_id, platform_id or None, repo_url, branch, task_dir, pr_url, status, now, now),
        )
        self.conn.commit()
        return self.get_publish_task(task_id) or {}

    def get_publish_task(self, task_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM publish_tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def list_publish_tasks(self, status: str = "", content_id: str = "") -> list[dict[str, Any]]:
        q = "SELECT pt.*, c.title as content_title FROM publish_tasks pt LEFT JOIN contents c ON pt.content_id=c.id"
        params: list[str] = []
        wheres: list[str] = []
        if status:
            wheres.append("pt.status=?")
            params.append(status)
        if content_id:
            wheres.append("pt.content_id=?")
            params.append(content_id)
        if wheres:
            q += " WHERE " + " AND ".join(wheres)
        q += " ORDER BY pt.created_at DESC"
        return [dict(r) for r in self.conn.execute(q, params).fetchall()]

    def update_publish_task(self, task_id: str, field: str, value: str) -> dict[str, Any] | None:
        allowed = {"status", "pr_url", "branch", "repo_url", "task_dir"}
        if field not in allowed:
            return None
        task = self.get_publish_task(task_id)
        if not task:
            return None
        self.conn.execute(
            f"UPDATE publish_tasks SET {field}=?, updated_at=? WHERE id=?",
            (value, _now(), task_id),
        )
        self.conn.commit()
        return self.get_publish_task(task_id)

    # ── Helpers ───────────────────────────────────────────────────

    def _get_row(self, table: str, row_id: str) -> dict[str, Any]:
        row = self.conn.execute(f"SELECT * FROM {table} WHERE id=?", (row_id,)).fetchone()
        return dict(row) if row else {}

    @staticmethod
    def _detect_workspace(path: Path) -> Path | None:
        current = path.resolve().parent
        for _ in range(20):
            if (current / ".fcontext").is_dir() or (current / ".git").is_dir():
                return current
            parent = current.parent
            if parent == current:
                break
            current = parent
        return None


def get_db(db_path: Path | None = None) -> Database:
    """Get a Database instance, initializing schema if needed."""
    db = Database(db_path)
    db.init_schema()
    return db
