"""
Job Repository
Data access layer for job operations
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

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
            job_id = str(uuid.uuid4())
            
            # Generate embedding
            full_text = f"{title}\n{description}"
            embedding = self.bedrock.generate_embedding(full_text)
            
            # Create document
            document = {
                "id": job_id,
                "title": title,
                "description": description,
                "text_excerpt": description[:500],
                "embeddings": embedding,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Index in OpenSearch
            self.opensearch.index_document(
                index_name=self.INDEX_NAME,
                doc_id=job_id,
                document=document
            )
            
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
        """Get job by ID"""
        return self.opensearch.get_document(self.INDEX_NAME, job_id)


job_repository = JobRepository()

