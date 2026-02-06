"""
Parser for converting relative dates to absolute timestamps
"""
import re
from datetime import datetime, timedelta
from typing import Optional


def parse_relative_date(date_text: str) -> Optional[datetime]:
    """
    Parse relative date strings like "20 hours ago", "Just now", "Yesterday"
    Returns datetime object or None if parsing fails
    """
    if not date_text:
        return None
    
    # Clean the text
    date_text = date_text.strip().lower()
    
    # Remove "Published: " prefix if present
    date_text = re.sub(r'^published:\s*', '', date_text, flags=re.IGNORECASE)
    
    now = datetime.now()
    
    # "Just now" or "now"
    if 'just now' in date_text or date_text == 'now':
        return now - timedelta(seconds=30)  # Approximate as 30 seconds ago
    
    # Minutes ago
    match = re.search(r'(\d+)\s*(?:minute|min)s?\s*ago', date_text)
    if match:
        minutes = int(match.group(1))
        return now - timedelta(minutes=minutes)
    
    # Hours ago
    match = re.search(r'(\d+)\s*(?:hour|hr)s?\s*ago', date_text)
    if match:
        hours = int(match.group(1))
        return now - timedelta(hours=hours)
    
    # "Almost an hour ago" or "Almost 1 hour ago"
    if 'almost an hour ago' in date_text or 'almost 1 hour ago' in date_text:
        return now - timedelta(hours=1, minutes=30)
    
    # Days ago
    match = re.search(r'(\d+)\s*(?:day|d)s?\s*ago', date_text)
    if match:
        days = int(match.group(1))
        return now - timedelta(days=days)
    
    # "Yesterday"
    if 'yesterday' in date_text:
        return now - timedelta(days=1, hours=12)  # Approximate as yesterday noon
    
    # Weeks ago
    match = re.search(r'(\d+)\s*(?:week|w)s?\s*ago', date_text)
    if match:
        weeks = int(match.group(1))
        return now - timedelta(weeks=weeks)
    
    # Months ago
    match = re.search(r'(\d+)\s*(?:month|mo)s?\s*ago', date_text)
    if match:
        months = int(match.group(1))
        return now - timedelta(days=months * 30)  # Approximate month as 30 days
    
    # Try to parse as absolute date if relative parsing fails
    try:
        # Try common date formats
        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%B %d, %Y']:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue
    except:
        pass
    
    # If all parsing fails, return None
    return None


def extract_job_id_from_url(url: str) -> str:
    """
    Extract unique job ID from Workana job URL
    Example: /job/desenvolvedor-expert-em-webhook... -> desenvolvedor-expert-em-webhook...
    """
    if not url:
        return ""
    
    # Remove base URL if present
    url = url.replace('https://www.workana.com', '')
    url = url.replace('http://www.workana.com', '')
    
    # Extract job slug
    match = re.search(r'/job/([^/?]+)', url)
    if match:
        return match.group(1)
    
    # If no match, return the last part of the URL
    return url.strip('/').split('/')[-1].split('?')[0]

