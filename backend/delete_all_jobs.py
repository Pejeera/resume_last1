"""
Script to delete all jobs from both S3 and OpenSearch
Use with caution - this will delete ALL jobs!
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.clients.s3_client import s3_client
from app.clients.opensearch_client import opensearch_client
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def delete_all_jobs():
    """Delete all jobs from both S3 and OpenSearch"""
    print("=" * 60)
    print("WARNING: This will delete ALL jobs from S3 and OpenSearch!")
    print("=" * 60)
    
    # Load all jobs from S3
    print("\n[1/3] Loading all jobs from S3...")
    jobs_data = s3_client.load_jobs_data()
    
    if not jobs_data:
        print("No jobs found in S3. Nothing to delete.")
        return
    
    print(f"Found {len(jobs_data)} job(s) in S3")
    
    deleted_from_s3 = 0
    deleted_from_opensearch = 0
    errors = []
    
    # Delete each job
    print("\n[2/3] Deleting jobs...")
    for i, job in enumerate(jobs_data, 1):
        job_id = job.get("_id") or job.get("id") or job.get("job_id")
        job_title = job.get("title", "N/A")
        
        if not job_id:
            print(f"  [{i}/{len(jobs_data)}] Skipping job without ID: {job_title}")
            continue
        
        print(f"  [{i}/{len(jobs_data)}] Deleting: {job_title} (ID: {job_id})")
        
        # Delete from OpenSearch
        try:
            deleted = opensearch_client.delete_document(
                index_name="jobs_index",
                doc_id=job_id
            )
            if deleted:
                deleted_from_opensearch += 1
                print(f"    ✓ Deleted from OpenSearch")
            else:
                print(f"    ⚠ Not found in OpenSearch (may have been already deleted)")
        except Exception as e:
            error_msg = f"Failed to delete {job_id} from OpenSearch: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            print(f"    ✗ Error deleting from OpenSearch: {e}")
        
        # Delete from S3
        try:
            from app.repositories.job_repository import job_repository
            job_title_for_file = job.get("title", "job")
            filename = job_repository._sanitize_filename(job_title_for_file, job_id)
            jobs_prefix = f"{settings.S3_PREFIX}jobs/"
            s3_key = f"{jobs_prefix}{filename}"
            
            if settings.USE_MOCK:
                # Delete local file
                local_file = os.path.join("jobs", filename)
                if os.path.exists(local_file):
                    os.remove(local_file)
                    deleted_from_s3 += 1
                    print(f"    ✓ Deleted from local S3 (mock): {local_file}")
                else:
                    print(f"    ⚠ File not found: {local_file}")
            else:
                # Delete from S3
                try:
                    s3_client.client.delete_object(
                        Bucket=settings.S3_BUCKET_NAME,
                        Key=s3_key
                    )
                    deleted_from_s3 += 1
                    print(f"    ✓ Deleted from S3: {s3_key}")
                except Exception as e:
                    error_msg = str(e)
                    if 'NoSuchKey' in error_msg or '404' in error_msg:
                        print(f"    ⚠ File not found in S3 (may have been already deleted)")
                    else:
                        error_msg = f"Failed to delete {job_id} from S3: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        print(f"    ✗ Error deleting from S3: {e}")
        except Exception as e:
            error_msg = f"Failed to delete {job_id} from S3: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            print(f"    ✗ Error: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("[3/3] Summary")
    print("=" * 60)
    print(f"Total jobs found: {len(jobs_data)}")
    print(f"Deleted from OpenSearch: {deleted_from_opensearch}")
    print(f"Deleted from S3: {deleted_from_s3}")
    
    if errors:
        print(f"\nErrors occurred: {len(errors)}")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✅ All jobs deleted successfully!")
    
    print("=" * 60)


if __name__ == "__main__":
    try:
        delete_all_jobs()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        logger.error(f"Error deleting all jobs: {e}", exc_info=True)
        sys.exit(1)
