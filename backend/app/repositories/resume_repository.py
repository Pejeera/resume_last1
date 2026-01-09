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
    
    def get_resume_from_s3(self, resume_id: str) -> Optional[Dict[str, Any]]:
        """
        Get resume from S3 and process it (extract text, generate embedding)
        
        This is used when resume was uploaded to S3 but not yet processed.
        """
        try:
            # 1. Get resume from OpenSearch first (if already processed)
            resume = self.opensearch.get_document(self.INDEX_NAME, resume_id)
            if resume:
                logger.info(f"Resume {resume_id} found in OpenSearch")
                return resume
            
            # 2. If not in OpenSearch, get from S3 and process
            logger.info(f"Resume {resume_id} not in OpenSearch, processing from S3...")
            
            # Get S3 key from resume_id (assuming format: resumes/{resume_id}/filename)
            # We need to find the file in S3
            from app.core.config import settings
            
            # Use s3_client if available, otherwise use boto3 directly
            if hasattr(self.s3, 'client') and self.s3.client:
                s3_client_boto = self.s3.client
            else:
                import boto3
                s3_client_boto = boto3.client('s3', region_name=settings.AWS_REGION)
            
            # Get file from Candidate folder (structure: resumes/Candidate/{filename})
            # We need to find the file by resume_id in metadata or by searching
            # Since we store resume_id in metadata, we'll search in Candidate folder
            candidate_prefix = f"{settings.S3_PREFIX}Candidate/"
            
            # List all files in Candidate folder and find by resume_id in metadata
            response = s3_client_boto.list_objects_v2(
                Bucket=settings.S3_BUCKET_NAME,
                Prefix=candidate_prefix
            )
            
            s3_key = None
            file_name = None
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Check metadata for resume_id
                    try:
                        obj_metadata = s3_client_boto.head_object(
                            Bucket=settings.S3_BUCKET_NAME,
                            Key=obj['Key']
                        )
                        metadata = obj_metadata.get('Metadata', {})
                        if metadata.get('resume_id') == resume_id:
                            s3_key = obj['Key']
                            file_name = obj['Key'].split('/')[-1]
                            break
                    except:
                        continue
            
            # If not found by metadata, try to get from OpenSearch document if available
            if not s3_key:
                # Try to get s3_key from OpenSearch document
                resume_doc = self.opensearch.get_document(self.INDEX_NAME, resume_id)
                if resume_doc and 's3_key' in resume_doc:
                    s3_key = resume_doc['s3_key']
                    file_name = s3_key.split('/')[-1]
                else:
                    logger.error(f"Resume {resume_id} not found in S3 Candidate folder")
                    return None
            
            # Download file from S3
            file_obj = s3_client_boto.get_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key
            )
            file_content = file_obj['Body'].read()
            
            # 3. Extract text
            text = self.file_processor.extract_text(file_content, file_name)
            
            # 4. Generate embedding
            embedding = self.bedrock.generate_embedding(text)
            
            # 5. Create document
            document = {
                "id": resume_id,
                "name": file_name,
                "text_excerpt": text[:500],
                "full_text": text,
                "embeddings": embedding,
                "metadata": {},
                "s3_url": f"s3://{settings.S3_BUCKET_NAME}/{s3_key}",
                "s3_key": s3_key,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # 6. Index in OpenSearch
            self.opensearch.index_document(
                index_name=self.INDEX_NAME,
                doc_id=resume_id,
                document=document
            )
            
            logger.info(f"Processed and indexed resume {resume_id} from S3")
            return document
            
        except Exception as e:
            logger.error(f"Error getting resume from S3: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def get_resume_from_s3_by_key(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Get resume from S3 by S3 key and process it (extract text, generate embedding)
        
        This is used when we have the S3 key directly (e.g., from frontend).
        """
        try:
            from app.core.config import settings
            
            logger.info(f"Getting resume from S3 by key: {s3_key}")
            
            # First, try to find in OpenSearch by s3_key
            if not settings.USE_MOCK:
                try:
                    # Search OpenSearch for document with this s3_key
                    # s3_key is a keyword field, so use term query
                    search_query = {
                        "query": {
                            "term": {
                                "s3_key": s3_key
                            }
                        },
                        "size": 1
                    }
                    response = self.opensearch.client.search(
                        index=self.INDEX_NAME,
                        body=search_query
                    )
                    
                    if response['hits']['total']['value'] > 0:
                        hit = response['hits']['hits'][0]
                        resume = hit['_source']
                        resume['_id'] = hit['_id']
                        # Verify s3_key matches exactly
                        if resume.get('s3_key') == s3_key:
                            logger.info(f"Found resume in OpenSearch by s3_key: {s3_key}, resume_id: {resume.get('id')}")
                            return resume
                        else:
                            logger.warning(f"Found resume but s3_key doesn't match: {resume.get('s3_key')} != {s3_key}")
                except Exception as search_error:
                    logger.warning(f"Failed to search OpenSearch by s3_key: {search_error}")
                    import traceback
                    logger.debug(traceback.format_exc())
            
            # If not found in OpenSearch, get from S3 and process
            logger.info(f"Resume not in OpenSearch, processing from S3: {s3_key}")
            
            # Use s3_client if available, otherwise use boto3 directly
            if hasattr(self.s3, 'client') and self.s3.client:
                s3_client_boto = self.s3.client
            else:
                import boto3
                s3_client_boto = boto3.client('s3', region_name=settings.AWS_REGION)
            
            file_name = s3_key.split('/')[-1]
            
            # Download file from S3
            try:
                file_obj = s3_client_boto.get_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=s3_key
                )
                file_content = file_obj['Body'].read()
                logger.info(f"Downloaded file from S3: {s3_key}, size: {len(file_content)} bytes")
            except Exception as e:
                logger.error(f"Failed to download file from S3: {s3_key}, error: {e}")
                return None
            
            # Get resume_id from metadata if available
            resume_id = None
            try:
                obj_metadata = s3_client_boto.head_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=s3_key
                )
                metadata = obj_metadata.get('Metadata', {})
                resume_id = metadata.get('resume_id', '')
            except Exception as meta_error:
                logger.warning(f"Failed to get metadata for {s3_key}: {meta_error}")
            
            # If no resume_id in metadata, generate one from filename
            if not resume_id:
                # Generate a stable resume_id from filename
                import hashlib
                resume_id = hashlib.md5(s3_key.encode()).hexdigest()
                logger.info(f"No resume_id in metadata, generated ID from s3_key: {resume_id}")
            
            # Extract text
            logger.info(f"Extracting text from file: {file_name}")
            text = self.file_processor.extract_text(file_content, file_name)
            
            if not text or len(text.strip()) == 0:
                logger.error(f"Failed to extract text from file: {file_name}")
                return None
            
            logger.info(f"Extracted text length: {len(text)} characters")
            
            # Generate embedding
            logger.info(f"Generating embedding for resume: {resume_id}")
            embedding = self.bedrock.generate_embedding(text)
            logger.info(f"Generated embedding dimension: {len(embedding)}")
            
            # Create document
            document = {
                "id": resume_id,
                "name": file_name,
                "text_excerpt": text[:500],
                "full_text": text,
                "embeddings": embedding,
                "metadata": {},
                "s3_url": f"s3://{settings.S3_BUCKET_NAME}/{s3_key}",
                "s3_key": s3_key,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Index in OpenSearch
            logger.info(f"Indexing resume {resume_id} in OpenSearch")
            self.opensearch.index_document(
                index_name=self.INDEX_NAME,
                doc_id=resume_id,
                document=document
            )
            
            logger.info(f"Successfully processed and indexed resume {resume_id} from S3 key: {s3_key}")
            return document
            
        except Exception as e:
            logger.error(f"Error getting resume from S3 by key: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None


resume_repository = ResumeRepository()

