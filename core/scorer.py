import re
from core.profile import get_active_profile


def extract_tech_stack(text: str, profile: dict = None) -> list[str]:
    """Extract matching tech keywords from text using regex word boundaries to avoid substring false positives."""
    profile = profile or get_active_profile()
    tech_list = profile["search"].get("relevant_tech") or []
    text_lower = text.lower()
    found = []
    for tech in tech_list:
        t_clean = tech.strip().lower()
        if not t_clean:
            continue
        # Use regex word boundaries for single words/acronyms to prevent false substring hits (e.g. 'c' in 'docker', 'php' in 'graphical')
        pattern = r'\b' + re.escape(t_clean) + r'\b'
        if re.search(pattern, text_lower):
            found.append(tech)
    return found


def estimate_experience_level(text: str) -> str:
    """Guess experience level from description using word-boundary pattern matching."""
    text_lower = text.lower()
    fresher_patterns = [
        r'\bintern\b', r'\binternship\b', r'\btrainee\b', r'\bentry level\b', r'\bentry-level\b',
        r'\b0-1 year\b', r'\b0-2 years\b', r'\bfresher\b', r'\bnew grad\b', r'\bgraduate\b'
    ]
    if any(re.search(pat, text_lower) for pat in fresher_patterns):
        return "fresher"

    senior_patterns = [
        r'\bsenior\b', r'\bsr\.\b', r'\bsr\b', r'\blead\b', r'\bprincipal\b', r'\bstaff\b',
        r'\b8\+ years\b', r'\b10\+ years\b'
    ]
    if any(re.search(pat, text_lower) for pat in senior_patterns):
        return "senior"

    junior_patterns = [
        r'\bjunior\b', r'\bjr\.\b', r'\bjr\b', r'\b1\+ year\b', r'\b1-2 years\b'
    ]
    if any(re.search(pat, text_lower) for pat in junior_patterns):
        return "junior"

    mid_patterns = [
        r'\bmid\b', r'\bmiddle\b', r'\b3\+ years\b', r'\b2\+ years\b', r'\b4\+ years\b', r'\b5\+ years\b'
    ]
    if any(re.search(pat, text_lower) for pat in mid_patterns):
        return "mid"
    return "mid"


def check_bd_friendly(location: str, description: str,
                      profile: dict = None) -> dict:
    """Determine if a remote job is accessible from Bangladesh.
    Returns:
        result: 'yes' | 'no' | 'maybe'
        note: explanation string
    """
    profile = profile or get_active_profile()
    loc_cfg = profile["location"]
    bd_pos = loc_cfg.get("bd_positive") or loc_cfg.get("india_positive") or []
    bd_neg = loc_cfg.get("bd_negative") or loc_cfg.get("india_negative") or []
    tz_good_list = loc_cfg.get("timezone_compatible") or []
    tz_bad_list = loc_cfg.get("timezone_incompatible") or []

    full_text = f"{location} {description}".lower()
    loc_lower = location.lower()

    positive_hits = [kw for kw in bd_pos if kw in full_text]
    negative_hits = [kw for kw in bd_neg if kw in full_text]
    tz_good = [kw for kw in tz_good_list if kw in full_text]
    tz_bad = [kw for kw in tz_bad_list if kw in full_text]

    if negative_hits:
        return {
            "result": "no",
            "note": f"Restricted: {', '.join(negative_hits[:3])}",
        }
    if tz_bad:
        return {
            "result": "no",
            "note": f"Timezone mismatch: {', '.join(tz_bad[:2])}",
        }

    bd_direct = any(kw in full_text for kw in [
        "bangladesh", "dhaka", "chittagong", "chattogram", "sylhet",
        "rajshahi", "khulna", "barishal", "rangpur", "comilla", "cumilla",
        "remote - bangladesh",
    ])
    if bd_direct:
        return {
            "result": "yes",
            "note": f"Location mentioned: {', '.join(positive_hits[:3])}",
        }

    global_signals = any(kw in full_text for kw in [
        "worldwide", "anywhere", "global", "work from anywhere",
        "location independent", "globally distributed",
    ])
    if global_signals:
        note_parts = [h for h in positive_hits if h in [
            "worldwide", "anywhere", "global", "work from anywhere",
            "location independent", "globally distributed",
        ]]
        return {
            "result": "yes",
            "note": f"Global remote: {', '.join(note_parts[:3])}",
        }

    if any(kw in full_text for kw in ["apac", "asia", "asia pacific", "asia-pacific"]):
        return {
            "result": "yes",
            "note": f"APAC region: {', '.join(positive_hits[:3])}",
        }
    if tz_good:
        return {
            "result": "maybe",
            "note": f"Compatible timezone: {', '.join(tz_good[:2])}",
        }

    if "remote" in loc_lower and not any(
        region in loc_lower for region in [
            "us", "usa", "uk", "europe", "eu", "canada",
            "germany", "france", "spain", "australia",
        ]
    ):
        return {
            "result": "maybe",
            "note": "Remote — no region specified, may accept Bangladesh",
        }

    non_bd_regions = [
        "united states", "usa", "us", "canada", "uk",
        "united kingdom", "europe", "eu", "germany",
        "france", "australia", "spain", "netherlands",
    ]
    if any(r in loc_lower for r in non_bd_regions):
        return {
            "result": "no",
            "note": f"Location restricted to: {location}",
        }

    return {
        "result": "maybe",
        "note": "No clear location restriction found",
    }


def score_job(title: str, description: str, location: str = "",
              profile: dict = None) -> dict:
    """Score a job 0-100 against the active (or passed) profile with exact word-boundary matching."""
    profile = profile or get_active_profile()
    search = profile["search"]
    scoring = profile["scoring"]
    weights = scoring.get("weights") or {}
    w_title = int(weights.get("title", 35))
    w_tech = int(weights.get("tech", 35))
    w_exp = int(weights.get("experience", 15))
    w_signal = int(weights.get("signal", 15))

    pos_titles = search.get("title_keywords_positive") or []
    neg_titles = search.get("title_keywords_negative") or []
    core_tech_list = [t.lower() for t in (scoring.get("core_tech") or [])]
    signal_list = scoring.get("backend_signals") or []
    exp_bonuses = scoring.get("experience_bonuses") or {}
    exp_target = scoring.get("experience_target", "mid")

    score = 0
    reasons: list[str] = []
    red_flags: list[str] = []
    full_text = f"{title} {description}".lower()
    title_lower = title.lower()

    # Title relevance matching with word boundaries
    title_matches = []
    for kw in pos_titles:
        kw_clean = kw.strip().lower()
        if kw_clean and re.search(r'\b' + re.escape(kw_clean) + r'\b', title_lower):
            title_matches.append(kw)

    if title_matches:
        pts = min(len(title_matches) * 12, w_title)
        score += pts
        reasons.append(f"Title match: {', '.join(title_matches[:6])}")

    title_negatives = []
    for kw in neg_titles:
        kw_clean = kw.strip().lower()
        if kw_clean and re.search(r'\b' + re.escape(kw_clean) + r'\b', title_lower):
            title_negatives.append(kw)

    if title_negatives:
        penalty = len(title_negatives) * 15
        score -= penalty
        red_flags.append(f"Title contains: {', '.join(title_negatives[:4])}")

    # Tech stack: regex word boundaries
    tech_found = extract_tech_stack(full_text, profile=profile)
    core_tech = [t for t in tech_found if t.lower() in core_tech_list]
    secondary_tech = [t for t in tech_found if t.lower() not in core_tech_list]

    core_budget = max(0, int(round(w_tech * 0.71)))
    secondary_budget = max(0, w_tech - core_budget)

    if core_tech:
        score += min(len(core_tech) * 12, core_budget)
        reasons.append(f"Core tech: {', '.join(core_tech)}")
    if secondary_tech:
        score += min(len(secondary_tech) * 3, secondary_budget)
        reasons.append(f"Related tech: {', '.join(secondary_tech[:8])}")

    # Experience lookup
    exp_level = estimate_experience_level(full_text)
    row = exp_bonuses.get(exp_target) or {}
    raw_bonus = int(row.get(exp_level, 0))
    scaled_bonus = int(round(raw_bonus * (w_exp / 15.0)))
    if scaled_bonus > 0:
        score += scaled_bonus
        reasons.append(f"Experience match: {exp_level} (target={exp_target}) +{scaled_bonus}")
    elif scaled_bonus < 0:
        score += scaled_bonus
        red_flags.append(f"Experience mismatch: {exp_level} (target={exp_target}) {scaled_bonus}")
    else:
        reasons.append(f"Experience: {exp_level} (target={exp_target})")

    # Domain signals with word boundaries
    signal_matches = []
    for s in signal_list:
        s_clean = s.strip().lower()
        if s_clean and re.search(r'\b' + re.escape(s_clean) + r'\b', full_text):
            signal_matches.append(s)

    if signal_matches:
        score += min(len(signal_matches) * 4, w_signal)
        reasons.append(f"Signals: {', '.join(signal_matches[:5])}")

    # Bangladesh-friendly
    bd_check = check_bd_friendly(location, description, profile=profile)

    score = max(0, min(100, score))

    return {
        "score": score,
        "tech_stack": tech_found,
        "experience_level": exp_level,
        "reasons": reasons,
        "red_flags": red_flags,
        "india_friendly": bd_check["result"],  # column name kept for DB compat
        "bd_friendly": bd_check["result"],
        "location_note": bd_check["note"],
    }
