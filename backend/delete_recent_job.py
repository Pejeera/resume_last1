"""
Script to delete recently created job from OpenSearch
Searches for job with title "Backend Engineer" and deletes it
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.clients.opensearch_client import opensearch_client
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def search_and_delete_job_by_title(title: str):
    """Search for job by title and delete it from OpenSearch"""
    try:
        index_name = "jobs_index"
        
        if settings.USE_MOCK:
            # In mock mode, search in mock storage
            docs = opensearch_client._mock_data_storage.get(index_name, [])
            matching_jobs = [
                doc for doc in docs 
                if doc.get('title', '').lower() == title.lower()
            ]
            
            if not matching_jobs:
                logger.warning(f"No job found with title '{title}' in mock storage")
                return False
            
            # Delete all matching jobs
            for job in matching_jobs:
                job_id = job.get('_id') or job.get('id') or job.get('job_id')
                if job_id:
                    deleted = opensearch_client.delete_document(index_name, job_id)
                    if deleted:
                        logger.info(f"Deleted job '{title}' (ID: {job_id}) from mock storage")
                    else:
                        logger.warning(f"Failed to delete job '{title}' (ID: {job_id})")
            
            return len(matching_jobs) > 0
        else:
            # In production, use OpenSearch search
            search_query = {
                "query": {
                    "match": {
                        "title": title
                    }
                },
                "size": 100
            }
            
            response = opensearch_client.client.search(index=index_name, body=search_query)
            hits = response.get('hits', {}).get('hits', [])
            
            if not hits:
                logger.warning(f"No job found with title '{title}' in OpenSearch")
                return False
            
            # Delete all matching jobs
            deleted_count = 0
            for hit in hits:
                job_id = hit['_id']
                job_title = hit['_source'].get('title', 'N/A')
                
                deleted = opensearch_client.delete_document(index_name, job_id)
                if deleted:
                    logger.info(f"Deleted job '{job_title}' (ID: {job_id}) from OpenSearch")
                    deleted_count += 1
                else:
                    logger.warning(f"Failed to delete job '{job_title}' (ID: {job_id})")
            
            logger.info(f"Deleted {deleted_count} job(s) with title '{title}'")
            return deleted_count > 0
            
    except Exception as e:
        logger.error(f"Error searching/deleting job: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    print("Searching for job with title 'Backend Engineer'...")
    success = search_and_delete_job_by_title("Backend Engineer")
    
    if success:
        print("✅ Successfully deleted job(s) from OpenSearch")
    else:
        print("⚠️  No job found or deletion failed")
        sys.exit(1)
