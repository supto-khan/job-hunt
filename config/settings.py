import os
from dotenv import load_dotenv

load_dotenv()

# Database Settings (MySQL / MariaDB)
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "job_hunter")

# API Keys (optional for test version)
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")

# Notifications (Discord & Telegram)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
NOTIFY_MIN_SCORE = int(os.getenv("NOTIFY_MIN_SCORE", "80"))

# Email Settings (Gmail SMTP)
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_APP_PASSWORD = os.getenv("SENDER_APP_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "parmanandprajapati0009@gmail.com")

# Daily digest scheduler
DAILY_EMAIL_HOUR = int(os.getenv("DAILY_EMAIL_HOUR", "10"))   # 24-hour format (10 = 10:00 AM)
DAILY_EMAIL_TIMEZONE = os.getenv("DAILY_EMAIL_TIMEZONE", "Asia/Dhaka")  # BST / Bangladesh Standard Time
DAILY_JOBS_COUNT = int(os.getenv("DAILY_JOBS_COUNT", "15"))  # how many jobs in email

# Google Sheets
GOOGLE_SHEETS_CREDS = os.getenv("GOOGLE_SHEETS_CREDS", "credentials.json")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

# Search criteria defaults
DEFAULT_SEARCH_TERMS = [
    "backend developer python",
    "python django developer",
    "fastapi developer",
    "backend engineer python",
    "python developer",
]

RELEVANT_TECH = [
    "python", "django", "fastapi", "flask", "celery", "redis",
    "postgresql", "postgres", "mysql", "mongodb", "docker",
    "kubernetes", "aws", "gcp", "rest", "graphql", "node",
    "nodejs", "express", "sql", "nosql", "microservices",
    "rabbitmq", "kafka", "elasticsearch",
]

TITLE_KEYWORDS_POSITIVE = [
    "backend", "back-end", "back end", "python", "django",
    "fastapi", "software engineer", "software developer",
    "full stack", "fullstack", "full-stack", "api developer",
]

TITLE_KEYWORDS_NEGATIVE = [
    "frontend", "front-end", "front end", "ios", "android",
    "mobile", "devops", "data scientist", "machine learning",
    "ml engineer", "ui/ux", "designer", "qa", "test",
    "intern", "internship", "trainee", "junior",
]

# ── Location / Bangladesh Remote Filtering ──

# Keywords that CONFIRM Bangladesh/Asia people can apply
LOCATION_BD_POSITIVE = [
    "bangladesh", "dhaka", "chittagong", "chattogram", "sylhet",
    "rajshahi", "khulna", "barishal", "rangpur", "comilla", "cumilla",
    "remote - bangladesh", "bst", "bangladesh standard time",
    "asia", "worldwide", "global", "anywhere",
    "apac", "asia pacific", "asia-pacific",
    "remote - global", "remote global", "globally distributed",
    "work from anywhere", "location independent",
    "south asia", "southeast asia", "emea/apac",
]

# Keywords that BLOCK Bangladesh — these mean US/EU only
LOCATION_BD_NEGATIVE = [
    "us only", "usa only", "us-only", "united states only",
    "must be located in the us", "must reside in the us",
    "us-based", "us based", "u.s. only", "u.s. based",
    "canada only", "uk only", "eu only", "europe only",
    "european union only", "uk-based", "eu-based",
    "must be authorized to work in the united states",
    "no visa sponsorship", "us citizen", "us work authorization",
    "est/cst/pst", "americas only", "americas timezone",
    "north america only", "na only", "latam only",
]

# Timezone overlap hints — Bangladesh (BST = UTC+6)
# These timezones have reasonable overlap with BST
TIMEZONE_COMPATIBLE = [
    "bst", "ist", "gmt", "utc", "cet", "eet", "ast",
    "flexible", "async", "asynchronous",
    "overlap", "any timezone", "all timezones",
]

TIMEZONE_INCOMPATIBLE = [
    "pst only", "est only", "cst only", "mst only",
    "pacific time only", "eastern time only",
    "us timezone required", "us hours required",
    "core hours pst", "core hours est",
]

# Minimum relevance score to show in polished results
MIN_RELEVANCE_SCORE = 50

# Server
HOST = "127.0.0.1"
PORT = 8000
