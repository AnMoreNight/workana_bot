"""
SQLite database manager for Workana job scraping
"""
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Set
import json
from pathlib import Path
from config.settings import MAX_JOBS_IN_DB


class WorkanaDatabase:
    """SQLite database manager for Workana job scraping"""
    
    def __init__(self, db_path: str = 'workana_jobs.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Access columns by name
        self.create_tables()
    
    def create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.conn.cursor()
        
        # Jobs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                url TEXT NOT NULL,
                posted_date_relative TEXT,
                posted_date_timestamp DATETIME,
                bids_count INTEGER,
                budget TEXT,
                budget_min REAL,
                budget_max REAL,
                budget_type TEXT,
                skills TEXT,
                client_name TEXT,
                client_country TEXT,
                client_rating REAL,
                client_payment_verified BOOLEAN DEFAULT 0,
                client_last_reply TEXT,
                is_featured BOOLEAN DEFAULT 0,
                is_max_project BOOLEAN DEFAULT 0,
                scraped_at DATETIME NOT NULL,
                first_seen_at DATETIME NOT NULL,
                last_seen_at DATETIME NOT NULL,
                sent_to_slack BOOLEAN DEFAULT 0,
                slack_sent_at DATETIME,
                exported_to_sheets BOOLEAN DEFAULT 0,
                sheets_exported_at DATETIME
            )
        ''')
        
        # Add sent_to_slack column to existing databases (migration)
        try:
            cursor.execute('ALTER TABLE jobs ADD COLUMN sent_to_slack BOOLEAN DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE jobs ADD COLUMN slack_sent_at DATETIME')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Add exported_to_sheets column to existing databases (migration)
        try:
            cursor.execute('ALTER TABLE jobs ADD COLUMN exported_to_sheets BOOLEAN DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE jobs ADD COLUMN sheets_exported_at DATETIME')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Scrape history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scrape_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                jobs_found INTEGER,
                new_jobs_count INTEGER,
                pages_scraped INTEGER,
                duration_seconds REAL,
                category TEXT,
                language TEXT
            )
        ''')
        
        # Create indexes
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_posted_timestamp ON jobs(posted_date_timestamp)',
            'CREATE INDEX IF NOT EXISTS idx_scraped_at ON jobs(scraped_at)',
            'CREATE INDEX IF NOT EXISTS idx_first_seen ON jobs(first_seen_at)',
            'CREATE INDEX IF NOT EXISTS idx_last_seen ON jobs(last_seen_at)',
            'CREATE INDEX IF NOT EXISTS idx_client_country ON jobs(client_country)',
            'CREATE INDEX IF NOT EXISTS idx_budget_type ON jobs(budget_type)',
            'CREATE INDEX IF NOT EXISTS idx_is_featured ON jobs(is_featured)',
            'CREATE INDEX IF NOT EXISTS idx_sent_to_slack ON jobs(sent_to_slack)',
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        self.conn.commit()
    
    def job_exists(self, job_id: str) -> bool:
        """Check if a job ID exists in database"""
        cursor = self.conn.execute(
            'SELECT id FROM jobs WHERE id = ?', (job_id,)
        )
        return cursor.fetchone() is not None
    
    def get_existing_job_ids(self) -> Set[str]:
        """
        Get all existing job identifiers as a set for fast lookup.
        
        We use a composite key of (id + client_name) when comparing jobs during
        scraping, so that two jobs are only considered the "same" if both their
        Workana ID and client name match.
        """
        cursor = self.conn.execute('SELECT id, client_name FROM jobs')
        keys: Set[str] = set()
        for row in cursor.fetchall():
            job_id = row['id'] if isinstance(row, sqlite3.Row) else row[0]
            client_name = row['client_name'] if isinstance(row, sqlite3.Row) else row[1]
            key = f"{job_id}|{client_name or ''}"
            keys.add(key)
        return keys
    
    def save_job(self, job_data: Dict) -> bool:
        """
        Save or update a job.
        Returns True if job is new, False if it already existed.
        
        If adding a new job would exceed MAX_JOBS_IN_DB, the oldest job
        (by scraped_at) is removed first to maintain the limit.
        """
        now = datetime.now()
        is_new = not self.job_exists(job_data['id'])
        
        # Prepare skills as JSON string
        skills_json = None
        if job_data.get('skills'):
            skills_json = json.dumps(job_data['skills']) if isinstance(job_data['skills'], list) else job_data['skills']
        
        if is_new:
            # Check if we need to remove oldest job to maintain limit
            cursor = self.conn.execute('SELECT COUNT(*) FROM jobs')
            current_count = cursor.fetchone()[0]
            
            if current_count >= MAX_JOBS_IN_DB:
                # Remove the oldest job (by scraped_at)
                cursor = self.conn.execute('''
                    SELECT id FROM jobs 
                    ORDER BY scraped_at ASC 
                    LIMIT 1
                ''')
                oldest_job = cursor.fetchone()
                if oldest_job:
                    oldest_job_id = oldest_job[0]
                    self.conn.execute('DELETE FROM jobs WHERE id = ?', (oldest_job_id,))
                    print(f"🗑️  Removed oldest job (ID: {oldest_job_id}) to maintain database limit of {MAX_JOBS_IN_DB}")
            
            # Insert new job
            self.conn.execute('''
                INSERT INTO jobs (
                    id, title, description, url, posted_date_relative,
                    posted_date_timestamp, bids_count, budget, budget_min,
                    budget_max, budget_type, skills, client_name,
                    client_country, client_rating, client_payment_verified,
                    client_last_reply, is_featured, is_max_project,
                    scraped_at, first_seen_at, last_seen_at,
                    sent_to_slack, slack_sent_at,
                    exported_to_sheets, sheets_exported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job_data.get('id'),
                job_data.get('title'),
                job_data.get('description'),
                job_data.get('url'),
                job_data.get('posted_date_relative'),
                job_data.get('posted_date_timestamp'),
                job_data.get('bids_count'),
                job_data.get('budget'),
                job_data.get('budget_min'),
                job_data.get('budget_max'),
                job_data.get('budget_type'),
                skills_json,
                job_data.get('client_name'),
                job_data.get('client_country'),
                job_data.get('client_rating'),
                job_data.get('client_payment_verified', False),
                job_data.get('client_last_reply'),
                job_data.get('is_featured', False),
                job_data.get('is_max_project', False),
                now,
                now,
                now,
                0,  # sent_to_slack = False for new jobs
                None,  # slack_sent_at = None
                0,  # exported_to_sheets = False for new jobs
                None  # sheets_exported_at = None
            ))
        else:
            # Update existing job
            self.conn.execute('''
                UPDATE jobs SET
                    title = ?,
                    description = ?,
                    bids_count = ?,
                    budget = ?,
                    budget_min = ?,
                    budget_max = ?,
                    budget_type = ?,
                    skills = ?,
                    client_rating = ?,
                    client_payment_verified = ?,
                    client_last_reply = ?,
                    scraped_at = ?,
                    last_seen_at = ?
                WHERE id = ?
            ''', (
                job_data.get('title'),
                job_data.get('description'),
                job_data.get('bids_count'),
                job_data.get('budget'),
                job_data.get('budget_min'),
                job_data.get('budget_max'),
                job_data.get('budget_type'),
                skills_json,
                job_data.get('client_rating'),
                job_data.get('client_payment_verified', False),
                job_data.get('client_last_reply'),
                now,
                now,
                job_data.get('id')
            ))
        
        self.conn.commit()
        return is_new
    
    def mark_job_sent_to_slack(self, job_id: str) -> bool:
        """
        Mark a job as sent to Slack to prevent duplicate notifications.
        Returns True if job was successfully marked, False if job doesn't exist.
        """
        now = datetime.now()
        cursor = self.conn.execute('''
            UPDATE jobs 
            SET sent_to_slack = 1, slack_sent_at = ?
            WHERE id = ? AND sent_to_slack = 0
        ''', (now, job_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def is_job_sent_to_slack(self, job_id: str) -> bool:
        """
        Check if a job has already been sent to Slack.
        Returns True if sent, False otherwise.
        """
        cursor = self.conn.execute(
            'SELECT sent_to_slack FROM jobs WHERE id = ?', (job_id,)
        )
        row = cursor.fetchone()
        if row:
            return bool(row[0])
        return False
    
    def mark_job_exported_to_sheets(self, job_id: str) -> bool:
        """
        Mark a job as exported to Google Sheets to prevent duplicate exports.
        Returns True if job was successfully marked, False if job doesn't exist.
        """
        now = datetime.now()
        cursor = self.conn.execute('''
            UPDATE jobs 
            SET exported_to_sheets = 1, sheets_exported_at = ?
            WHERE id = ? AND exported_to_sheets = 0
        ''', (now, job_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def is_job_exported_to_sheets(self, job_id: str) -> bool:
        """
        Check if a job has already been exported to Google Sheets.
        Returns True if exported, False otherwise.
        """
        cursor = self.conn.execute(
            'SELECT exported_to_sheets FROM jobs WHERE id = ?', (job_id,)
        )
        row = cursor.fetchone()
        if row:
            return bool(row[0])
        return False
    
    def get_jobs_for_today(self) -> List[Dict]:
        """
        Get all jobs that were first seen today (for daily sheet export).
        Returns list of job dictionaries.
        """
        cursor = self.conn.execute('''
            SELECT * FROM jobs 
            WHERE DATE(first_seen_at) = DATE('now')
            ORDER BY first_seen_at DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]
    
    def get_unsent_jobs(self) -> List[Dict]:
        """
        Get all jobs that haven't been sent to Slack yet.
        Useful for recovery or manual sending.
        """
        cursor = self.conn.execute('''
            SELECT * FROM jobs 
            WHERE sent_to_slack = 0 
            ORDER BY first_seen_at DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]
    
    def get_new_jobs_since(self, since_datetime: datetime) -> List[Dict]:
        """Get all jobs first seen after a specific datetime"""
        cursor = self.conn.execute(
            'SELECT * FROM jobs WHERE first_seen_at > ? ORDER BY first_seen_at DESC',
            (since_datetime,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_jobs_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get jobs posted within a date range"""
        cursor = self.conn.execute(
            '''SELECT * FROM jobs 
               WHERE posted_date_timestamp BETWEEN ? AND ?
               ORDER BY posted_date_timestamp DESC''',
            (start_date, end_date)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def save_scrape_history(self, jobs_found: int, new_jobs_count: int, 
                           pages_scraped: int, duration_seconds: float,
                           category: str = None, language: str = None):
        """Record scraping session statistics"""
        self.conn.execute('''
            INSERT INTO scrape_history 
            (timestamp, jobs_found, new_jobs_count, pages_scraped, duration_seconds, category, language)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now(), jobs_found, new_jobs_count, pages_scraped, duration_seconds, category, language))
        self.conn.commit()
    
    def get_last_scrape_time(self) -> Optional[datetime]:
        """Get timestamp of last scrape"""
        cursor = self.conn.execute(
            'SELECT timestamp FROM scrape_history ORDER BY timestamp DESC LIMIT 1'
        )
        row = cursor.fetchone()
        if row:
            timestamp_str = row[0]
            if isinstance(timestamp_str, str):
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return timestamp_str
        return None
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        stats = {}
        
        # Total jobs
        cursor = self.conn.execute('SELECT COUNT(*) FROM jobs')
        stats['total_jobs'] = cursor.fetchone()[0]
        
        # Jobs from last 24 hours
        cursor = self.conn.execute('''
            SELECT COUNT(*) FROM jobs 
            WHERE first_seen_at > datetime('now', '-24 hours')
        ''')
        stats['new_jobs_24h'] = cursor.fetchone()[0]
        
        # Total scrape sessions
        cursor = self.conn.execute('SELECT COUNT(*) FROM scrape_history')
        stats['total_scrapes'] = cursor.fetchone()[0]
        
        return stats
    
    def close(self):
        """Close database connection"""
        self.conn.close()

