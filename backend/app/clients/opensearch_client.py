"""
OpenSearch Client for Vector Search
"""
from opensearchpy import OpenSearch, RequestsHttpConnection
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
import boto3
from requests_aws4auth import AWS4Auth

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import OpenSearchError

logger = get_logger(__name__)


class OpenSearchClient:
    """OpenSearch client for vector search operations"""
    
    # Class-level mock data storage to persist across instances
    _mock_data_storage = {
        "jobs_index": [],
        "resumes_index": []
    }
    
    def __init__(self):
        if settings.USE_MOCK:
            self.client = None
            # Load jobs from S3 on initialization
            self._load_jobs_from_s3()
            logger.info("OpenSearchClient initialized in MOCK mode")
        else:
            # Parse endpoint URL properly
            endpoint = settings.OPENSEARCH_ENDPOINT
            # Remove protocol
            host = endpoint.replace('https://', '').replace('http://', '')
            # Remove port if included in URL
            if ':' in host:
                host, port_str = host.rsplit(':', 1)
                try:
                    port = int(port_str)
                except ValueError:
                    port = 443 if endpoint.startswith('https://') else 80
            else:
                port = 443 if endpoint.startswith('https://') else 80
            
            # Use credentials from settings (loaded from .env) instead of default boto3 session
            # This ensures we use the credentials specified in .env file
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                # Use credentials from settings (.env)
                awsauth = AWS4Auth(
                    settings.AWS_ACCESS_KEY_ID,
                    settings.AWS_SECRET_ACCESS_KEY,
                    opensearch_region,
                    'es'
                )
            else:
                # Fallback to default boto3 session (for Lambda/EC2 with IAM roles)
                credentials = boto3.Session().get_credentials()
                if credentials:
                    awsauth = AWS4Auth(
                        credentials.access_key,
                        credentials.secret_key,
                        opensearch_region,
                        'es',
                        session_token=credentials.token
                    )
                else:
                    raise ValueError("No AWS credentials found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env file or configure AWS credentials.")
            
            self.client = OpenSearch(
                hosts=[{'host': host, 'port': port}],
                http_auth=awsauth,
                use_ssl=settings.OPENSEARCH_USE_SSL,
                verify_certs=settings.OPENSEARCH_VERIFY_CERTS,
                connection_class=RequestsHttpConnection
            )
            logger.info(f"OpenSearchClient initialized for endpoint: {settings.OPENSEARCH_ENDPOINT} (using IAM authentication)")
    
    def _load_jobs_from_s3(self):
        """Load jobs from S3 into mock storage"""
        if not settings.USE_MOCK:
            return
        
        try:
            from app.clients.s3_client import s3_client
            jobs_data = s3_client.load_jobs_data()
            if jobs_data:
                OpenSearchClient._mock_data_storage["jobs_index"] = jobs_data
                logger.info(f"Loaded {len(jobs_data)} jobs from S3 into mock storage")
        except Exception as e:
            logger.error(f"Failed to load jobs from S3: {e}")
    
    def _save_jobs_to_s3(self):
        """Save jobs from mock storage to S3"""
        if not settings.USE_MOCK:
            return
        
        try:
            from app.clients.s3_client import s3_client
            jobs_data = OpenSearchClient._mock_data_storage.get("jobs_index", [])
            if jobs_data:
                s3_client.save_jobs_data(jobs_data)
        except Exception as e:
            logger.error(f"Failed to save jobs to S3: {e}")
    
    def create_index_if_not_exists(self, index_name: str, mapping: Dict[str, Any]) -> bool:
        """Create index if it doesn't exist"""
        if settings.USE_MOCK:
            if index_name not in OpenSearchClient._mock_data_storage:
                OpenSearchClient._mock_data_storage[index_name] = []
            logger.info(f"MOCK: Created/verified index {index_name}")
            # Save to S3 after creating index (for jobs only)
            if index_name == "jobs_index":
                self._save_jobs_to_s3()
            return True
        
        try:
            if not self.client.indices.exists(index=index_name):
                self.client.indices.create(index=index_name, body=mapping)
                logger.info(f"Created index: {index_name}")
            else:
                logger.info(f"Index {index_name} already exists")
            return True
        except Exception as e:
            logger.error(f"Error creating index {index_name}: {e}")
            raise OpenSearchError(f"Failed to create index: {str(e)}")
    
    def index_document(self, index_name: str, doc_id: str, document: Dict[str, Any]) -> bool:
        """Index a document"""
        if settings.USE_MOCK:
            # Make a copy to avoid modifying the original
            doc_copy = document.copy()
            doc_copy['_id'] = doc_id
            if index_name not in OpenSearchClient._mock_data_storage:
                OpenSearchClient._mock_data_storage[index_name] = []
            OpenSearchClient._mock_data_storage[index_name].append(doc_copy)
            logger.info(f"MOCK: Indexed document {doc_id} in {index_name} (total: {len(OpenSearchClient._mock_data_storage[index_name])})")
            # Save to S3 after indexing (for jobs only)
            if index_name == "jobs_index":
                self._save_jobs_to_s3()
            return True
        
        try:
            self.client.index(index=index_name, id=doc_id, body=document)
            logger.info(f"Indexed document {doc_id} in {index_name}")
            return True
        except Exception as e:
            logger.error(f"Error indexing document: {e}")
            raise OpenSearchError(f"Failed to index document: {str(e)}")
    
    def vector_search(
        self,
        index_name: str,
        query_vector: List[float],
        top_k: int = 50,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search
        
        Args:
            index_name: Name of the index to search
            query_vector: Query embedding vector
            top_k: Number of results to return
            filters: Optional filters
            
        Returns:
            List of search results with scores
        """
        if settings.USE_MOCK:
            # Mock vector search - return mock results
            logger.info(f"MOCK: Vector search in {index_name} (top_k={top_k}, available: {len(self._mock_data_storage.get(index_name, []))})")
            results = self._mock_data_storage.get(index_name, [])[:top_k]
            # Make copies to avoid modifying original
            results_copy = []
            for i, result in enumerate(results):
                result_copy = result.copy()
                result_copy['_score'] = 0.95 - (i * 0.05)
                results_copy.append(result_copy)
            logger.info(f"MOCK: Returning {len(results_copy)} results")
            return results_copy
        
        try:
            query = {
                "size": top_k,
                "query": {
                    "knn": {
                        "embeddings": {
                            "vector": query_vector,
                            "k": top_k
                        }
                    }
                },
                "_source": True
            }
            
            if filters:
                query["query"]["bool"] = {
                    "must": [
                        {"knn": {
                            "embeddings": {
                                "vector": query_vector,
                                "k": top_k
                            }
                        }}
                    ],
                    "filter": filters
                }
            
            response = self.client.search(index=index_name, body=query)
            
            results = []
            for hit in response['hits']['hits']:
                result = hit['_source']
                result['_score'] = hit['_score']
                result['_id'] = hit['_id']
                results.append(result)
            
            logger.info(f"Vector search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            raise OpenSearchError(f"Vector search failed: {str(e)}")
    
    def get_document(self, index_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID"""
        if settings.USE_MOCK:
            for doc in self._mock_data_storage.get(index_name, []):
                if doc.get('_id') == doc_id:
                    return doc.copy()
            return None
        
        try:
            response = self.client.get(index=index_name, id=doc_id)
            return response['_source']
        except Exception as e:
            logger.error(f"Error getting document {doc_id}: {e}")
            return None


# Singleton instance
opensearch_client = OpenSearchClient()

