"""
OpenSearch Client for Vector Search
"""
from opensearchpy import OpenSearch, RequestsHttpConnection
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import OpenSearchError

logger = get_logger(__name__)


class OpenSearchClient:
    """OpenSearch client for vector search operations"""
    
    def __init__(self):
        if settings.USE_MOCK:
            self.client = None
            self._mock_data = {
                "jobs_index": [],
                "resumes_index": []
            }
            logger.info("OpenSearchClient initialized in MOCK mode")
        else:
            self.client = OpenSearch(
                hosts=[{'host': settings.OPENSEARCH_ENDPOINT.replace('https://', '').replace('http://', ''), 'port': 443}],
                http_auth=(settings.OPENSEARCH_USERNAME, settings.OPENSEARCH_PASSWORD),
                use_ssl=settings.OPENSEARCH_USE_SSL,
                verify_certs=settings.OPENSEARCH_VERIFY_CERTS,
                connection_class=RequestsHttpConnection
            )
            logger.info(f"OpenSearchClient initialized for endpoint: {settings.OPENSEARCH_ENDPOINT}")
    
    def create_index_if_not_exists(self, index_name: str, mapping: Dict[str, Any]) -> bool:
        """Create index if it doesn't exist"""
        if settings.USE_MOCK:
            if index_name not in self._mock_data:
                self._mock_data[index_name] = []
            logger.info(f"MOCK: Created/verified index {index_name}")
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
            document['_id'] = doc_id
            self._mock_data[index_name].append(document)
            logger.info(f"MOCK: Indexed document {doc_id} in {index_name}")
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
            logger.info(f"MOCK: Vector search in {index_name} (top_k={top_k})")
            results = self._mock_data.get(index_name, [])[:top_k]
            # Add mock scores
            for i, result in enumerate(results):
                result['_score'] = 0.95 - (i * 0.05)
            return results
        
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
            for doc in self._mock_data.get(index_name, []):
                if doc.get('_id') == doc_id:
                    return doc
            return None
        
        try:
            response = self.client.get(index=index_name, id=doc_id)
            return response['_source']
        except Exception as e:
            logger.error(f"Error getting document {doc_id}: {e}")
            return None


# Singleton instance
opensearch_client = OpenSearchClient()

