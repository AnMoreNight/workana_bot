"""
Script to clean up old jobs from database, keeping only the newest ones
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import DATABASE_PATH, MAX_JOBS_IN_DB
from storage.database import WorkanaDatabase


def main():
    """Clean up old jobs from database"""
    print("=" * 60)
    print("Database Cleanup")
    print("=" * 60)
    
    # Initialize database
    db = WorkanaDatabase(str(DATABASE_PATH))
    
    # Get current statistics
    stats = db.get_statistics()
    current_count = stats['total_jobs']
    
    print(f"\nCurrent jobs in database: {current_count}")
    print(f"Target limit: {MAX_JOBS_IN_DB}")
    
    if current_count <= MAX_JOBS_IN_DB:
        print(f"\n✅ Database is already within limit ({current_count} <= {MAX_JOBS_IN_DB})")
        print("No cleanup needed.")
        db.close()
        return
    
    # Cleanup old jobs
    print(f"\n🗑️  Removing old jobs...")
    removed_count = db.cleanup_old_jobs()
    
    # Get updated statistics
    stats_after = db.get_statistics()
    new_count = stats_after['total_jobs']
    
    print(f"\n✅ Cleanup complete!")
    print(f"   Removed: {removed_count} job(s)")
    print(f"   Remaining: {new_count} job(s)")
    print(f"   Limit: {MAX_JOBS_IN_DB} job(s)")
    
    db.close()


if __name__ == "__main__":
    main()
