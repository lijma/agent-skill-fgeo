"""fgeo database — SQLite data layer for Project/Goal/Platform/Plan/Content."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fgeo.constants import FGEO_HOME

FGEO_DB_FILE = FGEO_HOME / "fgeo.db"

SCHEMA_VERSION = "0.2.0"

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

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
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
        """Create tables if they don't exist."""
        self.conn.executescript(SCHEMA_SQL)
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
        allowed = {"directions", "pace", "status", "last_published_at"}
        if field not in allowed:
            return None
        self.conn.execute(
            f"UPDATE platforms SET {field}=?, updated_at=? WHERE id=?",
            (value, _now(), plat["id"]),
        )
        self.conn.commit()
        return self._get_row("platforms", plat["id"])

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
        }
        if field not in allowed:
            return None
        self.conn.execute(
            f"UPDATE contents SET {field}=?, updated_at=? WHERE id=?",
            (value, _now(), content_id),
        )
        self.conn.commit()
        return self._get_row("contents", content_id)

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
