"""Multi-Provider Free LLM Client (Gemini + Groq Fallback Chain)

Provides automated failover between free AI providers:
  1. Primary: Google Gemini API (gemini-1.5-flash / gemini-2.0-flash)
  2. Secondary: Groq API (llama-3.3-70b-versatile)
  3. Fallback: None (triggers rule-based / template fallback in caller)

No extra dependencies required — uses existing `httpx` package.
"""

import os
import logging
from typing import Optional, Dict, Any
import httpx

from config import settings

logger = logging.getLogger(__name__)


def generate_text(prompt: str, system_instruction: str = "", timeout: float = 12.0) -> Optional[Dict[str, str]]:
    """Generate text using the AI provider fallback chain.

    Returns:
        dict: {"text": "...", "provider": "gemini" | "groq"} or None if all fail.
    """
    gemini_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", "")

    # 1. Try Gemini
    if gemini_key and gemini_key.strip():
        res = _call_gemini(prompt, system_instruction, gemini_key.strip(), timeout)
        if res:
            return {"text": res, "provider": "gemini"}
        logger.warning("[LLM] Gemini API call failed or rate-limited. Falling back to Groq...")

    # 2. Try Groq (Fallback)
    if groq_key and groq_key.strip():
        res = _call_groq(prompt, system_instruction, groq_key.strip(), timeout)
        if res:
            return {"text": res, "provider": "groq"}
        logger.warning("[LLM] Groq API call failed or rate-limited.")

    # 3. Both failed or no keys configured
    return None


def _call_gemini(prompt: str, system_instruction: str, api_key: str, timeout: float) -> Optional[str]:
    """Call Google Gemini REST API (v1beta generateContent)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    payload: Dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ]
    }
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates") or []
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts") or []
                    if parts:
                        return parts[0].get("text", "").strip()
            elif resp.status_code in (429, 403):
                logger.warning(f"[LLM] Gemini Rate Limited / Auth Error: {resp.status_code} - {resp.text[:150]}")
            else:
                logger.warning(f"[LLM] Gemini Error {resp.status_code}: {resp.text[:150]}")
    except Exception as e:
        logger.warning(f"[LLM] Gemini Exception: {e}")
    return None


def _call_groq(prompt: str, system_instruction: str, api_key: str, timeout: float) -> Optional[str]:
    """Call Groq OpenAI-compatible Chat Completions API."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1000,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices") or []
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
            elif resp.status_code in (429, 403):
                logger.warning(f"[LLM] Groq Rate Limited / Auth Error: {resp.status_code} - {resp.text[:150]}")
            else:
                logger.warning(f"[LLM] Groq Error {resp.status_code}: {resp.text[:150]}")
    except Exception as e:
        logger.warning(f"[LLM] Groq Exception: {e}")
    return None


def generate_ai_outreach_dm(job: dict, profile: dict) -> Optional[Dict[str, str]]:
    """Use AI fallback chain to generate tailored LinkedIn DMs (short + long).

    Returns {"short": "...", "long": "..."} or None if AI is unavailable.
    """
    out_cfg = profile.get("outreach", {})
    candidate_name = out_cfg.get("candidate_name") or "Candidate"
    candidate_core = ", ".join(out_cfg.get("candidate_core_tech") or [])
    candidate_bio = out_cfg.get("bio_short") or ""
    achievements = "\n- ".join(out_cfg.get("achievements") or [])

    job_title = job.get("title", "")
    company = job.get("company", "")
    description = job.get("description", "") or job.get("snippet", "") or ""

    system_instruction = (
        "You are an expert technical recruiter and outreach assistant. Your task is to write high-converting, "
        "polite, professional, and personalized cold outreach DMs for a developer applying to a role."
    )

    prompt = f"""
Candidate Info:
- Name: {candidate_name}
- Tech Stack: {candidate_core}
- Bio Summary: {candidate_bio}
- Key Achievements:
- {achievements}

Job Info:
- Title: {job_title}
- Company: {company}
- Job Snippet/Description: {description[:1000]}

Instructions:
Generate TWO distinct messages formatted strictly as valid JSON with keys "short" and "long":
1. "short": A punchy LinkedIn Connection Note under 280 characters. Mention {candidate_name}'s core background and interest in {job_title} at {company}.
2. "long": A detailed 3-4 sentence LinkedIn InMail message highlighting relevant achievements aligned with {company}'s tech/domain.

Return ONLY the JSON object. Do not include markdown code block backticks.
""".strip()

    result = generate_text(prompt, system_instruction=system_instruction)
    if not result:
        return None

    raw_text = result["text"]
    # Clean possible markdown formatting
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw_text = "\n".join(lines).strip()

    import json
    try:
        parsed = json.loads(raw_text)
        short_msg = parsed.get("short", "").strip()
        long_msg = parsed.get("long", "").strip()
        
        if short_msg and long_msg:
            # Enforce LinkedIn connection note character limit
            if len(short_msg) > 300:
                short_msg = short_msg[:297].rstrip() + "..."
            return {"short": short_msg, "long": long_msg, "provider": result["provider"]}
    except Exception as e:
        logger.warning(f"[LLM] Failed to parse JSON from AI response: {e}. Raw response: {raw_text[:100]}")

    return None
