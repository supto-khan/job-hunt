"""Orchestrates fetching from all sources, scoring, dedup, and storage.
Two tracks: job boards (existing) + company ATS crawling (new)."""

import asyncio
from datetime import datetime
from core.models import Job
from core.database import (
    insert_job, init_db, get_companies, update_company_crawl_status,
    cleanup_old_jobs,
)
from core.scorer import score_job
from core.profile import get_active_profile
from sources.remotive import RemotiveSource
from sources.remoteok import RemoteOKSource
from sources.arbeitnow import ArbeitnowSource
from sources.jsearch import JSearchSource
from sources.greenhouse import GreenhouseSource
from sources.lever import LeverSource
from sources.ashby import AshbySource
from sources.html_scraper import HTMLCareerSource
from sources.hn_algolia import HackerNewsSource
from sources.rss import RSSSource
from sources.jobicy import JobicySource
from sources.workable import WorkableSource
from sources.recruitee import RecruiteeSource
from sources.bamboohr import BambooHRSource
from sources.smartrecruiters import SmartRecruitersSource
from sources.adzuna import AdzunaSource
from sources.freehire import FreeHireSource
from config.settings import RAPIDAPI_KEY

# Days before a job not re-seen gets deleted (cleanup). Could be profile-driven
# in the future, but it's a storage-cost concern, not a user preference.
STALE_JOB_DAYS = 14


def log(msg):
    print(msg, flush=True)


def _build_job_board_sources() -> list:
    """Build the list of sources fresh each run so JSearch uses current queries."""
    sources = [
        FreeHireSource(),
        RemotiveSource(),
        RemoteOKSource(),
        ArbeitnowSource(),
        HackerNewsSource(),
        RSSSource(),
        JobicySource(),
        GreenhouseSource(),
        LeverSource(),
        AshbySource(),
        WorkableSource(),
        SmartRecruitersSource(),
        AdzunaSource(),
    ]
    if RAPIDAPI_KEY:
        try:
            profile = get_active_profile()
            profile_queries = (profile.get("search") or {}).get("jsearch_default_queries") or []
            queries = [
                {
                    "query": q["query"],
                    "country": q.get("country", "BD"),
                    "date_posted": q.get("date_posted", "3days"),
                    **({"remote_jobs_only": "true"} if q.get("remote_jobs_only") else {}),
                }
                for q in profile_queries
                if q.get("query") and q.get("enabled", True)
            ]
            if queries:
                sources.append(JSearchSource(queries=queries))
        except Exception as e:
            log(f"  [WARN] JSearch profile query load failed: {e}")
    return sources

COMPANY_CRAWL_CONCURRENCY = 5


def _make_ats_source(company: dict):
    """Factory: return the right source class for a company's ATS."""
    platform = company.get("ats_platform", "unknown")
    if platform == "greenhouse":
        return GreenhouseSource(company)
    elif platform == "lever":
        return LeverSource(company)
    elif platform == "ashby":
        return AshbySource(company)
    elif platform == "workable":
        return WorkableSource(company)
    elif platform == "recruitee":
        return RecruiteeSource(company)
    elif platform == "bamboohr":
        return BambooHRSource(company)
    elif platform == "html":
        return HTMLCareerSource(company)
    return None


async def _fetch_from_source(source) -> list[Job]:
    """Fetch jobs from a single source with error handling."""
    try:
        jobs = await source.fetch()
        log(f"  [OK] {source.name}: {len(jobs)} jobs fetched")
        return jobs
    except Exception as e:
        log(f"  [FAIL] {source.name}: {e}")
        return []


def _score_and_store(jobs: list[Job], stats: dict, profile: dict = None):
    """Score, filter, deduplicate, and store jobs. Shared by both tracks."""
    stats.setdefault("filtered_out", 0)
    stats.setdefault("new", 0)
    stats.setdefault("updated", 0)
    profile = profile or get_active_profile()
    profile_id = profile.get("_id")
    min_store = int((profile.get("scoring") or {}).get("min_score_to_store", 25))

    for job in jobs:
        result = score_job(job.title, job.description, job.location, profile=profile)

        # Filter: drop irrelevant jobs before storing (saves DB space)
        if result["score"] < min_store:
            stats["filtered_out"] += 1
            continue

        job.relevance_score = result["score"]
        job.experience_level = result["experience_level"]
        job.india_friendly = result["india_friendly"]
        job.location_note = result["location_note"]

        existing_tech = set(t.strip() for t in job.tech_stack.split(",") if t.strip())
        existing_tech.update(result["tech_stack"])
        job.tech_stack = ", ".join(sorted(existing_tech))

        if not job.company_domain:
            job.company_domain = job.extract_domain()

        job_dict = job.model_dump()
        job_dict["id"] = job.fingerprint
        job_dict["discovered_at"] = datetime.utcnow().isoformat()
        job_dict["scored_profile_id"] = profile_id

        result_status = insert_job(job_dict)
        if result_status == "new":
            stats["new"] += 1
            if result["score"] >= 80:
                stats.setdefault("new_high_matches", []).append(job_dict)
        else:
            stats["updated"] = stats.get("updated", 0) + 1


async def run_company_crawl(company_ids: list[str] = None) -> dict:
    """Track B: crawl jobs from companies in the DB."""
    init_db()
    log("Starting company crawl...")
    stats = {"fetched": 0, "new": 0, "updated": 0, "filtered_out": 0, "sources": {},
             "companies_crawled": 0, "companies_failed": 0}

    companies = get_companies(crawl_status="active")
    if company_ids:
        companies = [c for c in companies if c["id"] in company_ids]

    if not companies:
        log("  No active companies to crawl. Seed first with /api/companies/seed")
        return stats

    log(f"  Crawling {len(companies)} companies...")
    semaphore = asyncio.Semaphore(COMPANY_CRAWL_CONCURRENCY)

    async def crawl_one(company: dict) -> list[Job]:
        source = _make_ats_source(company)
        if not source:
            return []
        async with semaphore:
            try:
                jobs = await source.fetch()
                update_company_crawl_status(
                    company["id"], "active", datetime.utcnow().isoformat()
                )
                log(f"  [OK] {company['name']} ({company['ats_platform']}): {len(jobs)} jobs")
                stats["companies_crawled"] += 1
                stats["sources"][f"{company['ats_platform']}:{company['ats_slug']}"] = len(jobs)
                return jobs
            except Exception as e:
                update_company_crawl_status(
                    company["id"], "failed", datetime.utcnow().isoformat()
                )
                log(f"  [FAIL] {company['name']}: {e}")
                stats["companies_failed"] += 1
                return []

    tasks = [crawl_one(c) for c in companies]
    results = await asyncio.gather(*tasks)

    all_jobs = [job for batch in results for job in batch]
    stats["fetched"] = len(all_jobs)

    log(f"  Total from companies: {len(all_jobs)}")
    profile = get_active_profile()
    _score_and_store(all_jobs, stats, profile=profile)

    log(f"  Companies crawled: {stats['companies_crawled']}")
    log(f"  Companies failed: {stats['companies_failed']}")
    log(f"  New: {stats['new']} | Updated: {stats.get('updated', 0)} | Filtered out: {stats.get('filtered_out', 0)}")
    return stats


async def run_job_boards() -> dict:
    """Track A: fetch from existing job boards."""
    stats = {"fetched": 0, "new": 0, "updated": 0, "filtered_out": 0, "sources": {}}

    sources = _build_job_board_sources()
    tasks = [_fetch_from_source(src) for src in sources]
    results = await asyncio.gather(*tasks)

    all_jobs: list[Job] = []
    for source, jobs in zip(sources, results):
        stats["sources"][source.name] = len(jobs)
        all_jobs.extend(jobs)

    stats["fetched"] = len(all_jobs)
    profile = get_active_profile()
    _score_and_store(all_jobs, stats, profile=profile)
    return stats


async def run_collection(include_companies: bool = True) -> dict:
    """Run full collection: job boards + company crawl."""
    init_db()
    log("=" * 50)
    log("Starting full collection...")

    # Track A: job boards
    log("\n--- Job Boards ---")
    board_stats = await run_job_boards()

    # Track B: company crawl
    company_stats = {"fetched": 0, "new": 0, "updated": 0, "filtered_out": 0,
                     "companies_crawled": 0, "companies_failed": 0}
    if include_companies:
        log("\n--- Company Crawl ---")
        company_stats = await run_company_crawl()

    # Cleanup: delete jobs not re-seen in last N days
    log(f"\n--- Cleanup (jobs older than {STALE_JOB_DAYS} days) ---")
    deleted = cleanup_old_jobs(days=STALE_JOB_DAYS)
    log(f"  Deleted {deleted} stale jobs")

    # Merge stats
    new_high_matches = board_stats.get("new_high_matches", []) + company_stats.get("new_high_matches", [])
    if new_high_matches:
        try:
            from core.notifications import send_instant_job_alerts
            alerts_sent = send_instant_job_alerts(new_high_matches)
            log(f"  Notifications: Sent {alerts_sent} instant alerts (Discord/Telegram)")
        except Exception as e:
            log(f"  Notifications Error: {e}")

    total = {
        "fetched": board_stats["fetched"] + company_stats["fetched"],
        "new": board_stats["new"] + company_stats["new"],
        "updated": board_stats.get("updated", 0) + company_stats.get("updated", 0),
        "filtered_out": board_stats.get("filtered_out", 0) + company_stats.get("filtered_out", 0),
        "deleted_stale": deleted,
        "board_sources": board_stats["sources"],
        "companies_crawled": company_stats.get("companies_crawled", 0),
        "companies_failed": company_stats.get("companies_failed", 0),
    }

    log(f"\n--- Summary ---")
    log(f"  Total fetched: {total['fetched']}")
    log(f"  New: {total['new']} | Updated (already existed): {total['updated']}")
    log(f"  Filtered out (low score): {total['filtered_out']}")
    log(f"  Deleted (stale): {total['deleted_stale']}")
    log("Collection complete!")
    log("=" * 50)
    return total


async def run_multi_profile_hunt(remote_only: bool = True) -> dict:
    """24/7 continuous search & scoring pipeline across all 3 candidate profiles."""
    from core.profile import get_hunting_profiles
    from core.emailer import generate_outreach_for_top_jobs
    import json

    init_db()
    profiles = get_hunting_profiles()
    if not profiles:
        log("[24/7 Hunt] No candidate profiles found.")
        return {}

    log("=" * 60)
    log(f"⚡ [24/7 Remote Job Hunt] Starting cycle across {len(profiles)} candidate profiles...")
    for p in profiles:
        log(f"  • Candidate Profile #{p.get('_id')}: {p.get('_name')}")

    # 1. Aggregate unique search terms across all profiles for FreeHire
    all_terms: list[str] = []
    for p in profiles:
        terms = (p.get("search") or {}).get("default_terms") or []
        all_terms.extend(terms[:4])

    seen_terms = set()
    deduped_terms: list[str] = []
    for t in all_terms:
        clean = t.strip().lower()
        if clean and clean not in seen_terms:
            seen_terms.add(clean)
            deduped_terms.append(t)

    # 2. Build multi-source list with FreeHire querying all profile terms
    sources = [
        FreeHireSource(queries=deduped_terms, work_mode="remote" if remote_only else None, limit_per_query=50),
        RemotiveSource(),
        RemoteOKSource(),
        ArbeitnowSource(),
        HackerNewsSource(),
        RSSSource(),
        JobicySource(),
        GreenhouseSource(),
        LeverSource(),
        AshbySource(),
        WorkableSource(),
        SmartRecruitersSource(),
        AdzunaSource(),
    ]

    log(f"  Gathering live remote postings from {len(sources)} sources...")
    tasks = [_fetch_from_source(src) for src in sources]
    results = await asyncio.gather(*tasks)

    all_jobs: list[Job] = []
    for r in results:
        all_jobs.extend(r)

    # Filter strictly for remote if remote_only is True
    if remote_only:
        filtered_jobs = []
        for j in all_jobs:
            loc_str = (j.location or "").lower()
            title_str = (j.title or "").lower()
            desc_str = (j.description or "").lower()
            wm = getattr(j, "work_mode", "")
            # If explicit remote flag, or contains 'remote' or 'anywhere' or 'worldwide'
            if wm == "remote" or "remote" in loc_str or "anywhere" in loc_str or "worldwide" in loc_str or "remote" in title_str or "100% remote" in desc_str:
                filtered_jobs.append(j)
            elif not wm and not loc_str:  # Unspecified location on remote job boards
                filtered_jobs.append(j)
        all_jobs = filtered_jobs

    log(f"  Total remote postings fetched across all sources: {len(all_jobs)}")

    # 3. Score against each candidate profile and generate tailored outreach
    results_by_profile = {}
    high_matches_total = []

    for prof in profiles:
        prof_name = prof.get("_name")
        prof_id = prof.get("_id")
        prof_stats = {
            "fetched": len(all_jobs),
            "new": 0,
            "updated": 0,
            "filtered_out": 0,
            "new_high_matches": [],
        }

        # Score & store matching jobs for this profile
        _score_and_store(all_jobs, prof_stats, profile=prof)

        # Generate outreach for this profile
        outreach_gen = 0
        try:
            outreach_gen = generate_outreach_for_top_jobs(limit=5, profile=prof)
        except Exception as e:
            log(f"  [WARN] Outreach generation error for {prof_name}: {e}")

        results_by_profile[prof_name] = {
            "profile_id": prof_id,
            "new": prof_stats["new"],
            "updated": prof_stats["updated"],
            "filtered_out": prof_stats["filtered_out"],
            "high_matches": len(prof_stats.get("new_high_matches", [])),
            "outreach_generated": outreach_gen,
        }
        high_matches_total.extend(prof_stats.get("new_high_matches", []))

    # 4. Cleanup stale postings
    deleted = cleanup_old_jobs(days=STALE_JOB_DAYS)

    # 5. Send alerts if any high match discovered
    if high_matches_total:
        try:
            from core.notifications import send_instant_job_alerts
            send_instant_job_alerts(high_matches_total)
        except Exception as e:
            log(f"  [WARN] Alert error: {e}")

    # Record last run in app_settings
    try:
        from core.database import get_connection
        conn = get_connection()
        with conn.cursor() as cur:
            ts = datetime.utcnow().isoformat()
            cur.execute(
                "INSERT INTO app_settings (`key`, `value`, updated_at) "
                "VALUES ('24_7_last_run', %s, %s) "
                "ON DUPLICATE KEY UPDATE `value`=VALUES(`value`), updated_at=VALUES(updated_at)",
                (json.dumps({
                    "timestamp": ts,
                    "total_fetched": len(all_jobs),
                    "profiles": results_by_profile,
                }), ts)
            )
        conn.close()
    except Exception as e:
        log(f"  [WARN] Could not update 24_7_last_run setting: {e}")

    log(f"⚡ [24/7 Remote Job Hunt] Complete! Summary: {results_by_profile}")
    log("=" * 60)
    return results_by_profile

