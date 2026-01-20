"""
Job Repository
Data access layer for job operations
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import json
import os

from app.clients.opensearch_client import opensearch_client
from app.clients.bedrock_client import bedrock_client
from app.core.logging import get_logger

logger = get_logger(__name__)


class JobRepository:
    """Repository for job data operations"""
    
    INDEX_NAME = "jobs_index"
    
    def __init__(self):
        self.opensearch = opensearch_client
        self.bedrock = bedrock_client
    
    @staticmethod
    def _sanitize_filename(title: str, job_id: str) -> str:
        """
        Sanitize title to create a valid filename
        Format: {sanitized-title}-{job_id}.json
        """
        import re
        # Remove special characters, keep only alphanumeric, spaces, hyphens
        sanitized = re.sub(r'[^\w\s-]', '', title)
        # Replace multiple spaces/hyphens with single hyphen
        sanitized = re.sub(r'[-\s]+', '-', sanitized)
        # Remove leading/trailing hyphens and convert to lowercase
        sanitized = sanitized.strip('-').lower()
        
        # Limit filename length (keep it reasonable)
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        # If title is empty after sanitization, use a default
        if not sanitized:
            sanitized = "job"
        
        # Format: {title}-{job_id}.json
        return f"{sanitized}-{job_id}.json"
    
    def create_job(
        self,
        title: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new job entry
        
        Args:
            title: Job title
            description: Job description
            metadata: Optional metadata
            
        Returns:
            Created job document
        """
        try:
            from app.clients.s3_client import s3_client
            from app.core.config import settings
            
            job_id = str(uuid.uuid4())
            
            # Generate embedding
            full_text = f"{title}\n{description}"
            embedding = self.bedrock.generate_embedding(full_text)
            
            # Prepare metadata dict
            metadata_dict = metadata or {}
            
            # Create document for OpenSearch (without _id)
            document = {
                "id": job_id,
                "title": title,
                "description": description,
                "text_excerpt": description[:500],
                "embeddings": embedding,
                "metadata": metadata_dict,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Create job_data for S3 (with all fields including flattened metadata)
            job_data = {
                "_id": job_id,
                "id": job_id,
                "job_id": job_id,
                "title": title,
                "description": description,
                "text_excerpt": description[:500],
                "embeddings": embedding,
                "metadata": metadata_dict,
                "created_at": document["created_at"]
            }
            
            # Flatten metadata fields to top level for compatibility with list_jobs
            if metadata_dict:
                if "location" in metadata_dict:
                    job_data["location"] = metadata_dict["location"]
                if "department" in metadata_dict:
                    job_data["department"] = metadata_dict["department"]
                if "employment_type" in metadata_dict:
                    job_data["employment_type"] = metadata_dict["employment_type"]
                if "experience_years" in metadata_dict:
                    job_data["experience_years"] = metadata_dict["experience_years"]
                if "skills" in metadata_dict:
                    job_data["skills"] = metadata_dict["skills"]
                if "responsibilities" in metadata_dict:
                    job_data["responsibilities"] = metadata_dict["responsibilities"]
                if "requirements" in metadata_dict:
                    job_data["requirements"] = metadata_dict["requirements"]
                if "scoring_weights" in metadata_dict:
                    job_data["scoring_weights"] = metadata_dict["scoring_weights"]
            
            # Generate filename from title
            filename = self._sanitize_filename(title, job_id)
            
            # Save to S3
            jobs_prefix = f"{settings.S3_PREFIX}jobs/"
            s3_key = f"{jobs_prefix}{filename}"
            
            if settings.USE_MOCK:
                # In mock mode, save to local file
                local_dir = "jobs"
                os.makedirs(local_dir, exist_ok=True)
                local_file = os.path.join(local_dir, filename)
                try:
                    with open(local_file, 'w', encoding='utf-8') as f:
                        json.dump(job_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"MOCK: Created job {job_id} in {local_file}")
                except Exception as e:
                    logger.error(f"MOCK: Failed to save job: {e}")
                    raise
            else:
                # Save to S3
                try:
                    data_json = json.dumps(job_data, ensure_ascii=False, indent=2).encode('utf-8')
                    s3_client.client.put_object(
                        Bucket=settings.S3_BUCKET_NAME,
                        Key=s3_key,
                        Body=data_json,
                        ContentType='application/json',
                        Metadata={
                            "created_at": document["created_at"],
                            "job_id": job_id
                        }
                    )
                    logger.info(f"Created job {job_id} in S3: {s3_key}")
                except Exception as e:
                    logger.error(f"Failed to save job to S3: {e}")
                    raise
            
            # Index in OpenSearch (if not in mock mode)
            if not settings.USE_MOCK:
                try:
                    self.opensearch.index_document(
                        index_name=self.INDEX_NAME,
                        doc_id=job_id,
                        document=document
                    )
                    logger.info(f"Created job {job_id} in OpenSearch")
                except Exception as e:
                    logger.warning(f"Failed to index job in OpenSearch (job still saved in S3): {e}")
                    # Don't fail the request if OpenSearch indexing fails
            
            logger.info(f"Created job {job_id}")
            return {
                "job_id": job_id,
                "title": title,
                "created_at": document["created_at"]
            }
            
        except Exception as e:
            logger.error(f"Error creating job: {e}")
            raise
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID from OpenSearch"""
        return self.opensearch.get_document(self.INDEX_NAME, job_id)
    
    def get_job_from_s3(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job from S3 by ID
        Searches in S3 jobs directory
        """
        try:
            from app.clients.s3_client import s3_client
            from app.core.config import settings
            
            # Load jobs from S3
            jobs_data = s3_client.load_jobs_data()
            if not jobs_data:
                logger.warning(f"get_job_from_s3: No jobs data loaded from S3 for job_id={job_id}")
                return None
            
            logger.info(f"get_job_from_s3: Searching for job_id={job_id} in {len(jobs_data)} jobs")
            
            # Find job by ID - try multiple ID field formats
            for idx, job in enumerate(jobs_data):
                job_id_in_data = job.get("_id") or job.get("id") or job.get("job_id") or ""
                
                # Log for debugging (only for first few jobs to avoid spam)
                if idx < 3:
                    logger.debug(f"get_job_from_s3: Checking job with id={job_id_in_data}, title={job.get('title', 'N/A')}")
                
                # Compare job IDs (strip whitespace and compare as strings)
                if str(job_id_in_data).strip() == str(job_id).strip():
                    logger.info(f"get_job_from_s3: Found job {job_id} in S3")
                    # Return job with all fields (similar to what list_jobs returns)
                    return {
                        "id": job_id,
                        "job_id": job_id,
                        "_id": job_id,
                        "title": job.get("title", "N/A"),
                        "description": job.get("description", job.get("text_excerpt", "")),
                        "text_excerpt": job.get("text_excerpt", job.get("description", ""))[:500],
                        "metadata": job.get("metadata", {}),
                        "created_at": job.get("created_at", ""),
                        # Include flattened metadata fields for compatibility
                        "location": job.get("location") or (job.get("metadata", {}).get("location") if isinstance(job.get("metadata"), dict) else None),
                        "department": job.get("department") or (job.get("metadata", {}).get("department") if isinstance(job.get("metadata"), dict) else None),
                        "employment_type": job.get("employment_type") or (job.get("metadata", {}).get("employment_type") if isinstance(job.get("metadata"), dict) else None),
                        "experience_years": job.get("experience_years") or (job.get("metadata", {}).get("experience_years") if isinstance(job.get("metadata"), dict) else None),
                        "skills": job.get("skills") or (job.get("metadata", {}).get("skills", []) if isinstance(job.get("metadata"), dict) else []),
                        "responsibilities": job.get("responsibilities") or (job.get("metadata", {}).get("responsibilities", []) if isinstance(job.get("metadata"), dict) else []),
                        "requirements": job.get("requirements") or (job.get("metadata", {}).get("requirements", []) if isinstance(job.get("metadata"), dict) else []),
                        "scoring_weights": job.get("scoring_weights") or (job.get("metadata", {}).get("scoring_weights") if isinstance(job.get("metadata"), dict) else None),
                        "embeddings": job.get("embeddings")  # Include embeddings if available
                    }
            
            # Log all job IDs found for debugging
            found_ids = [job.get("_id") or job.get("id") or job.get("job_id") or "NO_ID" for job in jobs_data]
            logger.warning(f"get_job_from_s3: Job {job_id} not found. Available job IDs: {found_ids[:10]}")  # Log first 10 IDs
            return None
            
        except Exception as e:
            logger.error(f"Error getting job from S3: {e}", exc_info=True)
            return None


job_repository = JobRepository()

