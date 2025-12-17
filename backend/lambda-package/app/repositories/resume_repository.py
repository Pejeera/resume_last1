"""
Resume Repository
Data access layer for resume operations
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from app.clients.opensearch_client import opensearch_client
from app.clients.s3_client import s3_client
from app.clients.bedrock_client import bedrock_client
from app.services.file_processor import file_processor
from app.core.logging import get_logger
from app.core.exceptions import OpenSearchError, EmbeddingError

logger = get_logger(__name__)


class ResumeRepository:
    """Repository for resume data operations"""
    
    INDEX_NAME = "resumes_index"
    
    def __init__(self):
        self.opensearch = opensearch_client
        self.s3 = s3_client
        self.bedrock = bedrock_client
        self.file_processor = file_processor
    
    def create_resume(
        self,
        file_content: bytes,
        file_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new resume entry
        
        Args:
            file_content: Resume file content
            file_name: Original file name
            metadata: Optional metadata
            
        Returns:
            Created resume document
        """
        try:
            # 1. Upload to S3
            upload_result = self.s3.upload_file(file_content, file_name)
            resume_id = upload_result["file_id"]
            
            # 2. Extract text
            text = self.file_processor.extract_text(file_content, file_name)
            
            # 3. Generate embedding
            embedding = self.bedrock.generate_embedding(text)
            
            # 4. Create document
            document = {
                "id": resume_id,
                "name": file_name,
                "text_excerpt": text[:500],  # First 500 chars
                "full_text": text,
                "embeddings": embedding,
                "metadata": metadata or {},
                "s3_url": upload_result["s3_url"],
                "s3_key": upload_result["s3_key"],
                "created_at": datetime.utcnow().isoformat()
            }
            
            # 5. Index in OpenSearch
            self.opensearch.index_document(
                index_name=self.INDEX_NAME,
                doc_id=resume_id,
                document=document
            )
            
            logger.info(f"Created resume {resume_id}")
            return {
                "resume_id": resume_id,
                "s3_url": upload_result["s3_url"],
                "name": file_name,
                "created_at": document["created_at"]
            }
            
        except Exception as e:
            logger.error(f"Error creating resume: {e}")
            raise
    
    def bulk_create_resumes(
        self,
        files: List[tuple]  # List of (file_content, file_name) tuples
    ) -> List[Dict[str, Any]]:
        """
        Bulk create resumes
        
        Args:
            files: List of (file_content, file_name) tuples
            
        Returns:
            List of created resume documents
        """
        results = []
        for file_content, file_name in files:
            try:
                result = self.create_resume(file_content, file_name)
                results.append(result)
            except Exception as e:
                logger.error(f"Error creating resume {file_name}: {e}")
                results.append({
                    "error": str(e),
                    "file_name": file_name
                })
        
        return results
    
    def get_resume(self, resume_id: str) -> Optional[Dict[str, Any]]:
        """Get resume by ID"""
        return self.opensearch.get_document(self.INDEX_NAME, resume_id)


resume_repository = ResumeRepository()

