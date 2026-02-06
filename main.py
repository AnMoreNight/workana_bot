"""
Main script for Workana job scraper
"""
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import (
    DATABASE_PATH, DEFAULT_CATEGORY, DEFAULT_LANGUAGE,
    MAX_PAGES, STOP_ON_KNOWN_JOB, SLACK_WEBHOOK_URL, ENABLE_SLACK_NOTIFICATIONS,
    SCRAPE_INTERVAL, ENABLE_SHEETS_EXPORT, GOOGLE_SHEETS_SPREADSHEET_ID, GOOGLE_SHEETS_CREDENTIALS_JSON
)
from storage.database import WorkanaDatabase
from scrapers.workana_scraper import WorkanaScraper
from parsers.date_parser import extract_job_id_from_url
from utils.slack_notifier import SlackNotifier
from utils.translator import DeepLTranslator
from utils.sheets_exporter import SheetsExporter


def run_scrape(db, scraper, slack_notifier, translator, sheets_exporter):
    """Run a single scrape cycle"""
    start_time = time.time()
    
    # Get existing job IDs
    existing_job_ids = db.get_existing_job_ids()
    
    try:
        # Scrape jobs
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting scrape...")
        print(f"Category: {DEFAULT_CATEGORY} | Language: {DEFAULT_LANGUAGE} | Max pages: {MAX_PAGES or 'No limit'}")
        print("-" * 60)
        
        scraped_jobs = scraper.scrape(
            category=DEFAULT_CATEGORY,
            language=DEFAULT_LANGUAGE,
            existing_job_ids=existing_job_ids,
            max_pages=MAX_PAGES
        )
        
        print(f"Scraped {len(scraped_jobs)} jobs total")
        
        # Save jobs to database
        new_jobs = []
        updated_jobs = 0
        
        for job in scraped_jobs:
            if not job.get('id'):
                continue
            
            is_new = db.save_job(job)
            if is_new:
                new_jobs.append(job)
            else:
                updated_jobs += 1
        
        print(f"New jobs: {len(new_jobs)} | Updated jobs: {updated_jobs}")
        
        # Send Slack notification for new jobs (individually)
        # Only send jobs that haven't been sent before (prevent duplicates)
        if not slack_notifier:
            print("ℹ️  Slack notifier not configured, skipping Slack notifications")
        elif not new_jobs:
            print("ℹ️  No new jobs to send to Slack")
        else:
            # Filter out jobs that have already been sent to Slack
            unsent_jobs = []
            for job in new_jobs:
                job_id = job.get('id')
                if not job_id:
                    print(f"⚠️  Skipping job without ID: {job.get('title', 'Unknown')[:50]}")
                    continue
                if db.is_job_sent_to_slack(job_id):
                    print(f"ℹ️  Job {job_id} already sent to Slack, skipping")
                else:
                    unsent_jobs.append(job)
            
            if unsent_jobs:
                print(f"📤 Sending {len(unsent_jobs)} job(s) individually to Slack...")
                
                success_count = 0
                failed_count = 0
                for i, job in enumerate(unsent_jobs, 1):
                    job_id = job.get('id')
                    job_title = job.get('title', 'Unknown')[:50]
                    print(f"   [{i}/{len(unsent_jobs)}] Sending job: {job_title}...")
                    success = slack_notifier.send_single_job(job)
                    if success and job_id:
                        # Mark as sent to prevent duplicates
                        if db.mark_job_sent_to_slack(job_id):
                            success_count += 1
                            print(f"   ✅ Job {job_id} sent and marked in database")
                        else:
                            print(f"   ⚠️  Job {job_id} sent but failed to mark in database")
                    else:
                        failed_count += 1
                        print(f"   ❌ Failed to send job {job_id}")
                    
                    # Small delay between messages to avoid rate limiting
                    if i < len(unsent_jobs):
                        time.sleep(0.5)
                
                print(f"✅ Sent {success_count}/{len(unsent_jobs)} job notifications to Slack")
                if failed_count > 0:
                    print(f"⚠️  {failed_count} job(s) failed to send")
            else:
                print(f"ℹ️  All {len(new_jobs)} new job(s) were already sent to Slack (skipping duplicates)")
        
        # Calculate pages scraped (approximate)
        pages_scraped = len(scraped_jobs) // 20  # Assuming ~20 jobs per page
        
        # Save scrape history
        duration = time.time() - start_time
        db.save_scrape_history(
            jobs_found=len(scraped_jobs),
            new_jobs_count=len(new_jobs),
            pages_scraped=pages_scraped,
            duration_seconds=duration,
            category=DEFAULT_CATEGORY,
            language=DEFAULT_LANGUAGE
        )
        
        # Export jobs to Google Sheets (daily sheet)
        # Use new_jobs directly instead of querying database to avoid timing/timezone issues
        if not sheets_exporter:
            print("ℹ️  Google Sheets exporter not configured, skipping export")
        elif not sheets_exporter.is_available():
            print("ℹ️  Google Sheets exporter not available, skipping export")
        elif not new_jobs:
            print("ℹ️  No new jobs to export to Google Sheets")
        else:
            try:
                # Ensure today's sheet exists (create if it doesn't)
                sheets_exporter.ensure_today_sheet_exists()
                
                # Filter out jobs that have already been exported
                # Use new_jobs directly instead of querying database
                unexported_jobs = []
                for job in new_jobs:
                    job_id = job.get('id')
                    if not job_id:
                        print(f"⚠️  Skipping job without ID for Sheets export: {job.get('title', 'Unknown')[:50]}")
                        continue
                    if db.is_job_exported_to_sheets(job_id):
                        print(f"ℹ️  Job {job_id} already exported to Sheets, skipping")
                    else:
                        unexported_jobs.append(job)
                
                if unexported_jobs:
                    print(f"📊 Exporting {len(unexported_jobs)} job(s) to Google Sheets...")
                    exported_count = sheets_exporter.export_jobs(unexported_jobs)
                    
                    # Verify export count
                    if exported_count == 0:
                        print(f"⚠️  Warning: No jobs were exported, but {len(unexported_jobs)} job(s) were provided")
                    elif exported_count != len(unexported_jobs):
                        print(f"⚠️  Warning: Expected {len(unexported_jobs)} job(s) to be exported, but only {exported_count} were exported")
                    else:
                        print(f"✅ Successfully exported {exported_count} job(s) to Google Sheets")
                    
                    # Mark jobs as exported (only mark the ones that were actually exported)
                    marked_count = 0
                    for job in unexported_jobs[:exported_count]:
                        job_id = job.get('id')
                        if job_id:
                            if db.mark_job_exported_to_sheets(job_id):
                                marked_count += 1
                                print(f"   ✅ Job {job_id} marked as exported in database")
                            else:
                                print(f"   ⚠️  Failed to mark job {job_id} as exported in database")
                    
                    if marked_count != exported_count:
                        print(f"⚠️  Warning: Exported {exported_count} job(s), but only {marked_count} were marked as exported in database")
                else:
                    print(f"ℹ️  All {len(new_jobs)} new job(s) were already exported to Google Sheets")
            except ConnectionError as e:
                print(f"⚠️  Network error exporting to Google Sheets: {e}")
                print("   Jobs will be exported when network connection is restored.")
            except Exception as e:
                print(f"⚠️  Error exporting to Google Sheets: {e}")
                import traceback
                traceback.print_exc()
        
        # Display brief statistics
        stats = db.get_statistics()
        print(f"Total jobs in DB: {stats['total_jobs']} | New (24h): {stats['new_jobs_24h']} | Duration: {duration:.1f}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main execution function"""
    print("=" * 60)
    print("Workana Job Scraper")
    print("=" * 60)
    
    if SCRAPE_INTERVAL:
        print(f"🔄 Running in continuous mode (every {SCRAPE_INTERVAL} seconds)")
        print("   Press Ctrl+C to stop")
    else:
        print("▶️  Running once")
    
    # Initialize database
    print("\n[1/5] Initializing database...")
    db = WorkanaDatabase(str(DATABASE_PATH))
    
    # Initialize DeepL translator (if configured)
    translator = None
    try:
        translator = DeepLTranslator()
        if translator.is_available():
            print("[2/5] DeepL translator initialized ✅")
        else:
            print("[2/5] DeepL translator disabled (no API key)")
            translator = None
    except Exception as e:
        print(f"[2/5] DeepL translator error: {e}")
        translator = None
    
    # Initialize Slack notifier (if configured)
    slack_notifier = None
    if ENABLE_SLACK_NOTIFICATIONS and SLACK_WEBHOOK_URL:
        print("[3/6] Initializing Slack notifications...")
        slack_notifier = SlackNotifier(SLACK_WEBHOOK_URL, translator=translator)
        print(f"✅ Slack notifications enabled")
        if translator and translator.is_available():
            print(f"   Translation: Enabled (DeepL)")
    else:
        print("[3/6] Slack notifications disabled")
    
    # Initialize Google Sheets exporter (if configured)
    sheets_exporter = None
    if ENABLE_SHEETS_EXPORT and GOOGLE_SHEETS_CREDENTIALS_JSON:
        print("[4/6] Initializing Google Sheets exporter...")
        try:
            sheets_exporter = SheetsExporter(
                spreadsheet_id=GOOGLE_SHEETS_SPREADSHEET_ID,
                credentials_json=GOOGLE_SHEETS_CREDENTIALS_JSON,
                translator=translator  # Pass translator for translating jobs
            )
            print(f"✅ Google Sheets export enabled")
            print(f"   Spreadsheet ID: {GOOGLE_SHEETS_SPREADSHEET_ID}")
            if translator and translator.is_available():
                print(f"   Translation: Enabled (jobs will be translated to English)")
        except Exception as e:
            print(f"⚠️  Google Sheets export error: {e}")
            sheets_exporter = None
    else:
        print("[4/6] Google Sheets export disabled")
    
    # Initialize scraper
    print("[5/6] Initializing scraper...")
    scraper = WorkanaScraper()
    scraper.setup_driver()
    
    print("[6/6] Setup complete!")
    print("=" * 60)
    
    try:
        if SCRAPE_INTERVAL:
            # Continuous mode - run every SCRAPE_INTERVAL seconds
            run_count = 0
            while True:
                run_count += 1
                print(f"\n{'='*60}")
                print(f"Run #{run_count}")
                print(f"{'='*60}")
                
                run_scrape(db, scraper, slack_notifier, translator, sheets_exporter)
                
                # Calculate next run time
                next_run = datetime.now().timestamp() + SCRAPE_INTERVAL
                next_run_str = datetime.fromtimestamp(next_run).strftime('%H:%M:%S')
                print(f"\n⏰ Next run in {SCRAPE_INTERVAL} seconds (at {next_run_str})")
                print("   Press Ctrl+C to stop")
                
                # Wait for next run
                time.sleep(SCRAPE_INTERVAL)
        else:
            # Single run mode
            run_scrape(db, scraper, slack_notifier, translator, sheets_exporter)
            print("\n✅ Scraping complete!")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Scraping interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        print("\nCleaning up...")
        scraper.close()
        db.close()
        print("Done!")


if __name__ == "__main__":
    main()

