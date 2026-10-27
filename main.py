import uvicorn
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.database import (
    init_db, get_jobs, get_job_by_id, update_job_status, get_stats, get_sources,
    upsert_company, get_companies, get_company_by_id,
    update_company_crawl_status, get_company_stats,
    insert_outreach, get_outreach, update_outreach_status, update_outreach_notes,
    outreach_exists_for_job, get_outreach_stats,
    toggle_mark_for_email, get_marked_jobs, insert_job,
)
from core.collector import run_collection, run_company_crawl, run_multi_profile_hunt
from core.sheets import export_to_sheet
from core.emailer import run_daily_pipeline, send_daily_digest, generate_outreach_for_top_jobs
from core.profile import (
    get_active_profile, list_profiles, get_profile, create_profile,
    update_profile, activate_profile, delete_profile, duplicate_profile,
    import_preset, export_profile, list_presets,
    get_active_profile_queries, add_active_profile_query,
    update_active_profile_query, delete_active_profile_query,
    ensure_core_profiles, get_hunting_profiles,
)
from config.settings import (
    HOST, PORT, GOOGLE_SHEETS_CREDS, GOOGLE_SHEET_ID, HUNTER_API_KEY,
    DAILY_EMAIL_HOUR, DAILY_EMAIL_TIMEZONE, SENDER_EMAIL,
)

app = FastAPI(title="Job Scraper", version="2.0.0")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


scheduler = AsyncIOScheduler(timezone=DAILY_EMAIL_TIMEZONE)


@app.on_event("startup")
async def startup():
    init_db()
    try:
        ensure_core_profiles()
    except Exception as e:
        print(f"[WARN] Error ensuring core profiles: {e}", flush=True)

    # 24/7 Continuous Remote Job Hunt: runs every 2 hours across all 3 candidate profiles
    scheduler.add_job(
        run_multi_profile_hunt,
        IntervalTrigger(hours=2),
        id="continuous_24_7_remote_hunt",
        replace_existing=True,
        kwargs={"remote_only": True},
    )

    # Schedule daily job search & email digest at 10:00 AM BST (Asia/Dhaka)
    scheduler.add_job(
        run_daily_pipeline,
        CronTrigger(hour=DAILY_EMAIL_HOUR, minute=0),
        id="daily_digest",
        replace_existing=True,
        kwargs={"send": bool(SENDER_EMAIL)},
    )
    scheduler.start()
    print("✅ 24/7 Automated Remote Job Hunter started (Every 2 hours across all 3 CV profiles)", flush=True)
    print(f"✅ Automated Daily Search & Pipeline scheduled for {DAILY_EMAIL_HOUR}:00 AM ({DAILY_EMAIL_TIMEZONE})", flush=True)


@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon.png")


@app.on_event("shutdown")
async def shutdown():
    if scheduler.running:
        scheduler.shutdown()


# ── Jobs API ───────────────────────────────────────────────────

@app.get("/api/jobs")
async def api_get_jobs(
    source: Optional[str] = None,
    status: Optional[str] = None,
    min_score: int = Query(0, ge=0, le=100),
    search: Optional[str] = None,
    location: Optional[str] = None,
    tech: Optional[str] = None,
    bd_friendly: Optional[str] = None,
    india_friendly: Optional[str] = None,
    company_domain: Optional[str] = None,
    profile_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    loc_filter = bd_friendly or india_friendly
    jobs = get_jobs(
        source=source, status=status, min_score=min_score,
        search=search, location=location, tech=tech,
        bd_friendly=loc_filter, company_domain=company_domain,
        profile_id=profile_id,
        limit=limit, offset=offset,
    )
    return {"jobs": jobs, "count": len(jobs)}


@app.get("/api/jobs/{job_id}")
async def api_get_job(job_id: str):
    job = get_job_by_id(job_id)
    if not job:
        return {"error": "Job not found"}
    return job


@app.patch("/api/jobs/{job_id}/status")
async def api_update_status(job_id: str, status: str = Query(...)):
    update_job_status(job_id, status)
    return {"ok": True}


@app.get("/api/stats")
async def api_stats():
    return get_stats()


@app.get("/api/sources")
async def api_sources():
    return {"sources": get_sources()}


@app.post("/api/job-sync")
async def api_collect(generate_outreach: bool = Query(True)):
    from datetime import datetime
    cutoff = datetime.utcnow().isoformat()
    stats = await run_collection()
    if generate_outreach:
        # Only pick from jobs seen in this collection run — avoids re-using
        # stale 3-year-old python listings still sitting in the DB.
        stats["outreach_generated"] = generate_outreach_for_top_jobs(seen_after=cutoff)
    return stats


# ── 24/7 Automated Multi-Profile Remote Hunt ──────────────────

@app.post("/api/hunt-all")
async def api_hunt_all(remote_only: bool = Query(True)):
    """Run an immediate 24/7 multi-profile remote collection cycle across all 3 CV profiles."""
    summary = await run_multi_profile_hunt(remote_only=remote_only)
    return {"ok": True, "profiles": summary}


@app.get("/api/hunt-status")
async def api_hunt_status():
    """Return status, schedule, and recent stats of the 24/7 automated remote job hunt."""
    from core.database import get_connection
    import json

    job = scheduler.get_job("continuous_24_7_remote_hunt")
    next_run = str(job.next_run_time) if job and job.next_run_time else None

    last_run_data = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT `value` FROM app_settings WHERE `key` = '24_7_last_run'")
            row = cur.fetchone()
            if row and row["value"]:
                last_run_data = json.loads(row["value"])
        conn.close()
    except Exception:
        pass

    return {
        "active": scheduler.running and job is not None,
        "interval_hours": 2,
        "target": "Strictly Remote (Worldwide & Timezone Compatible)",
        "next_run_time": next_run,
        "last_run": last_run_data,
        "profiles": list_profiles(),
    }


# ── Companies API ──────────────────────────────────────────────

@app.get("/api/companies")
async def api_get_companies(
    ats_platform: Optional[str] = None,
    crawl_status: Optional[str] = None,
    bd_friendly: Optional[str] = None,
    india_friendly: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    loc_filter = bd_friendly or india_friendly
    companies = get_companies(
        ats_platform=ats_platform, crawl_status=crawl_status,
        bd_friendly=loc_filter, search=search,
        limit=limit, offset=offset,
    )
    return {"companies": companies, "count": len(companies)}


class CompanyInput(BaseModel):
    name: str
    domain: str = ""
    careers_url: str = ""
    ats_platform: str = "unknown"
    ats_slug: str = ""
    founded_year: int = 0
    employee_count: str = ""
    tags: str = ""
    india_friendly: str = "unknown"
    notes: str = ""


@app.post("/api/companies")
async def api_add_company(body: CompanyInput):
    from core.models import Company
    data = body.model_dump()
    data["id"] = Company.make_id(data["name"])
    data["last_crawled"] = ""
    data["crawl_status"] = "active"
    upsert_company(data)
    return {"ok": True, "id": data["id"]}


@app.patch("/api/companies/{company_id}")
async def api_update_company(company_id: str, body: CompanyInput):
    existing = get_company_by_id(company_id)
    if not existing:
        return {"error": "Not found"}
    data = body.model_dump()
    data["id"] = company_id
    data["last_crawled"] = existing.get("last_crawled", "")
    data["crawl_status"] = existing.get("crawl_status", "active")
    upsert_company(data)
    return {"ok": True}


@app.delete("/api/companies/{company_id}")
async def api_pause_company(company_id: str):
    from datetime import datetime
    update_company_crawl_status(company_id, "paused", datetime.utcnow().isoformat())
    return {"ok": True}


@app.post("/api/companies/{company_id}/activate")
async def api_activate_company(company_id: str):
    update_company_crawl_status(company_id, "active")
    return {"ok": True}


@app.get("/api/companies/stats")
async def api_company_stats():
    return get_company_stats()


@app.post("/api/companies/seed")
async def api_seed_companies():
    from core.company_seeder import get_all_seed_companies
    companies = get_all_seed_companies()
    added = 0
    for c in companies:
        if upsert_company(c):
            added += 1
    return {"seeded": len(companies), "added": added}


@app.post("/api/companies/mega-seed")
async def api_mega_seed():
    """Load 250+ Bangladesh + MNC + Global remote companies."""
    from core.mega_companies import get_all_mega_companies
    companies = get_all_mega_companies()
    added = 0
    for c in companies:
        if upsert_company(c):
            added += 1
    return {"total_in_list": len(companies), "added": added}


@app.post("/api/companies/{company_id}/crawl")
async def api_crawl_company(company_id: str):
    stats = await run_company_crawl(company_ids=[company_id])
    return stats


@app.post("/api/companies/crawl")
async def api_crawl_all_companies():
    stats = await run_company_crawl()
    return stats


@app.post("/api/companies/detect-ats")
async def api_detect_ats(domain: str = Query(...)):
    from core.company_seeder import detect_ats_platform
    result = await detect_ats_platform(domain)
    return result


@app.post("/api/companies/discover")
async def api_discover_companies(
    sources: str = Query("yc,remoteintech,wwr"),
    detect_ats: bool = Query(True),
    min_team_size: int = Query(10, ge=1),
):
    """Bulk discover companies from YC, RemoteInTech, WeWorkRemotely."""
    from core.bulk_discover import run_bulk_discovery
    source_list = [s.strip() for s in sources.split(",") if s.strip()]
    stats = await run_bulk_discovery(
        sources=source_list, detect_ats=detect_ats, min_team_size=min_team_size,
    )
    return stats


# ── Google Sheets Export ───────────────────────────────────────

@app.post("/api/export/sheets")
async def api_export_sheets(
    min_score: int = Query(0, ge=0, le=100),
    bd_friendly: Optional[str] = None,
    india_friendly: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    tech: Optional[str] = None,
    mode: str = Query("replace"),
    sheet_name: str = Query("Jobs"),
):
    import os
    creds = GOOGLE_SHEETS_CREDS
    sheet_id = GOOGLE_SHEET_ID
    if not sheet_id:
        return {"error": "GOOGLE_SHEET_ID not set in .env"}
    if not os.path.exists(creds):
        return {"error": f"Credentials file not found: {creds}"}
    try:
        loc_filter = bd_friendly or india_friendly
        result = export_to_sheet(
            creds_file=creds, spreadsheet_id=sheet_id, sheet_name=sheet_name,
            min_score=min_score, india_friendly=loc_filter,
            source=source, search=search, tech=tech, mode=mode,
        )
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/export/sheets/status")
async def api_sheets_status():
    import os
    return {
        "configured": bool(GOOGLE_SHEET_ID) and os.path.exists(GOOGLE_SHEETS_CREDS),
        "sheet_id": GOOGLE_SHEET_ID[:10] + "..." if GOOGLE_SHEET_ID else "",
        "creds_exists": os.path.exists(GOOGLE_SHEETS_CREDS),
    }


# ── Outreach API ───────────────────────────────────────────────

@app.get("/api/outreach")
async def api_get_outreach(
    status: Optional[str] = None,
    search: Optional[str] = None,
    batch: Optional[str] = Query(None, pattern="^(new|old|all)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    from core.database import get_last_outreach_batch_at
    batch_filter = batch if batch in ("new", "old") else None
    items = get_outreach(status=status, search=search, batch=batch_filter,
                         limit=limit, offset=offset)
    return {
        "outreach": items,
        "count": len(items),
        "last_batch_at": get_last_outreach_batch_at(),
    }


@app.get("/api/outreach/stats")
async def api_outreach_stats():
    return get_outreach_stats()


class OutreachBulkDelete(BaseModel):
    ids: list[str]


@app.post("/api/outreach/bulk-delete")
async def api_outreach_bulk_delete(body: OutreachBulkDelete):
    from core.database import delete_outreach_bulk
    deleted = delete_outreach_bulk(body.ids)
    return {"deleted": deleted}


@app.post("/api/outreach/refresh")
async def api_outreach_refresh(limit: int = Query(15, ge=1, le=50),
                               min_score: int = Query(40, ge=0, le=100)):
    """Refresh = run a fresh collection, then generate outreach scoped to the
    jobs that were actually returned by that collection. Previous batches stay
    in place and show up in the 'Old' tab."""
    from datetime import datetime
    cutoff = datetime.utcnow().isoformat()
    collect_stats = await run_collection()
    generated = generate_outreach_for_top_jobs(
        limit=limit, min_score=min_score, seen_after=cutoff,
    )
    return {"collected": collect_stats, "generated": generated}


@app.post("/api/outreach/generate")
async def api_generate_outreach(
    min_score: int = Query(40, ge=0, le=100),
    limit: int = Query(15, ge=1, le=50),
    bd_friendly: Optional[str] = None,
    india_friendly: Optional[str] = "maybe",
):
    """For top N high-scoring jobs without existing outreach,
    build LinkedIn search URLs + generate DMs. No API credits used."""
    loc_filter = bd_friendly or india_friendly or "maybe"
    generated = generate_outreach_for_top_jobs(
        limit=limit, min_score=min_score, bd_friendly=loc_filter,
    )
    if generated == 0:
        return {"generated": 0, "message": "No new jobs eligible for outreach"}
    return {"generated": generated}


@app.patch("/api/outreach/{outreach_id}/status")
async def api_update_outreach(outreach_id: str, status: str = Query(...)):
    field_map = {"messaged": "messaged", "replied": "replied", "followed_up": "followed_up"}
    update_outreach_status(outreach_id, status, field=field_map.get(status))
    return {"ok": True}


@app.patch("/api/outreach/{outreach_id}/notes")
async def api_update_outreach_notes(outreach_id: str, notes: str = Query("")):
    update_outreach_notes(outreach_id, notes)
    return {"ok": True}


# ── Search Queries (stored on the active profile) ──────────────

@app.get("/api/search-queries")
async def api_get_queries():
    return {"queries": get_active_profile_queries()}


class QueryInput(BaseModel):
    query: str
    country: str = "BD"
    date_posted: str = "3days"
    remote_jobs_only: bool = False


@app.post("/api/search-queries")
async def api_add_query(body: QueryInput):
    try:
        qid = add_active_profile_query(
            body.query, body.country, body.date_posted, body.remote_jobs_only,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": qid, "ok": True}


class QueryPatch(BaseModel):
    query: Optional[str] = None
    country: Optional[str] = None
    date_posted: Optional[str] = None
    remote_jobs_only: Optional[bool] = None
    enabled: Optional[bool] = None


@app.patch("/api/search-queries/{qid}")
async def api_update_query(qid: int, body: QueryPatch):
    try:
        update_active_profile_query(qid, **body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@app.delete("/api/search-queries/{qid}")
async def api_delete_query(qid: int):
    try:
        delete_active_profile_query(qid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


# ── Mark Job for Email ─────────────────────────────────────────

@app.post("/api/jobs/{job_id}/mark-for-email")
async def api_mark_for_email(job_id: str):
    new_state = toggle_mark_for_email(job_id)
    return {"mark_for_email": new_state}


@app.get("/api/jobs/marked")
async def api_get_marked():
    return {"jobs": get_marked_jobs()}


# ── Email Digest API ───────────────────────────────────────────

@app.post("/api/email/send-now")
async def api_send_email_now(dry_run: bool = Query(False)):
    """Manually trigger the daily digest email."""
    result = send_daily_digest(dry_run=dry_run)
    return result


@app.post("/api/email/run-pipeline")
async def api_run_pipeline(send: bool = Query(True)):
    """Manually run the full daily pipeline: collect → outreach → email."""
    result = await run_daily_pipeline(send=send)
    return result


@app.get("/api/email/status")
async def api_email_status():
    from core.database import get_email_logs
    import os
    logs = get_email_logs(limit=10)
    out_cfg = get_active_profile().get("outreach") or {}
    profile_recipient = (out_cfg.get("recipient_email") or "").strip()
    env_recipient = os.getenv("RECIPIENT_EMAIL", "")
    effective_recipient = profile_recipient or env_recipient
    return {
        "sender_configured": bool(SENDER_EMAIL) and bool(os.getenv("SENDER_APP_PASSWORD")),
        "sender": SENDER_EMAIL,
        "sender_source": "env" if SENDER_EMAIL else "none",
        "recipient": effective_recipient,
        "recipient_source": "profile" if profile_recipient else ("env" if env_recipient else "none"),
        "candidate_name": out_cfg.get("candidate_name") or "",
        "scheduled_hour": DAILY_EMAIL_HOUR,
        "timezone": DAILY_EMAIL_TIMEZONE,
        "recent_sends": logs,
    }


@app.get("/api/jsearch/status")
async def api_jsearch_status():
    from core.database import get_api_usage
    import os
    usage = get_api_usage("jsearch")
    month_usage = usage.get("month", 0) if isinstance(usage, dict) else 0
    today_usage = usage.get("today", 0) if isinstance(usage, dict) else 0
    total_usage = usage.get("total", 0) if isinstance(usage, dict) else 0
    # Free tier: 200 requests/month
    monthly_limit = 200
    return {
        "configured": bool(os.getenv("RAPIDAPI_KEY")),
        "month": month_usage,
        "today": today_usage,
        "total": total_usage,
        "monthly_limit": monthly_limit,
        "remaining": max(0, monthly_limit - month_usage),
    }


@app.get("/api/hunter/status")
async def api_hunter_status():
    import httpx
    if not HUNTER_API_KEY:
        return {"configured": False}
    try:
        resp = httpx.get(
            "https://api.hunter.io/v2/account",
            params={"api_key": HUNTER_API_KEY}, timeout=10,
        )
        data = resp.json()
        if "data" in data:
            return {
                "configured": True,
                "plan": data["data"].get("plan_name", ""),
                "used": data["data"].get("requests", {}).get("used", 0),
                "available": data["data"].get("requests", {}).get("available", 0),
            }
        return {"configured": True, "error": "could not fetch stats"}
    except Exception as e:
        return {"configured": True, "error": str(e)}


# ── Profiles API ───────────────────────────────────────────────

@app.get("/api/profiles")
async def api_list_profiles():
    return {"profiles": list_profiles(), "presets": list_presets()}


@app.get("/api/profiles/active")
async def api_active_profile():
    cfg = get_active_profile()
    return {
        "id": cfg.get("_id"),
        "name": cfg.get("_name"),
        "config": {k: v for k, v in cfg.items() if not k.startswith("_")},
    }


@app.get("/api/profiles/{pid}")
async def api_get_profile(pid: int):
    row = get_profile(pid)
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return row


class ProfileInput(BaseModel):
    name: str
    description: str = ""
    config: dict


@app.post("/api/profiles")
async def api_create_profile(body: ProfileInput):
    try:
        pid = create_profile(body.name, body.config, body.description)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": pid, "ok": True}


@app.put("/api/profiles/{pid}")
async def api_update_profile(pid: int, body: ProfileInput):
    if not get_profile(pid):
        raise HTTPException(status_code=404, detail="Profile not found")
    update_profile(pid, config=body.config, name=body.name,
                   description=body.description)
    return {"ok": True}


@app.post("/api/profiles/{pid}/activate")
async def api_activate_profile(pid: int):
    try:
        activate_profile(pid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    # Queries now live on the profile itself — no separate seeding needed.
    queries_count = len((get_profile(pid) or {}).get("config", {}).get("search", {}).get("jsearch_default_queries") or [])
    return {"ok": True, "active": pid, "queries": queries_count}


@app.post("/api/profiles/{pid}/duplicate")
async def api_duplicate_profile(pid: int, name: Optional[str] = Query(None)):
    try:
        new_id = duplicate_profile(pid, new_name=name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "id": new_id}


@app.delete("/api/profiles/{pid}")
async def api_delete_profile(pid: int):
    try:
        delete_profile(pid)
    except ValueError as e:
        # Thrown when trying to delete the active profile
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


class PresetImport(BaseModel):
    preset_slug: str
    activate: bool = False
    overwrite: bool = False


@app.post("/api/profiles/import")
async def api_import_preset(body: PresetImport):
    try:
        pid = import_preset(body.preset_slug, activate=body.activate,
                            overwrite=body.overwrite)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    queries_count = len((get_profile(pid) or {}).get("config", {}).get("search", {}).get("jsearch_default_queries") or [])
    return {"ok": True, "id": pid, "queries": queries_count}


@app.get("/api/profiles/{pid}/export")
async def api_export_profile(pid: int):
    try:
        yaml_text = export_profile(pid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return PlainTextResponse(yaml_text, media_type="application/x-yaml")


@app.post("/api/profiles/rescore-all")
async def api_rescore_all(
    delete_below_min: bool = Query(False),
):
    """Re-score every job against the active profile. Optionally delete jobs
    that now score below the profile's min_score_to_store."""
    from core.database import get_connection
    from core.scorer import score_job

    profile = get_active_profile()
    profile_id = profile.get("_id")
    min_store = int((profile.get("scoring") or {}).get("min_score_to_store", 25))

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, title, description, location, tech_stack FROM jobs"
        ).fetchall()
    finally:
        conn.close()

    updated = 0
    deleted = 0
    conn = get_connection()
    try:
        for r in rows:
            result = score_job(r["title"], r["description"] or "",
                               r["location"] or "", profile=profile)

            if delete_below_min and result["score"] < min_store:
                conn.execute("DELETE FROM jobs WHERE id = ?", (r["id"],))
                deleted += 1
                continue

            existing_tech = set(
                t.strip() for t in (r["tech_stack"] or "").split(",") if t.strip()
            )
            existing_tech.update(result["tech_stack"])
            tech_stack = ", ".join(sorted(existing_tech))

            conn.execute(
                "UPDATE jobs SET relevance_score = ?, experience_level = ?, "
                "bd_friendly = ?, location_note = ?, tech_stack = ?, "
                "scored_profile_id = ? WHERE id = ?",
                (result["score"], result["experience_level"],
                 result["bd_friendly"], result["location_note"],
                 tech_stack, profile_id, r["id"]),
            )
            updated += 1
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "scanned": len(rows), "updated": updated, "deleted": deleted}


# ── FreeHire Direct Search & Import API ─────────────────────────────

@app.get("/freehire", response_class=HTMLResponse)
async def freehire_page(request: Request):
    return templates.TemplateResponse(request, "freehire.html")


@app.get("/api/freehire/search")
async def api_freehire_search(
    q: Optional[str] = None,
    work_mode: Optional[str] = "remote",
    seniority: Optional[str] = None,
    skills: Optional[str] = None,
    skills_mode: Optional[str] = "or",
    category: Optional[str] = None,
    countries: Optional[str] = None,
    regions: Optional[str] = None,
    is_tech: Optional[str] = "tech",
    posted_within_days: Optional[int] = 14,
    include_applied: bool = Query(False),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Direct live query to FreeHire API with filters, excluding already applied jobs."""
    import httpx
    import hashlib
    from config.settings import FREEHIRE_API_KEY
    from core.database import get_applied_job_signatures

    params = {
        "limit": limit,
        "offset": offset,
    }
    if q and q.strip():
        params["q"] = q.strip()
    if work_mode and work_mode != "all":
        params["work_mode"] = work_mode
    if seniority and seniority != "all":
        params["seniority"] = seniority
    if is_tech and is_tech != "all":
        params["is_tech"] = is_tech
    if posted_within_days and posted_within_days > 0:
        params["posted_within_days"] = posted_within_days
    if regions and regions != "all":
        params["regions"] = regions
    if countries and countries != "all":
        params["countries"] = countries
    if category and category != "all":
        params["category"] = category
    if skills and skills.strip():
        skill_list = [s.strip() for s in skills.split(",") if s.strip()]
        if skill_list:
            params["skills"] = skill_list
            if skills_mode in ("and", "or"):
                params["skills_mode"] = skills_mode

    headers = {
        "User-Agent": "job-hunter/1.0 (+https://github.com/supto-khan/job-hunt)",
        "Accept": "application/json",
    }
    if FREEHIRE_API_KEY:
        headers["Authorization"] = f"Bearer {FREEHIRE_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.get("https://freehire.me/api/v1/jobs/search", headers=headers, params=params)
            if resp.status_code != 200:
                return {
                    "error": f"FreeHire API returned status {resp.status_code}",
                    "jobs": [],
                    "total": 0,
                    "limit": limit,
                    "offset": offset,
                    "hidden_applied": 0,
                }
            payload = resp.json()
            raw_jobs = payload.get("data", [])
            meta = payload.get("meta", {})
            total = meta.get("total", len(raw_jobs))
    except Exception as e:
        return {
            "error": f"Failed to contact FreeHire API: {str(e)}",
            "jobs": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "hidden_applied": 0,
        }

    # Load applied job signatures to automatically hide already applied jobs
    applied_sigs = {"ids": set(), "urls": set(), "pairs": set()}
    try:
        applied_sigs = get_applied_job_signatures()
    except Exception:
        pass

    # Format jobs & filter out already applied postings
    formatted_jobs = []
    hidden_applied = 0
    for item in raw_jobs:
        title = (item.get("title") or "").strip()
        company = (item.get("company") or "").strip()
        loc = (item.get("location") or "").strip()
        url = (item.get("url") or "").strip()
        clean_url = url.strip().lower()
        base_url = clean_url.split("?")[0].rstrip("/")
        comp_norm = company.strip().lower()
        tit_norm = title.strip().lower()

        work_mode_val = item.get("work_mode") or ""
        if work_mode_val == "remote":
            if loc and "remote" not in loc.lower():
                display_location = f"Remote ({loc})"
            else:
                display_location = loc or "Remote"
        else:
            display_location = loc or "Remote"

        raw_key = f"{company.lower().strip()}|{title.lower().strip()}|{display_location.lower().strip()}"
        job_id = hashlib.md5(raw_key.encode()).hexdigest()

        # Check local DB
        is_saved = False
        saved_status = None
        saved_score = None
        try:
            local_job = get_job_by_id(job_id)
            if local_job:
                is_saved = True
                saved_status = local_job.get("status")
                saved_score = local_job.get("relevance_score")
        except Exception:
            pass

        # Exclude applied jobs
        is_applied = (
            saved_status == "applied"
            or job_id in applied_sigs["ids"]
            or (clean_url and clean_url in applied_sigs["urls"])
            or (base_url and base_url in applied_sigs["urls"])
            or ((comp_norm, tit_norm) in applied_sigs["pairs"])
        )

        if is_applied:
            hidden_applied += 1
            if not include_applied:
                continue

        enrichment = item.get("enrichment") or {}
        s_min = enrichment.get("salary_min")
        s_max = enrichment.get("salary_max")
        curr = enrichment.get("salary_currency", "")
        period = enrichment.get("salary_period", "")
        if s_min and s_max:
            salary_str = f"{curr} {s_min:,} - {s_max:,} / {period}".strip()
        elif s_min:
            salary_str = f"{curr} {s_min:,}+ / {period}".strip()
        else:
            salary_str = ""

        formatted_jobs.append({
            "id": job_id,
            "public_slug": item.get("public_slug", ""),
            "title": title,
            "company": company,
            "company_slug": item.get("company_slug", ""),
            "location": display_location,
            "raw_location": loc,
            "work_mode": work_mode_val,
            "source": item.get("source", "freehire"),
            "url": url,
            "posted_at": item.get("posted_at", ""),
            "skills": item.get("skills", []),
            "description": item.get("description", ""),
            "summary": enrichment.get("summary", ""),
            "salary": salary_str,
            "seniority": enrichment.get("seniority") or "",
            "employment_type": enrichment.get("employment_type") or "",
            "is_saved": is_saved,
            "saved_status": saved_status,
            "saved_score": saved_score,
            "is_applied": is_applied,
        })

    return {
        "jobs": formatted_jobs,
        "total": max(0, total - (0 if include_applied else hidden_applied)),
        "limit": limit,
        "offset": offset,
        "hidden_applied": hidden_applied,
    }


class FreeHireImportRequest(BaseModel):
    title: str
    company: str
    location: str = "Remote"
    description: str = ""
    url: str = ""
    source: str = "freehire"
    posted_at: Optional[str] = ""
    skills: list = []
    salary: Optional[str] = ""
    seniority: Optional[str] = ""
    work_mode: Optional[str] = ""
    status: Optional[str] = "new"


@app.post("/api/freehire/import")
async def api_freehire_import(body: FreeHireImportRequest):
    """Import a FreeHire job into local DB with automatic profile scoring."""
    from datetime import datetime
    from core.models import Job
    from core.database import insert_job, update_job_status
    from core.scorer import score_job
    from core.profile import get_active_profile

    profile = get_active_profile()
    profile_id = profile.get("_id")

    loc = body.location.strip()
    if body.work_mode == "remote":
        if loc and "remote" not in loc.lower():
            loc = f"Remote ({loc})"
        else:
            loc = loc or "Remote"

    tech_stack = ", ".join(body.skills) if body.skills else ""
    req_status = (body.status or "new").strip().lower()
    if req_status not in ("new", "applied", "reviewed"):
        req_status = "new"

    job = Job(
        title=body.title.strip(),
        company=body.company.strip(),
        location=loc,
        description=body.description,
        url=body.url,
        source="freehire",
        posted_date=body.posted_at or "",
        tech_stack=tech_stack,
        salary=body.salary or "",
        job_type="remote" if body.work_mode == "remote" else "full-time",
        status=req_status,
    )

    result = score_job(job.title, job.description, job.location, profile=profile)
    job.relevance_score = result["score"]
    job.experience_level = result.get("experience_level", "")
    job.bd_friendly = result.get("bd_friendly", "unknown")
    job.india_friendly = result.get("india_friendly", "unknown")
    job.location_note = result.get("location_note", "")

    existing_tech = set(t.strip() for t in job.tech_stack.split(",") if t.strip())
    existing_tech.update(result.get("tech_stack", []))
    job.tech_stack = ", ".join(sorted(existing_tech))

    if not job.company_domain:
        job.company_domain = job.extract_domain()

    job_dict = job.model_dump()
    job_dict["id"] = job.fingerprint
    job_dict["discovered_at"] = datetime.utcnow().isoformat()
    job_dict["scored_profile_id"] = profile_id
    job_dict["status"] = req_status

    status = insert_job(job_dict)
    if req_status == "applied":
        update_job_status(job.fingerprint, "applied")

    return {
        "ok": True,
        "status": status,
        "job_status": req_status,
        "score": job.relevance_score,
        "id": job.fingerprint,
    }


# ── UI Routes ──────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/outreach", response_class=HTMLResponse)
async def outreach_page(request: Request):
    return templates.TemplateResponse(request, "outreach.html")


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    return templates.TemplateResponse(request, "profile.html")


if __name__ == "__main__":
    print(f"Starting Job Scraper at http://{HOST}:{PORT}")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
