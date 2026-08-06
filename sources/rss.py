"""RSS Feed aggregator source — 100% free, no API key required.
Aggregates RSS XML feeds from top remote tech job boards (WeWorkRemotely, RemoteOK RSS, Jobspresso).
"""

import xml.etree.ElementTree as ET
import httpx
from bs4 import BeautifulSoup
from sources.base import BaseSource
from core.models import Job


class RSSSource(BaseSource):
    name = "rss_feeds"

    RSS_FEEDS = [
        # WeWorkRemotely Feeds
        {
            "name": "weworkremotely_fullstack",
            "url": "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
        },
        {
            "name": "weworkremotely_backend",
            "url": "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
        },
        {
            "name": "weworkremotely_frontend",
            "url": "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
        },
        # Himalayas Remote Jobs Feed
        {
            "name": "himalayas_remote",
            "url": "https://himalayas.app/jobs/rss",
        },
        # LaraJobs (Laravel / PHP specialized)
        {
            "name": "larajobs",
            "url": "https://larajobs.com/feed",
        },
        # WorkingNomads Development Feed
        {
            "name": "workingnomads",
            "url": "https://www.workingnomads.com/jobs?category=development&format=rss",
        },
        # Arc.dev Remote Engineering Feed
        {
            "name": "arc_dev",
            "url": "https://arc.dev/remote-jobs/rss",
        },
        # NoDesk Remote Tech Feed
        {
            "name": "nodesk",
            "url": "https://nodesk.co/remote-jobs/index.xml",
        },
        # JS Remotely (React / Node / TS / Angular)
        {
            "name": "jsremotely",
            "url": "https://jsremotely.com/rss.xml",
        },
        # Jobspresso Tech Feed
        {
            "name": "jobspresso",
            "url": "https://jobspresso.co/category/tech/feed/",
        },
    ]

    async def fetch(self) -> list[Job]:
        all_jobs = []
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
            for feed_cfg in self.RSS_FEEDS:
                try:
                    resp = await client.get(feed_cfg["url"])
                    if resp.status_code != 200:
                        continue
                    
                    xml_text = resp.text
                    root = ET.fromstring(xml_text)
                    
                    # Channel items
                    items = root.findall(".//item")
                    for item in items:
                        title_elem = item.find("title")
                        link_elem = item.find("link")
                        desc_elem = item.find("description")
                        pub_date_elem = item.find("pubDate")
                        
                        raw_title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                        url = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                        raw_desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""
                        pub_date = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text else ""
                        
                        if not raw_title or not url:
                            continue
                            
                        # Clean HTML from description
                        clean_desc = ""
                        if raw_desc:
                            if "<" in raw_desc and ">" in raw_desc:
                                clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(separator=" ").strip()
                            else:
                                clean_desc = raw_desc.strip()
                        
                        # Parse Company and Title if title is formatted as "Company: Title" or "Title at Company"
                        company = "Remote Company"
                        title = raw_title
                        if ":" in raw_title:
                            parts = raw_title.split(":", 1)
                            company = parts[0].strip()
                            title = parts[1].strip()
                        elif " at " in raw_title:
                            parts = raw_title.split(" at ", 1)
                            title = parts[0].strip()
                            company = parts[1].strip()

                        job = Job(
                            title=title,
                            company=company,
                            location="Remote / Worldwide",
                            description=clean_desc,
                            url=url,
                            source=f"rss_{feed_cfg['name']}",
                            posted_date=pub_date,
                            job_type="Full-time",
                        )
                        all_jobs.append(job)
                except Exception:
                    continue

        return all_jobs
