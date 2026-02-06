"""
Configuration settings for Workana scraper
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Load environment variables from .env file
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try to load from default location
    load_dotenv()

# Database settings
DATABASE_PATH = BASE_DIR / 'workana_jobs.db'
MAX_JOBS_IN_DB = 500  # Maximum number of jobs to keep in database (oldest jobs are removed when limit is reached)

# Scraping settings
BASE_URL = "https://www.workana.com"
JOBS_URL = f"{BASE_URL}/jobs"
DEFAULT_CATEGORY = "it-programming"
DEFAULT_LANGUAGE = "en,pt,es"  # English, Portuguese, Spanish

# Playwright settings
HEADLESS = True  # Set to False for debugging
PAGE_LOAD_TIMEOUT = 20000  # milliseconds (20 seconds)
EXPLICIT_WAIT_TIMEOUT = 5000  # milliseconds (5 seconds)

# Rate limiting (optimized for speed while still being respectful)
DELAY_BETWEEN_REQUESTS = 1  # seconds (reduced from 3)
RANDOM_DELAY_RANGE = (0.5, 2)  # Random delay range in seconds (reduced from 2-5)

# Scraping limits
MAX_PAGES = 1  # Maximum pages to scrape (None = no limit)
STOP_ON_KNOWN_JOB = False  # Stop scraping when encountering known job ID (False = continue scraping)

# Scheduler settings
SCRAPE_INTERVAL = 30  # Seconds between scrapes (set to None to run once and exit)

# User agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Browser settings
BROWSER = "chromium"  # Options: "chromium", "firefox", "webkit"

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = BASE_DIR / 'scraper.log'

# Slack notifications
# Load from .env file, environment variable, or leave empty
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '').strip()
ENABLE_SLACK_NOTIFICATIONS = bool(SLACK_WEBHOOK_URL)  # Auto-enable if webhook URL is set

# Google Sheets export
# Load from .env file, environment variable, or leave empty
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID', '1cwP7M2acOs6kohi6KZY__nnT7ys_-DW4iNun_-XBVcY').strip()
# Google service account credentials as JSON string (paste entire JSON content from service account key as single line in .env)
# Example: GOOGLE_SHEETS_CREDENTIALS_JSON={"type":"service_account","project_id":"...","private_key":"..."}
GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv('GOOGLE_SHEETS_CREDENTIALS_JSON', '').strip()
ENABLE_SHEETS_EXPORT = bool(GOOGLE_SHEETS_CREDENTIALS_JSON)  # Auto-enable if credentials JSON is set

