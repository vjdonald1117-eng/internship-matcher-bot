# Multi-Platform Internship Scraping & Semantic Matching Bot

A local, $0-cost Python automation pipeline that scrapes internship listings from **Handshake**, **LinkedIn**, and **Indeed**, evaluates their semantic similarity against your PDF resume using `sentence-transformers/all-MiniLM-L6-v2`, deduplicates state in SQLite (`jobs.db`), and dispatches high-match alerts to a **Discord Webhook**.

## Architecture Highlights
- **Unified Schema (`src/models.py`)**: Strict Pydantic v2 validation and URL canonicalization paired with SQLAlchemy 2.0 ORM.
- **Handshake Session Persistence (`src/scrapers/handshake.py`)**: Launches a visible Chromium window on first run so you can complete University SSO and Duo 2FA, then saves encrypted cookies/localStorage to `auth/handshake_state.json` for headless future runs.
- **Anti-Bot Evasion (`src/scrapers/linkedin.py` & `indeed.py`)**: Combines LinkedIn's unauthenticated Guest Job API with `playwright-stealth` v2.x, custom `navigator.webdriver` JS init patches, and randomized human delays.
- **Sliding-Window Semantic Matcher (`src/matcher.py`)**: Overcomes the 256-token truncation limit of `all-MiniLM-L6-v2` by chunking long resumes and job descriptions with overlapping windows and mean-pooling normalized embeddings.

## Prerequisites
- **Python 3.10+**
- **Visual Studio Code**
- A **Discord Webhook URL** (Server Settings -> Integrations -> Webhooks -> New Webhook)

## Quickstart & Execution Steps

### 1. Environment Initialization
```bash
python -m venv .venv
# Activate on Windows:
.venv\Scripts\activate
# Activate on macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium