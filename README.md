# 🎯 Job Hunter — AI-Powered Job Scraper & Cold Outreach Platform

<p align="center">
  <img src="static/favicon.svg" alt="Job Hunter Logo" width="80" height="80">
</p>

An automated job discovery, relevance scoring, and cold outreach platform built for software engineers and technical recruiters. Finds fresh jobs daily across multiple aggregators and career pages, scores them against a **configurable candidate profile**, generates personalized LinkedIn/email cold outreach templates, and visualizes analytics in a modern dashboard.

---

## ✨ Features & Architecture Highlights

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                            JOB HUNTER ENGINE                            │
 └─────────────────────────────────────────────────────────────────────────┘
        │                                 │                               │
        ▼                                 ▼                               ▼
 ┌──────────────┐                 ┌──────────────┐                ┌──────────────┐
 │ Job Scraping │                 │ Profile Engine│                │ UI Analytics │
 └──────────────┘                 └──────────────┘                └──────────────┘
   • FreeHire (124+ ATSs)           • Custom Scoring Weights        • Forest Green Theme
   • Remotive & RemoteOK            • BD/India Remote Classifier    • Chart.js Visuals
   • 150+ ATS Crawlers              • Automated LinkedIn Outreach   • Lexend Typography
   • Greenhouse / Lever / Ashby     • Persona Switcher (YAML)       • Alpine.js Controls
```

- 🎨 **Modern SaaS UI**: Styled with **Brand Emerald & Mint** palette (`#00A878`, `#00C896`, `#5EEAD4`, `#F0FDF9`), Google Font **Lexend**, **Tailwind CSS**, and **Alpine.js**.
- 📊 **Interactive Analytics Dashboard**: Live **Chart.js** visualizations for *Jobs Scraped by Source*, *Top Tech Stacks Found*, and *Outreach Conversion Funnel*.
- ⚡ **24/7 Automated Remote Job Hunter**: Continuously scans every 2 hours across all 3 candidate CV profiles strictly for remote positions worldwide with instant alert triggers.
- 🎯 **Multi-CV Candidate Profiles**: Built from real candidate resumes:
  1. **Supto — Senior Angular Developer (5+ YOE)** (LMS, TypeScript, RxJS, Ionic hybrid mobile)
  2. **Supto — Senior Full-Stack Developer (5+ YOE)** (Angular, React, Node.js, Laravel/PHP, GenAI)
  3. **Supto — Frontend Developer (5+ YOE)** (React, Next.js, Angular, TypeScript, Tailwind, UI Architecture)
- 🗄️ **MySQL Database**: Production-grade persistence with full support for profile tagging and outreach history.
- 📬 **Scheduled Email Digest**: Daily morning digests delivered straight to your inbox via Gmail SMTP.

---

## 🎨 Design System & Palette

- **Background:** `--color-brand-bg: #F0FDF9`
- **Surface:** `--color-brand-surface: #FFFFFF`
- **Primary:** `--color-brand-primary: #00A878`
- **CTA:** `--color-brand-cta: #00C896`
- **Accent:** `--color-brand-accent: #5EEAD4`
- **Muted:** `--color-brand-muted: #64748B`
- **Dark:** `--color-brand-dark: #0F1F17`
- **Typography:** Google Font **[Lexend](https://fonts.google.com/specimen/Lexend)**

---

## 🚀 Quick Start

### 1. Prerequisites & Installation

Ensure you have **Python 3.10+** installed.

```bash
# Clone repository
git clone https://github.com/supto-khan/job-hunt.git
cd job-hunter

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration (`.env`)

Copy the example environment file:

```bash
cp .env.example .env
```

Update your `.env` settings:

```bash
# ─── Database Configuration (MySQL or SQLite) ───
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=job_hunter

# ─── Required for JSearch (Aggregator API) ───
RAPIDAPI_KEY=your_rapidapi_key_here

# ─── Required for Daily Email Digest (Gmail SMTP) ───
SENDER_EMAIL=your-gmail@gmail.com
SENDER_APP_PASSWORD=your_gmail_app_password
RECIPIENT_EMAIL=candidate@gmail.com

# ─── Daily Digest Timing ───
DAILY_EMAIL_HOUR=10                 # 10:00 AM
DAILY_EMAIL_TIMEZONE=Asia/Dhaka     # BST (UTC+6)
DAILY_JOBS_COUNT=15                 # Jobs per email digest
```

### 3. Database Migration (Optional for MySQL)

If you are running MySQL and want to migrate existing SQLite data:

```bash
python scripts/migrate_sqlite_to_mysql.py
```

### 4. Launch Application Server

Start the FastAPI application server using Uvicorn:

```bash
python main.py
```

Open your browser at **`http://127.0.0.1:8000`**.

---

## 📖 Application Pages & Capabilities

### 1. Dashboard (`/`)
- **Analytics Charts**: Visual breakdown of jobs scraped per source, top tech tags, and outreach pipeline stage funnel.
- **Job Board**: Live filtering by search keyword, job status (`New`, `Reviewed`, `Applied`), Bangladesh/India remote availability, min relevance score, and source.
- **Actions**: Click **Collect Jobs** to execute scrapers or **Export to Sheets** for external automations.

### 2. Outreach (`/outreach`)
- View generated outreach contact items.
- Ready-to-send LinkedIn DMs tailored to hiring managers, tech leads, and recruiters.
- Track conversion statuses (`Pending`, `Emailed`, `Messaged`, `Replied`, `Followed Up`).

### 3. Profiles (`/profile`)
- Switch active target role profiles on the fly.
- Import YAML presets from `profiles/`:
  - `supto_angular.yaml` (CV 1: Senior Angular Developer)
  - `supto_fullstack.yaml` (CV 2: Senior Full-Stack Developer)
  - `supto_frontend.yaml` (CV 3: Frontend Developer)
- Run **Re-score All Jobs** to re-index all stored database jobs against newly updated scoring weights.

---

## 🛠 Tech Stack

- **Backend:** Python 3.12+, FastAPI, PyMySQL / SQLite3, APScheduler, Jinja2 Templates.
- **Frontend:** Tailwind CSS (CDN), Alpine.js, Chart.js, Vanilla JS, Lexend Google Font.
- **Scraper Engines:** Greenhouse, Lever, Ashby, JSearch (RapidAPI), Remotive, RemoteOK, Arbeitnow.
- **Email:** Gmail SMTP with SSL/TLS & App Passwords.

---

## 📝 License & Contributing

Built for personal and commercial job automation workflows. Feel free to submit pull requests or open issues!
