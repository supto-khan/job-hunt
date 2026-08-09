"""Target ATS Companies Configuration for Greenhouse, Lever, Ashby, Workable, and SmartRecruiters.
Provides default company fallback tokens and slugs for scrapers.
"""

# List of Greenhouse board tokens (e.g., boards.greenhouse.io/{token})
GREENHOUSE_COMPANIES = [
    {"name": "Stripe", "token": "stripe", "domain": "stripe.com"},
    {"name": "GitLab", "token": "gitlab", "domain": "gitlab.com"},
    {"name": "Canonical", "token": "canonical", "domain": "canonical.com"},
    {"name": "Figma", "token": "figma", "domain": "figma.com"},
    {"name": "Pinterest", "token": "pinterest", "domain": "pinterest.com"},
    {"name": "Discord", "token": "discord", "domain": "discord.com"},
    {"name": "Reddit", "token": "reddit", "domain": "reddit.com"},
    {"name": "Vercel", "token": "vercel", "domain": "vercel.com"},
    # Mid-tier / Fast-growing Tech
    {"name": "Sentry", "token": "sentry", "domain": "sentry.io"},
    {"name": "LaunchDarkly", "token": "launchdarkly", "domain": "launchdarkly.com"},
    {"name": "Brex", "token": "brex", "domain": "brex.com"},
    {"name": "Plaid", "token": "plaid", "domain": "plaid.com"},
    {"name": "Sourcegraph", "token": "sourcegraph", "domain": "sourcegraph.com"},
    {"name": "Cockroach Labs", "token": "cockroachlabs", "domain": "cockroachlabs.com"},
    {"name": "CircleCI", "token": "circleci", "domain": "circleci.com"},
    {"name": "Algolia", "token": "algolia", "domain": "algolia.com"},
    {"name": "Snyk", "token": "snyk", "domain": "snyk.io"},
    {"name": "Tailscale", "token": "tailscale", "domain": "tailscale.com"},
    {"name": "Checkly", "token": "checkly", "domain": "checklyhq.com"},
    {"name": "PlanetScale", "token": "planetscale", "domain": "planetscale.com"},
]

# List of Lever site slugs (e.g., jobs.lever.co/{slug})
LEVER_COMPANIES = [
    {"name": "Spotify", "slug": "spotify", "domain": "spotify.com"},
    {"name": "Palantir", "slug": "palantir", "domain": "palantir.com"},
    {"name": "Retool", "slug": "retool", "domain": "retool.com"},
    # Mid-tier / Remote-first Tech
    {"name": "Hotjar", "slug": "hotjar", "domain": "hotjar.com"},
    {"name": "1Password", "slug": "1password", "domain": "1password.com"},
    {"name": "Kinsta", "slug": "kinsta", "domain": "kinsta.com"},
    {"name": "Automattic", "slug": "automattic", "domain": "automattic.com"},
    {"name": "Toptal", "slug": "toptal", "domain": "toptal.com"},
    {"name": "LottieFiles", "slug": "lottiefiles", "domain": "lottiefiles.com"},
    {"name": "Framer Motion", "slug": "framermotion", "domain": "framer.com"},
    {"name": "Coursera", "slug": "coursera", "domain": "coursera.org"},
    {"name": "Duolingo", "slug": "duolingo", "domain": "duolingo.com"},
    {"name": "Eventbrite", "slug": "eventbrite", "domain": "eventbrite.com"},
]

# List of Ashby board slugs (e.g., jobs.ashbyhq.com/{slug})
ASHBY_COMPANIES = [
    {"name": "Linear", "slug": "linear", "domain": "linear.app"},
    {"name": "Notion", "slug": "notion", "domain": "notion.so"},
    {"name": "Vanta", "slug": "vanta", "domain": "vanta.com"},
    # Mid-tier / Startups (10-100 employees)
    {"name": "Ramp", "slug": "ramp", "domain": "ramp.com"},
    {"name": "Resend", "slug": "resend", "domain": "resend.com"},
    {"name": "Raycast", "slug": "raycast", "domain": "raycast.com"},
    {"name": "Replit", "slug": "replit", "domain": "replit.com"},
    {"name": "Pinecone", "slug": "pinecone", "domain": "pinecone.io"},
    {"name": "Together AI", "slug": "togetherai", "domain": "together.ai"},
    {"name": "Mistral AI", "slug": "mistralai", "domain": "mistral.ai"},
    {"name": "Modal", "slug": "modal", "domain": "modal.com"},
    {"name": "Baseten", "slug": "baseten", "domain": "baseten.co"},
    {"name": "Runway", "slug": "runway", "domain": "runwayml.com"},
    {"name": "Cursor", "slug": "cursor", "domain": "cursor.com"},
    {"name": "Superhuman", "slug": "superhuman", "domain": "superhuman.com"},
    {"name": "LangChain", "slug": "langchain", "domain": "langchain.com"},
    {"name": "LlamaIndex", "slug": "llamaindex", "domain": "llamaindex.ai"},
    {"name": "Groq", "slug": "groq", "domain": "groq.com"},
]

# List of Workable account slugs
WORKABLE_COMPANIES = [
    {"name": "Basecamp", "slug": "basecamp", "domain": "basecamp.com"},
    {"name": "Printify", "slug": "printify", "domain": "printify.com"},
    {"name": "N26", "slug": "n26", "domain": "n26.com"},
    {"name": "Klarna", "slug": "klarna", "domain": "klarna.com"},
    {"name": "Jooble", "slug": "jooble", "domain": "jooble.org"},
    {"name": "GetYourGuide", "slug": "getyourguide", "domain": "getyourguide.com"},
    {"name": "Personio", "slug": "personio", "domain": "personio.com"},
    {"name": "Pitch", "slug": "pitch", "domain": "pitch.com"},
    {"name": "Typeform", "slug": "typeform", "domain": "typeform.com"},
    {"name": "Front", "slug": "front", "domain": "front.com"},
    {"name": "G2", "slug": "g2", "domain": "g2.com"},
    {"name": "WeWork", "slug": "wework", "domain": "wework.com"},
]

# List of SmartRecruiters company slugs
SMARTRECRUITERS_COMPANIES = [
    {"name": "Square", "slug": "square", "domain": "squareup.com"},
    {"name": "Canva", "slug": "canva", "domain": "canva.com"},
    {"name": "Revolut", "slug": "revolut", "domain": "revolut.com"},
    {"name": "Ubisoft", "slug": "ubisoft", "domain": "ubisoft.com"},
    {"name": "Roblox", "slug": "roblox", "domain": "roblox.com"},
    {"name": "Atlassian", "slug": "atlassian", "domain": "atlassian.com"},
    {"name": "Visa", "slug": "visa", "domain": "visa.com"},
    {"name": "PayPal", "slug": "paypal", "domain": "paypal.com"},
    {"name": "eBay", "slug": "ebay", "domain": "ebay.com"},
    {"name": "Booking.com", "slug": "booking", "domain": "booking.com"},
    {"name": "Zalando", "slug": "zalando", "domain": "zalando.com"},
    {"name": "HelloFresh", "slug": "hellofresh", "domain": "hellofresh.com"},
    {"name": "Deliveroo", "slug": "deliveroo", "domain": "deliveroo.com"},
]
