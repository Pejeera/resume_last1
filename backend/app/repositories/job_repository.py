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
                return None
            
            # Find job by ID
            for job in jobs_data:
                job_id_in_data = job.get("_id") or job.get("id") or job.get("job_id") or ""
                if job_id_in_data == job_id:
                    # Return job in OpenSearch format
                    return {
                        "id": job_id,
                        "title": job.get("title", "N/A"),
                        "description": job.get("description", job.get("text_excerpt", "")),
                        "text_excerpt": job.get("text_excerpt", job.get("description", ""))[:500],
                        "metadata": job.get("metadata", {}),
                        "created_at": job.get("created_at", "")
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting job from S3: {e}")
            return None


job_repository = JobRepository()

