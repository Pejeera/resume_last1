"""
Script to create OpenSearch indices
Run this script to initialize OpenSearch indices for jobs and resumes
"""
import json
import os
from opensearchpy import OpenSearch, RequestsHttpConnection
from app.core.config import settings

def create_indices():
    """Create OpenSearch indices with proper mappings"""
    
    # Load mappings
    with open('infra/opensearch_index_mapping.json', 'r') as f:
        mappings = json.load(f)
    
    # Initialize OpenSearch client
    if settings.USE_MOCK:
        print("MOCK MODE: Skipping OpenSearch index creation")
        return
    
    client = OpenSearch(
        hosts=[{'host': settings.OPENSEARCH_ENDPOINT.replace('https://', '').replace('http://', ''), 'port': 443}],
        http_auth=(settings.OPENSEARCH_USERNAME, settings.OPENSEARCH_PASSWORD),
        use_ssl=settings.OPENSEARCH_USE_SSL,
        verify_certs=settings.OPENSEARCH_VERIFY_CERTS,
        connection_class=RequestsHttpConnection
    )
    
    # Create jobs_index
    jobs_mapping = mappings['jobs_index']
    if client.indices.exists(index='jobs_index'):
        print("jobs_index already exists. Deleting...")
        client.indices.delete(index='jobs_index')
    
    client.indices.create(index='jobs_index', body=jobs_mapping)
    print("✅ Created jobs_index")
    
    # Create resumes_index
    resumes_mapping = mappings['resumes_index']
    if client.indices.exists(index='resumes_index'):
        print("resumes_index already exists. Deleting...")
        client.indices.delete(index='resumes_index')
    
    client.indices.create(index='resumes_index', body=resumes_mapping)
    print("✅ Created resumes_index")
    
    print("\n✅ All indices created successfully!")

if __name__ == "__main__":
    create_indices()

