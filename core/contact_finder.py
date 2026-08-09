import re
import httpx
import logging
from typing import Dict, List, Optional
import os

logger = logging.getLogger(__name__)

# Regex patterns
EMAIL_REGEX = re.compile(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)')
LINKEDIN_REGEX = re.compile(r'(https:\/\/(www\.)?linkedin\.com\/in\/[a-zA-Z0-9_-]+)')


def extract_contacts_from_text(text: str) -> Dict[str, List[str]]:
    """Extract emails and LinkedIn profile URLs from raw text/HTML."""
    if not text:
        return {"emails": [], "linkedin": []}
    
    # Extract emails
    emails = list(set(re.findall(EMAIL_REGEX, text)))
    # Exclude common image extensions or dummy emails that might match regex
    emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg'))]
    emails = [e for e in emails if "example.com" not in e.lower() and "yourdomain" not in e.lower()]
    
    # Extract LinkedIn profiles
    linkedin_matches = re.findall(LINKEDIN_REGEX, text)
    # re.findall with groups returns tuples if there are capturing groups. 
    # LINKEDIN_REGEX has groups: [0] is full match
    linkedin_urls = list(set([m[0] for m in linkedin_matches]))

    return {
        "emails": emails,
        "linkedin": linkedin_urls
    }


def _get_org_slug_from_domain(domain: str) -> str:
    """Extract a likely GitHub org slug from a domain (e.g., 'stripe.com' -> 'stripe')."""
    if not domain:
        return ""
    # Remove www., https, etc if present
    domain = domain.replace("https://", "").replace("http://", "").replace("www.", "")
    return domain.split('.')[0].lower()


def extract_github_contacts(company_domain: str, token: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Search GitHub for the top repo of an org (inferred from domain),
    and extract commit author names and emails.
    """
    slug = _get_org_slug_from_domain(company_domain)
    if not slug:
        return []

    headers = {"User-Agent": "JobHunter-Contact-Extraction"}
    if token:
        headers["Authorization"] = f"token {token}"

    contacts = []
    seen_emails = set()

    with httpx.Client(timeout=10.0, headers=headers) as client:
        try:
            # 1. Fetch top recently updated public repos for the org
            repos_url = f"https://api.github.com/orgs/{slug}/repos?sort=updated&per_page=3"
            r_repos = client.get(repos_url)
            if r_repos.status_code != 200:
                logger.debug(f"GitHub Hack: Org '{slug}' not found or rate limited ({r_repos.status_code}).")
                return []

            repos = r_repos.json()
            if not repos:
                return []

            # 2. Check commits for the most active repos
            for repo in repos:
                repo_name = repo.get("name")
                if not repo_name:
                    continue

                commits_url = f"https://api.github.com/repos/{slug}/{repo_name}/commits?per_page=10"
                r_commits = client.get(commits_url)
                if r_commits.status_code == 200:
                    for commit_obj in r_commits.json():
                        author = commit_obj.get("commit", {}).get("author", {})
                        name = author.get("name", "").strip()
                        email = author.get("email", "").strip()

                        # Filter out bots and noreply emails
                        if not name or not email:
                            continue
                        if "bot" in name.lower() or "[bot]" in name.lower():
                            continue
                        if email.endswith("@users.noreply.github.com") or "noreply" in email.lower():
                            continue
                        if email in seen_emails:
                            continue

                        contacts.append({"name": name, "email": email})
                        seen_emails.add(email)

                        # We don't want a massive list, just the top 3 tech contacts is enough
                        if len(contacts) >= 3:
                            return contacts

        except Exception as e:
            logger.debug(f"GitHub Hack error for {slug}: {e}")

    return contacts
