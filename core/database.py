"""MySQL / MariaDB database layer using PyMySQL.

All database tables, indexes, and queries use PyMySQL DictCursor.
Provides automatic database creation and table initialization.
"""

import pymysql
import pymysql.cursors
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from config.settings import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
)

logger = logging.getLogger(__name__)


def get_server_connection():
    """Connect to MySQL server without selecting a database (for DB creation)."""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        charset="utf8mb4",
    )


def get_connection():
    """Connect to the target MySQL database."""
    # Ensure database exists first
    _ensure_database_exists()
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        charset="utf8mb4",
    )


def _ensure_database_exists():
    """Create the MySQL database if it doesn't exist yet."""
    try:
        conn = get_server_connection()
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn.close()
    except Exception as e:
        logger.warning(f"[MySQL] Database check/create warning: {e}")


def _prep_sql(sql: str) -> str:
    """Translate standard SQL placeholders ? to MySQL %s."""
    return sql.replace("?", "%s")


def init_db():
    """Create all MySQL tables, columns, and indexes if they do not exist."""
    conn = get_connection()
    with conn.cursor() as cur:
        # Jobs table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id VARCHAR(255) PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                company VARCHAR(255) NOT NULL,
                location VARCHAR(255) DEFAULT 'Remote',
                description LONGTEXT,
                url TEXT,
                source VARCHAR(255) DEFAULT '',
                posted_date VARCHAR(255) DEFAULT '',
                discovered_at VARCHAR(255) NOT NULL,
                tech_stack TEXT,
                experience_level VARCHAR(255) DEFAULT '',
                relevance_score INT DEFAULT 0,
                status VARCHAR(255) DEFAULT 'new',
                company_domain VARCHAR(255) DEFAULT '',
                salary VARCHAR(255) DEFAULT '',
                job_type VARCHAR(255) DEFAULT '',
                bd_friendly VARCHAR(255) DEFAULT 'unknown',
                location_note TEXT,
                mark_for_email INT DEFAULT 0,
                scored_profile_id INT DEFAULT NULL,
                last_seen VARCHAR(255) DEFAULT ''
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Migration: Add bd_friendly column if upgrading from older schema without it
        try:
            cur.execute("ALTER TABLE jobs ADD COLUMN bd_friendly VARCHAR(255) DEFAULT 'unknown';")
        except Exception:
            pass

        # Companies table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                domain VARCHAR(255) DEFAULT '',
                careers_url TEXT,
                ats_platform VARCHAR(255) DEFAULT 'unknown',
                ats_slug VARCHAR(255) DEFAULT '',
                crawl_status VARCHAR(255) DEFAULT 'active',
                last_crawled_at VARCHAR(255) DEFAULT '',
                created_at VARCHAR(255) NOT NULL,
                founded_year INT DEFAULT NULL,
                employee_count VARCHAR(255) DEFAULT '',
                tags TEXT,
                bd_friendly VARCHAR(255) DEFAULT 'maybe',
                notes TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Migration: Add bd_friendly column if upgrading from older schema without it
        try:
            cur.execute("ALTER TABLE companies ADD COLUMN bd_friendly VARCHAR(255) DEFAULT 'maybe';")
        except Exception:
            pass

        # Profiles table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                config_json LONGTEXT NOT NULL,
                created_at VARCHAR(255) NOT NULL,
                updated_at VARCHAR(255) NOT NULL,
                source VARCHAR(255) DEFAULT 'custom'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # App Settings table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                `key` VARCHAR(255) PRIMARY KEY,
                `value` TEXT,
                updated_at VARCHAR(255)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Outreach table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS outreach (
                id VARCHAR(255) PRIMARY KEY,
                job_id VARCHAR(255) NOT NULL,
                job_title VARCHAR(255) NOT NULL,
                company VARCHAR(255) NOT NULL,
                company_domain VARCHAR(255) DEFAULT '',
                contact_name VARCHAR(255) DEFAULT '',
                contact_position VARCHAR(255) DEFAULT '',
                contact_linkedin TEXT,
                dm_short TEXT,
                dm_long LONGTEXT,
                status VARCHAR(255) DEFAULT 'pending',
                messaged_at VARCHAR(255) DEFAULT '',
                replied_at VARCHAR(255) DEFAULT '',
                followed_up_at VARCHAR(255) DEFAULT '',
                created_at VARCHAR(255) NOT NULL,
                notes LONGTEXT,
                emailed_at VARCHAR(255) DEFAULT '',
                profile_id INT DEFAULT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Queries table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INT AUTO_INCREMENT PRIMARY KEY,
                query VARCHAR(255) NOT NULL,
                country VARCHAR(50) DEFAULT 'BD',
                date_posted VARCHAR(50) DEFAULT '3days',
                remote_jobs_only INT DEFAULT 1,
                enabled INT DEFAULT 1,
                created_at VARCHAR(255) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Email Logs table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS email_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sent_at VARCHAR(255) NOT NULL,
                recipient VARCHAR(255) NOT NULL,
                subject VARCHAR(255) NOT NULL,
                items_count INT DEFAULT 0,
                job_ids LONGTEXT,
                status VARCHAR(50) DEFAULT 'sent',
                error TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # API Logs table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS api_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp VARCHAR(255) NOT NULL,
                api_name VARCHAR(255) NOT NULL,
                success INT DEFAULT 1,
                notes TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Outreach Batches table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS outreach_batches (
                `key` VARCHAR(255) PRIMARY KEY,
                `value` TEXT,
                updated_at VARCHAR(255)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

    conn.close()


# ── Jobs CRUD ─────────────────────────────────────────────────────────

def insert_job(job_dict: dict) -> str:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("SELECT id FROM jobs WHERE id = ?"), (job_dict["id"],))
            row = cur.fetchone()

            if row:
                cur.execute(_prep_sql("""
                    UPDATE jobs SET
                        title = ?, company = ?, location = ?, description = ?,
                        url = ?, source = ?, posted_date = ?, tech_stack = ?,
                        experience_level = ?, relevance_score = ?,
                        company_domain = ?, salary = ?, job_type = ?,
                        bd_friendly = ?, location_note = ?,
                        scored_profile_id = ?, last_seen = ?
                    WHERE id = ?
                """), (
                    job_dict.get("title", ""), job_dict.get("company", ""),
                    job_dict.get("location", ""), job_dict.get("description", ""),
                    job_dict.get("url", ""), job_dict.get("source", ""),
                    job_dict.get("posted_date", ""), job_dict.get("tech_stack", ""),
                    job_dict.get("experience_level", ""), job_dict.get("relevance_score", 0),
                    job_dict.get("company_domain", ""), job_dict.get("salary", ""),
                    job_dict.get("job_type", ""), job_dict.get("bd_friendly", "unknown"),
                    job_dict.get("location_note", ""), job_dict.get("scored_profile_id"),
                    job_dict.get("discovered_at", ""), job_dict["id"],
                ))
                return "updated"
            else:
                cur.execute(_prep_sql("""
                    INSERT INTO jobs (
                        id, title, company, location, description, url, source,
                        posted_date, discovered_at, tech_stack, experience_level,
                        relevance_score, status, company_domain, salary, job_type,
                        bd_friendly, location_note, scored_profile_id, last_seen
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """), (
                    job_dict["id"], job_dict.get("title", ""), job_dict.get("company", ""),
                    job_dict.get("location", "Remote"), job_dict.get("description", ""),
                    job_dict.get("url", ""), job_dict.get("source", ""),
                    job_dict.get("posted_date", ""), job_dict.get("discovered_at", ""),
                    job_dict.get("tech_stack", ""), job_dict.get("experience_level", ""),
                    job_dict.get("relevance_score", 0), job_dict.get("status", "new"),
                    job_dict.get("company_domain", ""), job_dict.get("salary", ""),
                    job_dict.get("job_type", ""), job_dict.get("bd_friendly", "unknown"),
                    job_dict.get("location_note", ""), job_dict.get("scored_profile_id"),
                    job_dict.get("discovered_at", ""),
                ))
                return "new"
    finally:
        conn.close()


def cleanup_old_jobs(days: int = 14) -> int:
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("SELECT COUNT(*) AS count FROM jobs WHERE last_seen != '' AND last_seen < ?"), (cutoff,))
            count = cur.fetchone()["count"]
            cur.execute(_prep_sql("DELETE FROM jobs WHERE last_seen != '' AND last_seen < ?"), (cutoff,))
            return count
    finally:
        conn.close()


def toggle_mark_for_email(job_id: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("SELECT mark_for_email FROM jobs WHERE id = ?"), (job_id,))
            row = cur.fetchone()
            if not row:
                return False
            new_val = 0 if row["mark_for_email"] else 1
            cur.execute(_prep_sql("UPDATE jobs SET mark_for_email = ? WHERE id = ?"), (new_val, job_id))
            return bool(new_val)
    finally:
        conn.close()


def get_marked_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("SELECT * FROM jobs WHERE mark_for_email = 1 ORDER BY relevance_score DESC LIMIT %s"), (limit,))
            return list(cur.fetchall())
    finally:
        conn.close()


def get_jobs(
    min_score: int = 0,
    status: Optional[str] = None,
    source: Optional[str] = None,
    bd_friendly: Optional[str] = None,
    search: Optional[str] = None,
    location: Optional[str] = None,
    tech: Optional[str] = None,
    company_domain: Optional[str] = None,
    seen_after: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        query = "SELECT * FROM jobs WHERE relevance_score >= %s"
        params: list = [min_score]

        if status:
            query += " AND status = %s"
            params.append(status)

        if source:
            query += " AND source = %s"
            params.append(source)

        if location:
            query += " AND location LIKE %s"
            params.append(f"%{location}%")

        if tech:
            query += " AND tech_stack LIKE %s"
            params.append(f"%{tech}%")

        if company_domain:
            query += " AND company_domain = %s"
            params.append(company_domain)

        if bd_friendly and bd_friendly != "all":
            if bd_friendly == "yes":
                query += " AND bd_friendly = 'yes'"
            elif bd_friendly == "maybe":
                query += " AND bd_friendly IN ('yes', 'maybe')"
            elif bd_friendly == "no":
                query += " AND bd_friendly = 'no'"

        if search:
            query += " AND (title LIKE %s OR company LIKE %s OR tech_stack LIKE %s)"
            s_param = f"%{search}%"
            params.extend([s_param, s_param, s_param])

        if seen_after:
            query += " AND (last_seen >= %s OR (last_seen = '' AND discovered_at >= %s))"
            params.extend([seen_after, seen_after])

        query += " ORDER BY (CASE WHEN status = 'new' THEN 0 ELSE 1 END), relevance_score DESC, discovered_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with conn.cursor() as cur:
            cur.execute(query, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("SELECT * FROM jobs WHERE id = ?"), (job_id,))
            return cur.fetchone()
    finally:
        conn.close()


def update_job_status(job_id: str, status: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("UPDATE jobs SET status = ? WHERE id = ?"), (status, job_id))
    finally:
        conn.close()


def get_stats() -> Dict[str, Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM jobs")
            total = cur.fetchone()["total"]

            cur.execute("SELECT AVG(relevance_score) AS avg_score FROM jobs")
            avg_score = cur.fetchone()["avg_score"] or 0

            cur.execute("SELECT COUNT(*) AS c FROM jobs WHERE bd_friendly = 'yes'")
            by_india_yes = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) AS c FROM jobs WHERE bd_friendly = 'maybe'")
            by_india_maybe = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) AS c FROM jobs WHERE bd_friendly = 'no'")
            by_india_no = cur.fetchone()["c"]

            cur.execute("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status")
            by_status = {row["status"]: row["count"] for row in cur.fetchall()}

            cur.execute("SELECT source, COUNT(*) AS count FROM jobs GROUP BY source ORDER BY count DESC")
            by_source = {row["source"]: row["count"] for row in cur.fetchall()}

            cur.execute("SELECT COUNT(*) AS marked FROM jobs WHERE mark_for_email = 1")
            marked = cur.fetchone()["marked"]

            # Outreach breakdown for analytics chart
            cur.execute("SELECT status, COUNT(*) AS count FROM outreach GROUP BY status")
            outreach_status = {row["status"]: row["count"] for row in cur.fetchall()}

            # Top tech stack frequency breakdown
            cur.execute("SELECT tech_stack FROM jobs WHERE tech_stack IS NOT NULL AND tech_stack != ''")
            tech_counts = {}
            for row in cur.fetchall():
                tags = [t.strip().lower() for t in row["tech_stack"].split(",") if t.strip()]
                for tag in tags:
                    tech_counts[tag] = tech_counts.get(tag, 0) + 1
            sorted_tech = dict(sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:10])

            return {
                "total": total,
                "avg_score": round(avg_score, 1),
                "by_india": {"yes": by_india_yes, "maybe": by_india_maybe, "no": by_india_no},
                "by_status": by_status,
                "by_source": by_source,
                "marked_for_email": marked,
                "outreach_status": outreach_status,
                "top_tech": sorted_tech,
            }
    finally:
        conn.close()


def get_sources() -> List[str]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT source FROM jobs ORDER BY source")
            return [row["source"] for row in cur.fetchall() if row["source"]]
    finally:
        conn.close()


# ── Companies CRUD ───────────────────────────────────────────────────

def upsert_company(company_dict: dict) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("""
                INSERT INTO companies (
                    id, name, domain, careers_url, ats_platform, ats_slug,
                    crawl_status, created_at, founded_year, employee_count,
                    tags, bd_friendly, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                    name=VALUES(name), domain=VALUES(domain), careers_url=VALUES(careers_url),
                    ats_platform=VALUES(ats_platform), ats_slug=VALUES(ats_slug),
                    crawl_status=VALUES(crawl_status), founded_year=VALUES(founded_year),
                    employee_count=VALUES(employee_count), tags=VALUES(tags),
                    bd_friendly=VALUES(bd_friendly), notes=VALUES(notes)
            """), (
                company_dict["id"], company_dict["name"],
                company_dict.get("domain", ""), company_dict.get("careers_url", ""),
                company_dict.get("ats_platform", "unknown"), company_dict.get("ats_slug", ""),
                company_dict.get("crawl_status", "active"), company_dict.get("created_at", datetime.utcnow().isoformat()),
                company_dict.get("founded_year"), company_dict.get("employee_count", ""),
                company_dict.get("tags", ""), company_dict.get("bd_friendly", "maybe"),
                company_dict.get("notes", ""),
            ))
            return True
    finally:
        conn.close()


def get_companies(
    ats_platform: Optional[str] = None,
    crawl_status: Optional[str] = None,
    bd_friendly: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        query = "SELECT * FROM companies WHERE 1=1"
        params: list = []

        if ats_platform:
            query += " AND ats_platform = %s"
            params.append(ats_platform)

        if crawl_status:
            query += " AND crawl_status = %s"
            params.append(crawl_status)

        if bd_friendly and bd_friendly != "all":
            query += " AND bd_friendly = %s"
            params.append(bd_friendly)

        if search:
            query += " AND (name LIKE %s OR domain LIKE %s OR tags LIKE %s)"
            s_param = f"%{search}%"
            params.extend([s_param, s_param, s_param])

        query += " ORDER BY name ASC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with conn.cursor() as cur:
            cur.execute(query, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def get_company_by_id(company_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("SELECT * FROM companies WHERE id = ?"), (company_id,))
            return cur.fetchone()
    finally:
        conn.close()


def update_company_crawl_status(company_id: str, status: str, last_crawled: str = ""):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if last_crawled:
                cur.execute(_prep_sql("UPDATE companies SET crawl_status = ?, last_crawled_at = ? WHERE id = ?"), (status, last_crawled, company_id))
            else:
                cur.execute(_prep_sql("UPDATE companies SET crawl_status = ? WHERE id = ?"), (status, company_id))
    finally:
        conn.close()


# ── Outreach CRUD ─────────────────────────────────────────────────────

def insert_outreach(item: dict) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("""
                INSERT INTO outreach (
                    id, job_id, job_title, company, company_domain, contact_name,
                    contact_position, contact_linkedin, dm_short, dm_long, status,
                    created_at, notes, emailed_at, profile_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE status=VALUES(status)
            """), (
                item["id"], item["job_id"], item["job_title"], item["company"],
                item.get("company_domain", ""), item.get("contact_name", ""),
                item.get("contact_position", ""), item.get("contact_linkedin", ""),
                item.get("dm_short", ""), item.get("dm_long", ""),
                item.get("status", "pending"), item["created_at"],
                item.get("notes", ""), item.get("emailed_at", ""),
                item.get("profile_id"),
            ))
            return True
    finally:
        conn.close()


def get_outreach(
    status: Optional[str] = None,
    search: Optional[str] = None,
    new_only: bool = False,
    batch: Optional[str] = None,
    profile_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        query = """
            SELECT o.*, j.relevance_score, j.url AS job_url, j.bd_friendly, j.location, j.tech_stack, j.posted_date
            FROM outreach o
            LEFT JOIN jobs j ON o.job_id = j.id
            WHERE 1=1
        """
        params: list = []

        if status:
            query += " AND o.status = %s"
            params.append(status)

        if profile_id is not None:
            query += " AND o.profile_id = %s"
            params.append(profile_id)

        is_new = new_only or (batch == "new")
        is_old = (batch == "old")

        if is_new or is_old:
            with conn.cursor() as cur:
                cur.execute(_prep_sql("SELECT value FROM outreach_batches WHERE `key` = 'last_batch_at'"))
                last_batch = cur.fetchone()
                if last_batch and last_batch["value"]:
                    if is_new:
                        query += " AND o.created_at >= %s"
                    else:
                        query += " AND o.created_at < %s"
                    params.append(last_batch["value"])

        if search:
            query += " AND (o.company LIKE %s OR o.job_title LIKE %s)"
            s_param = f"%{search}%"
            params.extend([s_param, s_param])

        query += " ORDER BY (CASE WHEN o.status = 'new' THEN 0 ELSE 1 END), o.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with conn.cursor() as cur:
            cur.execute(query, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def delete_outreach_bulk(ids: List[str]) -> int:
    if not ids:
        return 0
    conn = get_connection()
    try:
        placeholders = ",".join(["%s"] * len(ids))
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM outreach WHERE id IN ({placeholders})", ids)
            return cur.rowcount
    finally:
        conn.close()


def delete_all_outreach() -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM outreach")
            return cur.rowcount
    finally:
        conn.close()


def set_last_outreach_batch_at(ts: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("""
                INSERT INTO outreach_batches (`key`, `value`, updated_at) VALUES ('last_batch_at', ?, ?)
                ON DUPLICATE KEY UPDATE `value`=VALUES(`value`), updated_at=VALUES(updated_at)
            """), (ts, ts))
    finally:
        conn.close()


def get_last_outreach_batch_at() -> Optional[str]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("SELECT `value` FROM outreach_batches WHERE `key` = 'last_batch_at'"))
            row = cur.fetchone()
            return row["value"] if row else None
    finally:
        conn.close()


def update_outreach_status(outreach_id: str, status: str, field: str = None):
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        with conn.cursor() as cur:
            if field and field in ["messaged_at", "replied_at", "followed_up_at"]:
                cur.execute(_prep_sql(f"UPDATE outreach SET status = ?, {field} = ? WHERE id = ?"), (status, now, outreach_id))
            else:
                cur.execute(_prep_sql("UPDATE outreach SET status = ? WHERE id = ?"), (status, outreach_id))
    finally:
        conn.close()


def update_outreach_notes(outreach_id: str, notes: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("UPDATE outreach SET notes = ? WHERE id = ?"), (notes, outreach_id))
    finally:
        conn.close()


def outreach_exists_for_job(job_id: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("SELECT id FROM outreach WHERE job_id = ?"), (job_id,))
            return bool(cur.fetchone())
    finally:
        conn.close()


def get_outreach_stats() -> Dict[str, Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status, COUNT(*) AS count FROM outreach GROUP BY status")
            return {row["status"]: row["count"] for row in cur.fetchall()}
    finally:
        conn.close()


def get_unemailed_outreach(limit: int = 15, only_marked: bool = False) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        query = """
            SELECT o.*, j.relevance_score, j.url AS job_url, j.bd_friendly, j.location, j.tech_stack, j.posted_date
            FROM outreach o
            LEFT JOIN jobs j ON o.job_id = j.id
            WHERE o.emailed_at = ''
        """
        if only_marked:
            query += " AND j.mark_for_email = 1"
        query += " ORDER BY j.relevance_score DESC LIMIT %s"

        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            return list(cur.fetchall())
    finally:
        conn.close()


def mark_outreach_emailed(outreach_ids: List[str]):
    if not outreach_ids:
        return
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        placeholders = ",".join(["%s"] * len(outreach_ids))
        with conn.cursor() as cur:
            cur.execute(f"UPDATE outreach SET emailed_at = %s WHERE id IN ({placeholders})", [now] + outreach_ids)
    finally:
        conn.close()


def log_email(recipient: str, subject: str, items_count: int, job_ids: list, status: str = "sent", error: str = ""):
    conn = get_connection()
    try:
        import json
        with conn.cursor() as cur:
            cur.execute(_prep_sql("""
                INSERT INTO email_logs (sent_at, recipient, subject, items_count, job_ids, status, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """), (
                datetime.utcnow().isoformat(), recipient, subject, items_count,
                json.dumps(job_ids), status, error,
            ))
    finally:
        conn.close()


# ── Search Queries CRUD ────────────────────────────────────────────────

def get_search_queries(enabled_only: bool = False) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        query = "SELECT * FROM queries"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY id ASC"

        with conn.cursor() as cur:
            cur.execute(query)
            return list(cur.fetchall())
    finally:
        conn.close()


def add_search_query(query: str, country: str = "BD", date_posted: str = "3days", remote_jobs_only: bool = True) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("""
                INSERT INTO queries (query, country, date_posted, remote_jobs_only, enabled, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
            """), (
                query, country, date_posted,
                1 if remote_jobs_only else 0,
                datetime.utcnow().isoformat(),
            ))
            return cur.lastrowid
    finally:
        conn.close()


def update_search_query(qid: int, query: str = None, country: str = None, date_posted: str = None, remote_jobs_only: bool = None, enabled: bool = None):
    conn = get_connection()
    try:
        updates = []
        params = []
        if query is not None:
            updates.append("query = %s")
            params.append(query)
        if country is not None:
            updates.append("country = %s")
            params.append(country)
        if date_posted is not None:
            updates.append("date_posted = %s")
            params.append(date_posted)
        if remote_jobs_only is not None:
            updates.append("remote_jobs_only = %s")
            params.append(1 if remote_jobs_only else 0)
        if enabled is not None:
            updates.append("enabled = %s")
            params.append(1 if enabled else 0)

        if not updates:
            return

        params.append(qid)
        sql = f"UPDATE queries SET {', '.join(updates)} WHERE id = %s"
        with conn.cursor() as cur:
            cur.execute(sql, params)
    finally:
        conn.close()


def delete_search_query(qid: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("DELETE FROM queries WHERE id = ?"), (qid,))
    finally:
        conn.close()


# ── Logs & Analytics CRUD ─────────────────────────────────────────────

def log_api_call(api_name: str, success: bool = True, notes: str = ""):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("""
                INSERT INTO api_logs (timestamp, api_name, success, notes)
                VALUES (?, ?, ?, ?)
            """), (
                datetime.utcnow().isoformat(), api_name,
                1 if success else 0, notes,
            ))
    finally:
        conn.close()


def get_api_usage(api_name: str) -> Dict[str, Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("""
                SELECT COUNT(*) AS total_calls,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS successful_calls
                FROM api_logs WHERE api_name = ?
            """), (api_name,))
            row = cur.fetchone()
            return {
                "total_calls": row["total_calls"] if row else 0,
                "successful_calls": row["successful_calls"] if row else 0,
            }
    finally:
        conn.close()


def get_email_logs(limit: int = 30) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_prep_sql("SELECT * FROM email_logs ORDER BY sent_at DESC LIMIT %s"), (limit,))
            return list(cur.fetchall())
    finally:
        conn.close()


def get_company_stats() -> Dict[str, Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM companies")
            total = cur.fetchone()["total"]

            cur.execute("SELECT crawl_status, COUNT(*) AS count FROM companies GROUP BY crawl_status")
            by_status = {row["crawl_status"]: row["count"] for row in cur.fetchall()}

            cur.execute("SELECT ats_platform, COUNT(*) AS count FROM companies GROUP BY ats_platform")
            by_platform = {row["ats_platform"]: row["count"] for row in cur.fetchall()}

            return {
                "total": total,
                "by_status": by_status,
                "by_platform": by_platform,
            }
    finally:
        conn.close()
