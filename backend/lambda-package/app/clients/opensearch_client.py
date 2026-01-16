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
            # Remove port if included in URL (we'll always use 443)
            if ':' in host:
                host, _ = host.rsplit(':', 1)
            
            # ⚠️ CRITICAL: Always use port 443 for OpenSearch (HTTPS)
            # Never use port 80 - it will cause authentication failures
            port = 443
            
            # Extract region from endpoint or use configured region
            # OpenSearch endpoint format: search-xxx.REGION.es.amazonaws.com
            if '.es.amazonaws.com' in host or '.aoss.amazonaws.com' in host:
                # Extract region from hostname
                parts = host.split('.')
                if len(parts) >= 2:
                    # Find region in hostname (e.g., ap-southeast-2, us-east-1)
                    opensearch_region = settings.AWS_REGION  # Default
                    for part in parts:
                        if part.startswith('ap-') or part.startswith('us-') or part.startswith('eu-') or part.startswith('sa-') or part.startswith('ca-') or part.startswith('cn-'):
                            opensearch_region = part
                            break
                else:
                    opensearch_region = settings.AWS_REGION
            else:
                opensearch_region = settings.AWS_REGION
            
            # Use credentials from boto3 session (for Lambda/EC2 with IAM roles)
            # This is the correct way for Lambda - uses IAM role credentials
            credentials = boto3.Session().get_credentials()
            if not credentials:
                # Fallback to settings if no IAM role (for local development)
                if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                    awsauth = AWS4Auth(
                        settings.AWS_ACCESS_KEY_ID,
                        settings.AWS_SECRET_ACCESS_KEY,
                        opensearch_region,
                        'es'
                    )
                else:
                    raise ValueError("No AWS credentials found. Please configure IAM role for Lambda or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env file.")
            else:
                # ✅ CORRECT: Use IAM role credentials with session_token (for Lambda)
                awsauth = AWS4Auth(
                    credentials.access_key,
                    credentials.secret_key,
                    opensearch_region,
                    'es',
                    session_token=credentials.token  # ⚠️ CRITICAL: Must include session_token for Lambda
                )
            
            # ✅ CORRECT: OpenSearch client configuration
            # - port: 443 (always HTTPS)
            # - use_ssl: True (always use SSL)
            # - verify_certs: True (verify SSL certificates)
            # - RequestsHttpConnection: Required for AWS4Auth
            self.client = OpenSearch(
                hosts=[{'host': host, 'port': 443}],  # ⚠️ CRITICAL: Always 443
                http_auth=awsauth,
                use_ssl=True,  # ⚠️ CRITICAL: Always True for AWS OpenSearch
                verify_certs=True,  # ⚠️ CRITICAL: Always True for AWS OpenSearch
                connection_class=RequestsHttpConnection  # ⚠️ CRITICAL: Required for AWS4Auth
            )
            
            # Log configuration for debugging
            logger.info(f"OpenSearchClient initialized:")
            logger.info(f"  - Endpoint: {settings.OPENSEARCH_ENDPOINT}")
            logger.info(f"  - Host: {host}")
            logger.info(f"  - Port: {self.client.transport.hosts[0]['port']}")  # Should be 443
            logger.info(f"  - Region: {opensearch_region}")
            logger.info(f"  - Use SSL: True")
            logger.info(f"  - Verify Certs: True")
            logger.info(f"  - Using IAM authentication with session_token")
    
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
            else:
                # Clear mock storage if no jobs found in S3
                OpenSearchClient._mock_data_storage["jobs_index"] = []
                logger.info("No jobs found in S3, cleared mock storage")
        except Exception as e:
            logger.error(f"Failed to load jobs from S3: {e}")
            # Clear mock storage on error
            OpenSearchClient._mock_data_storage["jobs_index"] = []
    
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
            # ✅ CORRECT: Use client.index() method (not requests or urllib3)
            # For OpenSearch 2.x+, use 'document' parameter
            # For older versions, use 'body' parameter
            # Try 'document' first (OpenSearch 2.x+), fallback to 'body' for compatibility
            try:
                self.client.index(index=index_name, id=doc_id, document=document)
            except TypeError:
                # Fallback for older OpenSearch client versions
                self.client.index(index=index_name, id=doc_id, body=document)
            
            logger.info(f"Indexed document {doc_id} in {index_name}")
            return True
        except Exception as e:
            logger.error(f"Error indexing document: {e}")
            logger.error(f"Document ID: {doc_id}, Index: {index_name}")
            logger.error(f"OpenSearch client hosts: {self.client.transport.hosts if hasattr(self.client, 'transport') else 'N/A'}")
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
            # Try KNN search first
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
            
            try:
                response = self.client.search(index=index_name, body=query)
                
                results = []
                for hit in response['hits']['hits']:
                    result = hit['_source']
                    result['_score'] = hit['_score']
                    result['_id'] = hit['_id']
                    results.append(result)
                
                logger.info(f"Vector search returned {len(results)} results")
                return results
                
            except Exception as knn_error:
                error_msg = str(knn_error)
                # If ANN structure not built, fallback to script_score query
                if "not built for ANN search" in error_msg or "ANN" in error_msg:
                    logger.warning(f"ANN structure not ready, using fallback script_score query")
                    
                    # Fallback: Use script_score to calculate cosine similarity manually
                    import math
                    
                    # Calculate query vector norm
                    query_norm = math.sqrt(sum(x * x for x in query_vector))
                    
                    # Script to calculate cosine similarity
                    script_source = f"""
                    double dotProduct = 0.0;
                    double docNorm = 0.0;
                    if (doc['embeddings'].size() != params.queryVector.size()) {{
                        return 0.0;
                    }}
                    for (int i = 0; i < doc['embeddings'].size(); i++) {{
                        dotProduct += doc['embeddings'][i] * params.queryVector[i];
                        docNorm += doc['embeddings'][i] * doc['embeddings'][i];
                    }}
                    double docNormSqrt = Math.sqrt(docNorm);
                    double queryNorm = params.queryNorm;
                    if (docNormSqrt == 0.0 || queryNorm == 0.0) {{
                        return 0.0;
                    }}
                    return dotProduct / (docNormSqrt * queryNorm);
                    """
                    
                    fallback_query = {
                        "size": top_k,
                        "query": {
                            "script_score": {
                                "query": {"match_all": {}},
                                "script": {
                                    "source": script_source,
                                    "params": {
                                        "queryVector": query_vector,
                                        "queryNorm": query_norm
                                    }
                                }
                            }
                        },
                        "_source": True
                    }
                    
                    if filters:
                        fallback_query["query"]["script_score"]["query"] = {"bool": {"filter": filters}}
                    
                    try:
                        response = self.client.search(index=index_name, body=fallback_query)
                        
                        results = []
                        for hit in response['hits']['hits']:
                            result = hit['_source']
                            result['_score'] = hit['_score']
                            result['_id'] = hit['_id']
                            results.append(result)
                        
                        # Sort by score descending
                        results.sort(key=lambda x: x.get('_score', 0), reverse=True)
                        results = results[:top_k]
                        
                        logger.info(f"Fallback vector search returned {len(results)} results")
                        return results
                        
                    except Exception as fallback_error:
                        logger.error(f"Fallback vector search also failed: {fallback_error}")
                        raise OpenSearchError(f"Vector search failed (both KNN and fallback): {str(fallback_error)}")
                else:
                    # Other error, raise it
                    raise
            
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

