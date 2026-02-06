"""
Slack notification module for sending new jobs to Slack channel
"""
import json
import re
from typing import List, Dict, Optional
from datetime import datetime
import requests
from config.settings import BASE_URL
from utils.text_summarizer import summarize_job_description
from utils.translator import DeepLTranslator

try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False


class SlackNotifier:
    """Send notifications to Slack channel via webhook"""
    
    def __init__(self, webhook_url: str, translator: Optional[DeepLTranslator] = None):
        """
        Initialize Slack notifier
        
        Args:
            webhook_url: Slack incoming webhook URL
            translator: Optional DeepL translator for translating job descriptions
        """
        self.webhook_url = webhook_url
        self.translator = translator
    
    def send_message(self, text: str, blocks: Optional[List] = None) -> bool:
        """
        Send a message to Slack
        
        Args:
            text: Fallback text
            blocks: Slack block kit blocks (optional)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            print("⚠️  Warning: Slack webhook URL not configured")
            print("   Set SLACK_WEBHOOK_URL environment variable or edit config/settings.py")
            return False
        
        if not self.webhook_url.startswith('https://hooks.slack.com'):
            print(f"⚠️  Warning: Invalid Slack webhook URL format")
            print(f"   URL should start with 'https://hooks.slack.com'")
            print(f"   Current URL: {self.webhook_url[:50]}...")
            return False
        
        payload = {
            "text": text
        }
        
        if blocks:
            payload["blocks"] = blocks
        
        try:
            print(f"📤 Sending Slack message to webhook...")
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            # Check response
            if response.status_code == 200:
                print("✅ Slack notification sent successfully!")
                return True
            else:
                print(f"❌ Slack API returned error: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            print("❌ Error: Slack request timed out")
            return False
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Error: Could not connect to Slack")
            print(f"   Check your internet connection")
            return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending Slack notification: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error sending Slack notification: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def format_job_block(self, job: Dict, index: int = None) -> Dict:
        """
        Format a single job as Slack block (simplified format)
        
        Args:
            job: Job data dictionary
            index: Optional index number
        
        Returns:
            Slack block dictionary
        """
        # Translate title if translator is available
        original_title = job.get('title', 'N/A')
        title = original_title
        if self.translator and self.translator.is_available():
            try:
                translated_title = self.translator.translate_text(original_title, target_lang="EN-US")
                if translated_title:
                    title = translated_title
            except Exception as e:
                print(f"⚠️  Warning: Failed to translate title: {e}")
        
        url = job.get('url', '')
        if url and not url.startswith('http'):
            url = BASE_URL + url
        
        # Build text with each field on a new line
        text_parts = []
        
        # Title with link (bold)
        if url:
            title_text = f"*<{url}|{title}>*"
        else:
            title_text = f"*{title}*"
        text_parts.append(title_text)
        
        # Country
        if job.get('client_country'):
            text_parts.append(f"Country: {job['client_country']}")
        
        # Payment verification
        if job.get('client_payment_verified'):
            text_parts.append("Payment: ✅ Verified")
        else:
            text_parts.append("Payment: ❌ Not Verified")
        
        # Budget
        if job.get('budget'):
            text_parts.append(f"Budget: {job['budget']}")
        
        # Join all parts with newlines
        main_text = "\n".join(text_parts)
        
        # Create main block
        block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": main_text
            }
        }
        
        return block
    
    def _get_tokyo_timestamp(self) -> str:
        """
        Get current timestamp in Asia/Tokyo timezone formatted as YYYY/MM/DD : HH:MM
        
        Returns:
            Formatted timestamp string
        """
        try:
            if PYTZ_AVAILABLE:
                tokyo_tz = pytz.timezone('Asia/Tokyo')
                now_tokyo = datetime.now(tokyo_tz)
            else:
                # Fallback: use UTC offset for JST (UTC+9)
                from datetime import timezone, timedelta
                jst = timezone(timedelta(hours=9))
                now_tokyo = datetime.now(jst)
            
            return now_tokyo.strftime('%Y/%m/%d : %H:%M')
        except Exception as e:
            # Fallback to local time if timezone conversion fails
            return datetime.now().strftime('%Y/%m/%d : %H:%M')
    
    def format_job_blocks(self, job: Dict, index: int = None) -> List[Dict]:
        """
        Format a job as Slack blocks with simplified format
        
        Args:
            job: Job data dictionary
            index: Optional index number
        
        Returns:
            List of Slack block dictionaries
        """
        blocks = []
        
        # Translate title if translator is available
        original_title = job.get('title', 'N/A')
        title = original_title
        if self.translator and self.translator.is_available():
            try:
                translated_title = self.translator.translate_text(original_title, target_lang="EN-US")
                if translated_title:
                    title = translated_title
            except Exception as e:
                print(f"⚠️  Warning: Failed to translate title: {e}")
        
        url = job.get('url', '')
        if url and not url.startswith('http'):
            url = BASE_URL + url
        
        # Build text with each field on a new line (all in one block for consistent spacing)
        text_parts = []
        
        # Title (normal text, same font size)
        text_parts.append(title)
        
        # Country
        if job.get('client_country'):
            text_parts.append(f"Country: {job['client_country']}")
        
        # Budget with payment status emoji at the end (no separate payment line)
        budget_raw = job.get('budget')
        status_emoji = "✅" if job.get('client_payment_verified') else "❌"
        if budget_raw:
            # Extract numbers from budget and make them bold
            import re
            # Find numbers in the budget string
            budget_with_bold = re.sub(r'(\d+(?:,\d+)*(?:\.\d+)?)', r'*\1*', budget_raw)
            text_parts.append(f"Budget: {budget_with_bold} : {status_emoji}")
        
        # Divider on same line as budget (no extra spacing)
        divider_text = "*───────────────────────────────────*"
        if text_parts:
            # Add divider to the last line (budget line)
            text_parts[-1] = f"{text_parts[-1]}\n{divider_text}"
        else:
            text_parts.append(divider_text)
        
        # Join all parts with single newlines (consistent spacing)
        main_text = "\n".join(text_parts)
        
        # Create main block with all content (one block = consistent spacing)
        main_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": main_text
            }
        }
        
        # Add button as accessory (will appear on right side)
        if url:
            main_block["accessory"] = {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Open Job"
                },
                "url": url,
                "action_id": "view_job"
            }
        
        blocks.append(main_block)
        
        return blocks
    
    def _get_tokyo_timestamp(self) -> str:
        """
        Get current timestamp in Asia/Tokyo timezone formatted as YYYY/MM/DD : HH:MM
        
        Returns:
            Formatted timestamp string
        """
        try:
            if PYTZ_AVAILABLE:
                tokyo_tz = pytz.timezone('Asia/Tokyo')
                now_tokyo = datetime.now(tokyo_tz)
            else:
                # Fallback: use UTC offset for JST (UTC+9)
                from datetime import timezone, timedelta
                jst = timezone(timedelta(hours=9))
                now_tokyo = datetime.now(jst)
            
            return now_tokyo.strftime('%Y/%m/%d : %H:%M')
        except Exception as e:
            # Fallback to local time if timezone conversion fails
            return datetime.now().strftime('%Y/%m/%d : %H:%M')
    
    def send_single_job(self, job: Dict) -> bool:
        """
        Send a single job notification to Slack
        
        Args:
            job: Job data dictionary
        
        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            print("⚠️  Warning: Slack webhook URL not configured, skipping notification")
            return False
        
        # Format job blocks (includes divider at bottom)
        job_blocks = self.format_job_blocks(job, index=None)
        
        # Get timestamp in Tokyo timezone
        timestamp = self._get_tokyo_timestamp()
        
        # Combine timestamp header with job blocks in one block for consistent spacing
        blocks = []
        
        if job_blocks and len(job_blocks) > 0:
            # Get the job content from first block
            first_block = job_blocks[0]
            job_text = first_block.get("text", {}).get("text", "") if first_block.get("text") else ""
            
            # Combine timestamp and job content in one block (no extra spacing)
            combined_text = f"*🎉 New Job Found 🎉 {timestamp}*\n{job_text}"
            
            combined_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": combined_text
                }
            }
            
            # Add button if it exists in the first block
            if first_block.get("accessory"):
                combined_block["accessory"] = first_block["accessory"]
            
            blocks.append(combined_block)
        else:
            # Fallback: just header
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🎉 New Job Found 🎉 {timestamp}*"
                }
            })
        
        # Get job title for fallback text
        title = job.get('title', 'New Job')
        if self.translator and self.translator.is_available():
            try:
                translated_title = self.translator.translate_text(title, target_lang="EN-US")
                if translated_title:
                    title = translated_title
            except:
                pass
        
        return self.send_message(f"🎉 New Job Found 🎉 {timestamp} - {title}", blocks=blocks)
    
    def send_new_jobs(self, new_jobs: List[Dict], total_scraped: int = None) -> bool:
        """
        Send notification about new jobs found
        
        Args:
            new_jobs: List of new job dictionaries
            total_scraped: Total number of jobs scraped (optional)
        
        Returns:
            True if successful, False otherwise
        """
        if not new_jobs:
            print("ℹ️  No new jobs to notify about")
            return True  # No new jobs, nothing to send
        
        if not self.webhook_url:
            print("⚠️  Warning: Slack webhook URL not configured, skipping notification")
            return False
        
        print(f"📤 Preparing to send {len(new_jobs)} new job(s) to Slack...")
        
        # Header block
        header_text = f"🎉 *{len(new_jobs)} New Job{'s' if len(new_jobs) != 1 else ''} Found on Workana!*"
        if total_scraped:
            header_text += f"\n(Scraped {total_scraped} jobs total)"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🎉 {len(new_jobs)} New Job{'s' if len(new_jobs) != 1 else ''} Found!"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": header_text
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*───────────────────────────────────*"
                }
            }
        ]
        
        # Add job blocks (limit to 10 jobs per message to avoid message too long)
        jobs_to_send = new_jobs[:10]
        for i, job in enumerate(jobs_to_send, 1):
            blocks.append(self.format_job_block(job, index=i))
            # Add bold divider between jobs (except after the last one)
            if i < len(jobs_to_send):
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*───────────────────────────────────*"
                    }
                })
        
        # If more than 10 jobs, add note
        if len(new_jobs) > 10:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*... and {len(new_jobs) - 10} more new jobs!* Check the database for full list."
                }
            })
        
        # Footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Scraped from Workana.com • Total new jobs: {len(new_jobs)}"
                }
            ]
        })
        
        # Send message
        fallback_text = f"Found {len(new_jobs)} new job(s) on Workana"
        return self.send_message(fallback_text, blocks)
    
    def send_summary(self, stats: Dict) -> bool:
        """
        Send scraping summary statistics
        
        Args:
            stats: Statistics dictionary with keys like:
                   - total_jobs
                   - new_jobs_24h
                   - total_scrapes
                   - duration_seconds
        
        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            return False
        
        duration_min = stats.get('duration_seconds', 0) / 60
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 Workana Scraping Summary"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Jobs:*\n{stats.get('total_jobs', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*New (24h):*\n{stats.get('new_jobs_24h', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Scrapes:*\n{stats.get('total_scrapes', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Duration:*\n{duration_min:.1f} min"
                    }
                ]
            }
        ]
        
        fallback_text = f"Scraping complete: {stats.get('total_jobs', 0)} total jobs"
        return self.send_message(fallback_text, blocks)

