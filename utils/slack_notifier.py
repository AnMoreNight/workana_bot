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
        Format a single job as Slack block
        
        Args:
            job: Job data dictionary
            index: Optional index number
        
        Returns:
            Slack block dictionary
        """
        # Get original values
        original_title = job.get('title', 'N/A')
        original_description = job.get('description', '')
        
        # Translate title if translator is available
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
        
        # Build job info text
        info_parts = []
        
        if job.get('posted_date_relative'):
            info_parts.append(f"*Posted:* {job['posted_date_relative']}")
        
        if job.get('budget'):
            info_parts.append(f"*Budget:* {job['budget']}")
        
        if job.get('bids_count') is not None:
            info_parts.append(f"*Bids:* {job['bids_count']}")
        
        # Note: client_country is displayed separately for prominence
        # if job.get('client_country'):
        #     info_parts.append(f"*Country:* {job['client_country']}")
        
        if job.get('client_rating'):
            info_parts.append(f"*Client Rating:* {job['client_rating']}/5.0")
        
        info_text = " • ".join(info_parts)
        
        # Skills
        skills_text = ""
        if job.get('skills'):
            skills = job['skills'] if isinstance(job['skills'], list) else json.loads(job['skills'])
            if skills:
                skills_text = f"*Skills:* {', '.join(skills[:5])}"  # Show first 5 skills
                if len(skills) > 5:
                    skills_text += f" (+{len(skills) - 5} more)"
        
        # Description summary - summarize first, then translate
        description_summary = ""
        key_points = []
        
        if original_description:
            # Get summarized description from original
            summary_data = summarize_job_description(original_description, include_key_points=True)
            description_summary = summary_data.get('summary', '')
            key_points = summary_data.get('key_points', [])
            
            # Translate summary and key points if translator is available
            if self.translator and self.translator.is_available():
                try:
                    # Translate summary
                    if description_summary:
                        translated_summary = self.translator.translate_text(description_summary, target_lang="EN-US")
                        if translated_summary:
                            description_summary = translated_summary
                    
                    # Translate key points
                    if key_points:
                        translated_key_points = []
                        for point in key_points:
                            translated_point = self.translator.translate_text(point, target_lang="EN-US")
                            if translated_point:
                                translated_key_points.append(translated_point)
                            else:
                                translated_key_points.append(point)  # Fallback to original
                        key_points = translated_key_points
                except Exception as e:
                    print(f"⚠️  Warning: Failed to translate description summary: {e}")
        
        # Build block with better formatting - use single text field with proper line breaks
        title_text = f"*{index}. {title}*" if index is not None else f"*{title}*"
        
        # Build main text with proper spacing and line breaks
        text_parts = [title_text]
        
        # Add client information on separate lines for prominence
        client_info_parts = []
        
        # Client name
        if job.get('client_name'):
            client_info_parts.append(f"👤 *Client:* {job['client_name']}")
        
        # Country
        if job.get('client_country'):
            client_info_parts.append(f"🌍 *Country:* {job['client_country']}")
        
        # Payment verified status
        if job.get('client_payment_verified'):
            client_info_parts.append("✅ *Payment Verified*")
        else:
            client_info_parts.append("❌ *Payment Not Verified*")
        
        if client_info_parts:
            text_parts.append("\n".join(client_info_parts))
        
        # Add info text with proper spacing
        if info_text:
            text_parts.append(info_text)
        
        # Add skills with proper spacing
        if skills_text:
            text_parts.append(skills_text)
        
        # Combine with double line breaks for better separation
        main_text = "\n\n".join(text_parts)
        
        # Create main block
        block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": main_text
            }
        }
        
        # Add description summary as a separate field for better layout
        if description_summary:
            # Build description text with proper formatting
            desc_parts = [f"*Summary:*"]
            desc_parts.append(description_summary)
            
            # Add key points if available
            if key_points:
                desc_parts.append("\n*Key Points:*")
                for point in key_points:
                    desc_parts.append(f"• {point}")
            
            desc_text = "\n".join(desc_parts)
            
            # Add as a field (Slack fields are displayed side-by-side, but we'll use it for better spacing)
            block["fields"] = [
                {
                    "type": "mrkdwn",
                    "text": desc_text
                }
            ]
        
        # Add accessory (link button)
        if url:
            block["accessory"] = {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "View Job"
                },
                "url": url,
                "action_id": "view_job"
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
        main_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": main_text
            }
        }
        
        blocks.append(main_block)
        
        # Add divider at the bottom to separate from other jobs
        blocks.append({
            "type": "divider"
        })
        
        return blocks
    
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
        
        # Create blocks with header (using section instead of header type for same font, bold text)
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🎉 New Job Found 🎉 {timestamp}*"
                }
            }
        ]
        
        # Add job blocks (already includes divider at bottom)
        blocks.extend(job_blocks)
        
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
                "type": "divider"
            }
        ]
        
        # Add job blocks (limit to 10 jobs per message to avoid message too long)
        jobs_to_send = new_jobs[:10]
        for i, job in enumerate(jobs_to_send, 1):
            blocks.append(self.format_job_block(job, index=i))
            if i < len(jobs_to_send):
                blocks.append({"type": "divider"})
        
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

