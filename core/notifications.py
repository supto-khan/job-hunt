"""Notification module for Discord Webhooks and Telegram Bot API.

Dispatches instant alerts for high-matching jobs (Relevance Score >= NOTIFY_MIN_SCORE)
and sends daily pipeline run summary digests.

100% free — uses standard httpx requests.
"""

import os
import logging
import httpx
from typing import List, Dict, Any, Optional
from config import settings

logger = logging.getLogger(__name__)


def send_discord_alert(job: Dict[str, Any], webhook_url: Optional[str] = None) -> bool:
    """Send a rich Discord Embed card for a high-matching job."""
    url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL") or getattr(settings, "DISCORD_WEBHOOK_URL", "")
    if not url or not url.strip():
        return False

    score = job.get("relevance_score", 0)
    title = job.get("title", "Job Posting")
    company = job.get("company", "Unknown Company")
    location = job.get("location", "Remote / Flexible")
    apply_url = job.get("url") or job.get("careers_url") or "#"
    tech_stack = job.get("tech_stack", "") or "N/A"
    bd_friendly = (job.get("india_friendly") or "maybe").upper()

    # Discord color decimal: Green=3066993 (#2ecc71), Purple=7101671 (#6c5ce7)
    color = 7101671 if score >= 80 else 3066993

    embed = {
        "title": f"🎯 High Match Job: {title}",
        "url": apply_url,
        "color": color,
        "fields": [
            {"name": "🏢 Company", "value": company, "inline": True},
            {"name": "📍 Location", "value": location, "inline": True},
            {"name": "⭐ Score", "value": f"**{score}/100**", "inline": True},
            {"name": "🇧🇩 BD Friendly", "value": bd_friendly, "inline": True},
            {"name": "🛠️ Tech Stack", "value": tech_stack[:250], "inline": False},
        ],
        "footer": {"text": "Job Hunter Automated Alert"},
    }

    payload = {"username": "Job Hunter Bot", "embeds": [embed]}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url.strip(), json=payload)
            return resp.status_code in (200, 204)
    except Exception as e:
        logger.warning(f"[Notifications] Discord dispatch failed: {e}")
        return False


def send_telegram_alert(job: Dict[str, Any], bot_token: Optional[str] = None, chat_id: Optional[str] = None) -> bool:
    """Send an HTML-formatted message card to a Telegram chat/channel."""
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN") or getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    target_chat = chat_id or os.getenv("TELEGRAM_CHAT_ID") or getattr(settings, "TELEGRAM_CHAT_ID", "")

    if not token or not target_chat:
        return False

    url = f"https://api.telegram.org/bot{token.strip()}/sendMessage"

    title = _escape_html(job.get("title", "Job Posting"))
    company = _escape_html(job.get("company", "Unknown"))
    location = _escape_html(job.get("location", "Remote"))
    score = job.get("relevance_score", 0)
    apply_url = job.get("url") or "#"
    tech = _escape_html(job.get("tech_stack", "N/A"))

    html_message = (
        f"🎯 <b>High Match Job Found!</b>\n\n"
        f"<b>Role:</b> {title}\n"
        f"<b>Company:</b> {company}\n"
        f"<b>Location:</b> {location}\n"
        f"<b>Relevance Score:</b> <code>{score}/100</code>\n"
        f"<b>Tech Stack:</b> {tech[:200]}\n\n"
        f"🔗 <a href='{apply_url}'>View & Apply Here</a>"
    )

    payload = {
        "chat_id": target_chat.strip(),
        "text": html_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        logger.warning(f"[Notifications] Telegram dispatch failed: {e}")
        return False


def send_instant_job_alerts(jobs: List[Dict[str, Any]], min_score: Optional[int] = None) -> int:
    """Dispatches instant notifications to configured channels for high matching jobs."""
    threshold = min_score if min_score is not None else int(os.getenv("NOTIFY_MIN_SCORE", getattr(settings, "NOTIFY_MIN_SCORE", 80)))
    
    top_jobs = [j for j in jobs if (j.get("relevance_score") or 0) >= threshold]
    if not top_jobs:
        return 0

    sent_count = 0
    for job in top_jobs[:10]:  # Cap at top 10 per run to prevent spam
        d_ok = send_discord_alert(job)
        t_ok = send_telegram_alert(job)
        if d_ok or t_ok:
            sent_count += 1

    return sent_count


def send_pipeline_summary_notification(summary: Dict[str, Any]) -> bool:
    """Send daily pipeline completion summary notification."""
    fetched = summary.get("collection", {}).get("new", 0)
    outreach = summary.get("outreach_generated", 0)

    # Discord Summary
    url = os.getenv("DISCORD_WEBHOOK_URL") or getattr(settings, "DISCORD_WEBHOOK_URL", "")
    if url and url.strip():
        embed = {
            "title": "🚀 Daily Job Scraper Run Completed",
            "color": 3066993,
            "fields": [
                {"name": "✨ New Jobs Added", "value": str(fetched), "inline": True},
                {"name": "✉️ Outreach Items", "value": str(outreach), "inline": True},
            ],
            "footer": {"text": "Job Hunter Automated Pipeline"},
        }
        try:
            with httpx.Client(timeout=10) as client:
                client.post(url.strip(), json={"username": "Job Hunter Bot", "embeds": [embed]})
        except Exception:
            pass

    # Telegram Summary
    token = os.getenv("TELEGRAM_BOT_TOKEN") or getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    target_chat = os.getenv("TELEGRAM_CHAT_ID") or getattr(settings, "TELEGRAM_CHAT_ID", "")
    if token and target_chat:
        msg = (
            f"🚀 <b>Daily Job Pipeline Completed</b>\n\n"
            f"✨ <b>New Jobs Discovered:</b> <code>{fetched}</code>\n"
            f"✉️ <b>Outreach Messages Generated:</b> <code>{outreach}</code>"
        )
        try:
            with httpx.Client(timeout=10) as client:
                client.post(
                    f"https://api.telegram.org/bot{token.strip()}/sendMessage",
                    json={"chat_id": target_chat.strip(), "text": msg, "parse_mode": "HTML"},
                )
        except Exception:
            pass

    return True


def _escape_html(s: str) -> str:
    if not s:
        return ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
