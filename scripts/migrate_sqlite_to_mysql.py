"""Data Migration Utility: SQLite (jobs.db) -> MySQL

Migrates existing local SQLite rows into your MySQL database.
Usage:
    python scripts/migrate_sqlite_to_mysql.py
"""

import os
import sys
import sqlite3
import pymysql

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
)
from core.database import init_db, get_connection

SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jobs.db")


def migrate():
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"[!] SQLite DB not found at {SQLITE_DB_PATH}. Skipping migration.")
        return

    print("=== Starting SQLite -> MySQL Data Migration ===")
    print(f"Source SQLite: {SQLITE_DB_PATH}")
    print(f"Target MySQL: {MYSQL_USER}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")

    # Ensure MySQL tables are initialized
    init_db()

    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    mysql_conn = get_connection()
    mysql_cur = mysql_conn.cursor()

    # 1. Migrate Jobs
    try:
        sqlite_cur.execute("SELECT * FROM jobs")
        jobs = sqlite_cur.fetchall()
        print(f"-> Migrating {len(jobs)} jobs...")
        migrated_jobs = 0
        for j in jobs:
            row = dict(j)
            mysql_cur.execute("""
                INSERT INTO jobs (
                    id, title, company, location, description, url, source,
                    posted_date, discovered_at, tech_stack, experience_level,
                    relevance_score, status, company_domain, salary, job_type,
                    bd_friendly, location_note, mark_for_email, scored_profile_id, last_seen
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON DUPLICATE KEY UPDATE title=VALUES(title), relevance_score=VALUES(relevance_score)
            """, (
                row.get("id"), row.get("title", ""), row.get("company", ""),
                row.get("location", "Remote"), row.get("description", ""),
                row.get("url", ""), row.get("source", ""), row.get("posted_date", ""),
                row.get("discovered_at", ""), row.get("tech_stack", ""),
                row.get("experience_level", ""), row.get("relevance_score", 0),
                row.get("status", "new"), row.get("company_domain", ""),
                row.get("salary", ""), row.get("job_type", ""),
                row.get("bd_friendly", row.get("india_friendly", "unknown")), row.get("location_note", ""),
                row.get("mark_for_email", 0), row.get("scored_profile_id"),
                row.get("last_seen", ""),
            ))
            migrated_jobs += 1
        print(f"  [OK] {migrated_jobs} jobs migrated.")
    except Exception as e:
        print(f"  [!] Error migrating jobs: {e}")

    # 2. Migrate Companies
    try:
        sqlite_cur.execute("SELECT * FROM companies")
        companies = sqlite_cur.fetchall()
        print(f"-> Migrating {len(companies)} companies...")
        for c in companies:
            row = dict(c)
            mysql_cur.execute("""
                INSERT INTO companies (
                    id, name, domain, careers_url, ats_platform, ats_slug,
                    crawl_status, last_crawled_at, created_at, founded_year,
                    employee_count, tags, bd_friendly, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE name=VALUES(name)
            """, (
                row.get("id"), row.get("name", ""), row.get("domain", ""),
                row.get("careers_url", ""), row.get("ats_platform", "unknown"),
                row.get("ats_slug", ""), row.get("crawl_status", "active"),
                row.get("last_crawled_at", ""), row.get("created_at", ""),
                row.get("founded_year"), row.get("employee_count", ""),
                row.get("tags", ""), row.get("bd_friendly", row.get("india_friendly", "maybe")),
                row.get("notes", ""),
            ))
        print(f"  [OK] {len(companies)} companies migrated.")
    except Exception as e:
        print(f"  [!] Error migrating companies: {e}")

    # 3. Migrate Profiles
    try:
        sqlite_cur.execute("SELECT * FROM profiles")
        profiles = sqlite_cur.fetchall()
        print(f"-> Migrating {len(profiles)} profiles...")
        for p in profiles:
            row = dict(p)
            mysql_cur.execute("""
                INSERT INTO profiles (id, name, description, config_json, created_at, updated_at, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE name=VALUES(name), config_json=VALUES(config_json)
            """, (
                row.get("id"), row.get("name", ""), row.get("description", ""),
                row.get("config_json", "{}"), row.get("created_at", ""),
                row.get("updated_at", ""), row.get("source", "custom"),
            ))
        print(f"  [OK] {len(profiles)} profiles migrated.")
    except Exception as e:
        print(f"  [!] Error migrating profiles: {e}")

    # 4. Migrate Outreach
    try:
        sqlite_cur.execute("SELECT * FROM outreach")
        outreach = sqlite_cur.fetchall()
        print(f"-> Migrating {len(outreach)} outreach items...")
        for o in outreach:
            row = dict(o)
            mysql_cur.execute("""
                INSERT INTO outreach (
                    id, job_id, job_title, company, company_domain, contact_name,
                    contact_position, contact_linkedin, dm_short, dm_long, status,
                    messaged_at, replied_at, followed_up_at, created_at, notes, emailed_at, profile_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE status=VALUES(status)
            """, (
                row.get("id"), row.get("job_id", ""), row.get("job_title", ""),
                row.get("company", ""), row.get("company_domain", ""),
                row.get("contact_name", ""), row.get("contact_position", ""),
                row.get("contact_linkedin", ""), row.get("dm_short", ""),
                row.get("dm_long", ""), row.get("status", "pending"),
                row.get("messaged_at", ""), row.get("replied_at", ""),
                row.get("followed_up_at", ""), row.get("created_at", ""),
                row.get("notes", ""), row.get("emailed_at", ""),
                row.get("profile_id"),
            ))
        print(f"  [OK] {len(outreach)} outreach items migrated.")
    except Exception as e:
        print(f"  [!] Error migrating outreach: {e}")

    sqlite_conn.close()
    mysql_conn.close()
    print("=== Migration Completed Successfully! ===")


if __name__ == "__main__":
    migrate()
