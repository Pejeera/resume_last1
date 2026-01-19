"""
Script to check OpenSearch indices and verify resume indexing
"""
import sys
import json
import io
import urllib3
from app.clients.opensearch_client import opensearch_client
from app.core.config import settings
from app.core.logging import get_logger

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Disable SSL warnings if needed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_logger(__name__)


def check_indices():
    """1. Check what indices exist"""
    print("\n" + "="*60)
    print("1. ตรวจสอบ indices ที่มีอยู่")
    print("="*60)
    
    if settings.USE_MOCK:
        print("[WARNING] อยู่ในโหมด MOCK - ไม่สามารถเช็ค OpenSearch จริงได้")
        print(f"Mock indices: {list(opensearch_client._mock_data_storage.keys())}")
        return []
    
    try:
        # Get all indices
        indices = opensearch_client.client.cat.indices(format='json')
        
        print(f"\nพบ {len(indices)} indices:")
        for idx in indices:
            print(f"  - {idx['index']} (docs: {idx.get('docs.count', 'N/A')}, size: {idx.get('store.size', 'N/A')})")
        
        # Filter resume-related indices
        resume_indices = [idx['index'] for idx in indices if 'resume' in idx['index'].lower()]
        
        if resume_indices:
            print(f"\n[OK] พบ resume indices: {resume_indices}")
        else:
            print("\n[WARNING] ไม่พบ resume indices")
        
        return [idx['index'] for idx in indices]
        
    except Exception as e:
        print(f"[ERROR] Error checking indices: {e}")
        return []


def check_resume_exists(index_name: str, resume_id: str):
    """2. Check if resume_id exists in OpenSearch"""
    print("\n" + "="*60)
    print(f"2. ตรวจสอบว่า resume_id อยู่ใน {index_name} หรือไม่")
    print("="*60)
    print(f"Resume ID: {resume_id}")
    
    if settings.USE_MOCK:
        print("[WARNING] อยู่ในโหมด MOCK")
        mock_docs = opensearch_client._mock_data_storage.get(index_name, [])
        found = any(doc.get('resume_id') == resume_id or doc.get('_id') == resume_id for doc in mock_docs)
        if found:
            print("[OK] พบ resume ใน mock storage")
        else:
            print("[NO] ไม่พบ resume ใน mock storage")
        return found
    
    try:
        # Try with keyword field first
        query = {
            "query": {
                "term": {
                    "resume_id.keyword": resume_id
                }
            }
        }
        
        try:
            response = opensearch_client.client.search(index=index_name, body=query)
            total = response['hits']['total']
            
            if isinstance(total, dict):
                total_value = total.get('value', 0)
            else:
                total_value = total
            
            if total_value > 0:
                print(f"[OK] พบ resume (total: {total_value})")
                print(f"\nDocument:")
                print(json.dumps(response['hits']['hits'][0]['_source'], indent=2, ensure_ascii=False))
                return True
            else:
                print("[NO] ไม่พบ resume (total: 0)")
                print("\nลองใช้ match query แทน...")
                
                # Try with match query
                query_match = {
                    "query": {
                        "match": {
                            "resume_id": resume_id
                        }
                    }
                }
                response_match = opensearch_client.client.search(index=index_name, body=query_match)
                total_match = response_match['hits']['total']
                
                if isinstance(total_match, dict):
                    total_match_value = total_match.get('value', 0)
                else:
                    total_match_value = total_match
                
                if total_match_value > 0:
                    print(f"[OK] พบ resume ด้วย match query (total: {total_match_value})")
                    print(f"\nDocument:")
                    print(json.dumps(response_match['hits']['hits'][0]['_source'], indent=2, ensure_ascii=False))
                    return True
                else:
                    print("[NO] ไม่พบ resume แม้ใช้ match query")
                    return False
                    
        except Exception as e:
            print(f"[ERROR] Error searching: {e}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return False


def check_vector_fields(index_name: str):
    """3. Check if index has vector/embedding fields"""
    print("\n" + "="*60)
    print(f"3. ตรวจสอบว่า {index_name} มี vector fields หรือไม่")
    print("="*60)
    
    if settings.USE_MOCK:
        print("[WARNING] อยู่ในโหมด MOCK")
        return False
    
    try:
        # Get a sample document to check fields
        query = {
            "_source": ["resume_id", "embedding", "embeddings", "vector", "resume_vector", "content"],
            "query": {
                "match_all": {}
            },
            "size": 1
        }
        
        response = opensearch_client.client.search(index=index_name, body=query)
        
        if response['hits']['total']['value'] > 0:
            doc = response['hits']['hits'][0]['_source']
            print(f"\nFields ใน document:")
            for key in doc.keys():
                print(f"  - {key}: {type(doc[key]).__name__}")
            
            # Check for vector fields
            vector_fields = ['embedding', 'embeddings', 'vector', 'resume_vector']
            found_vector_fields = [field for field in vector_fields if field in doc]
            
            if found_vector_fields:
                print(f"\n[OK] พบ vector fields: {found_vector_fields}")
                for field in found_vector_fields:
                    value = doc[field]
                    if isinstance(value, list):
                        print(f"  - {field}: list with {len(value)} dimensions")
                    else:
                        print(f"  - {field}: {type(value).__name__}")
                return True
            else:
                print(f"\n[NO] ไม่พบ vector fields ใน document")
                print(f"   (ตรวจสอบ: {vector_fields})")
                return False
        else:
            print("[NO] ไม่มี documents ใน index นี้")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return False


def check_mapping(index_name: str):
    """4. Check index mapping to verify it's a vector index"""
    print("\n" + "="*60)
    print(f"4. ตรวจสอบ mapping ของ {index_name}")
    print("="*60)
    
    if settings.USE_MOCK:
        print("[WARNING] อยู่ในโหมด MOCK")
        return False
    
    try:
        mapping = opensearch_client.client.indices.get_mapping(index=index_name)
        index_mapping = mapping[index_name]['mappings']['properties']
        
        print(f"\nMapping fields:")
        for field_name, field_config in index_mapping.items():
            field_type = field_config.get('type', 'N/A')
            print(f"  - {field_name}: {field_type}")
            
            # Check for vector types
            if field_type in ['knn_vector', 'dense_vector']:
                dimension = field_config.get('dimension', 'N/A')
                print(f"    [OK] Vector field! (dimension: {dimension})")
        
        # Check specifically for vector fields
        vector_fields = {}
        for field_name, field_config in index_mapping.items():
            field_type = field_config.get('type', '')
            if field_type in ['knn_vector', 'dense_vector']:
                vector_fields[field_name] = {
                    'type': field_type,
                    'dimension': field_config.get('dimension', 'N/A')
                }
        
        if vector_fields:
            print(f"\n[OK] พบ vector fields ใน mapping:")
            for field_name, config in vector_fields.items():
                print(f"  - {field_name}: {config['type']} (dimension: {config['dimension']})")
            return True
        else:
            print(f"\n[NO] ไม่พบ vector fields ใน mapping")
            print("   (ตรวจสอบ: knn_vector หรือ dense_vector)")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return False


def test_vector_search(index_name: str):
    """5. Test vector search directly"""
    print("\n" + "="*60)
    print(f"5. ทดสอบ vector search ใน {index_name}")
    print("="*60)
    
    if settings.USE_MOCK:
        print("[WARNING] อยู่ในโหมด MOCK")
        return False
    
    try:
        # Create a dummy vector (1536 dimensions for typical embeddings)
        dummy_vector = [0.01] * 1536
        
        # Try KNN search
        query = {
            "size": 3,
            "query": {
                "knn": {
                    "embeddings": {
                        "vector": dummy_vector,
                        "k": 3
                    }
                }
            }
        }
        
        print("ลองใช้ field 'embeddings'...")
        try:
            response = opensearch_client.client.search(index=index_name, body=query)
            print(f"[OK] Vector search สำเร็จ! (พบ {response['hits']['total']['value']} results)")
            return True
        except Exception as knn_error:
            error_msg = str(knn_error)
            print(f"[WARNING] KNN search with 'embeddings' failed: {error_msg}")
            
            # Try with 'embedding' field
            print("\nลองใช้ field 'embedding'...")
            query_embedding = {
                "size": 3,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": dummy_vector,
                            "k": 3
                        }
                    }
                }
            }
            try:
                response = opensearch_client.client.search(index=index_name, body=query_embedding)
                print(f"[OK] Vector search สำเร็จ! (พบ {response['hits']['total']['value']} results)")
                return True
            except Exception as e2:
                print(f"[ERROR] Vector search failed: {e2}")
                return False
                
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return False


def main():
    """Main function"""
    print("\n" + "="*60)
    print("OpenSearch Index Checker")
    print("="*60)
    
    # Get resume_id from command line or use default
    resume_id = sys.argv[1] if len(sys.argv) > 1 else "c3a74273-816f-4dd6-bd50-24e8d8c6d8f7"
    
    # Check if we should skip SSL verification (for testing)
    skip_ssl = len(sys.argv) > 2 and sys.argv[2].lower() == "--skip-ssl"
    
    if skip_ssl:
        print("\n[WARNING] SSL verification disabled for testing")
        # Temporarily disable SSL verification in the client
        if hasattr(opensearch_client, 'client') and opensearch_client.client:
            # Try to disable SSL verification
            try:
                opensearch_client.client.transport.connection_pool.connection_kwargs['verify'] = False
            except:
                pass
    
    print(f"\nConfiguration:")
    print(f"  - USE_MOCK: {settings.USE_MOCK}")
    print(f"  - OPENSEARCH_ENDPOINT: {settings.OPENSEARCH_ENDPOINT}")
    print(f"  - Resume ID to check: {resume_id}")
    
    # 1. Check indices
    indices = check_indices()
    
    # Find resume index
    resume_index = None
    if not settings.USE_MOCK:
        resume_indices = [idx for idx in indices if 'resume' in idx.lower()]
        if resume_indices:
            resume_index = resume_indices[0]
            print(f"\nใช้ index: {resume_index}")
        else:
            print("\nไม่พบ resume index - จะลองใช้ชื่อ 'resumes_index'")
            resume_index = "resumes_index"
    else:
        resume_index = "resumes_index"
    
    if resume_index:
        # 2. Check if resume exists
        resume_exists = check_resume_exists(resume_index, resume_id)
        
        # 3. Check vector fields
        has_vector_fields = check_vector_fields(resume_index)
        
        # 4. Check mapping
        has_vector_mapping = check_mapping(resume_index)
        
        # 5. Test vector search (only if mapping is correct)
        if has_vector_mapping:
            test_vector_search(resume_index)
        
        # Summary
        print("\n" + "="*60)
        print("สรุปผล")
        print("="*60)
        print(f"  Index: {resume_index}")
        print(f"  Resume exists: {'YES' if resume_exists else 'NO'}")
        print(f"  Has vector fields: {'YES' if has_vector_fields else 'NO'}")
        print(f"  Has vector mapping: {'YES' if has_vector_mapping else 'NO'}")
        
        if resume_exists and has_vector_fields and has_vector_mapping:
            print("\n[OK] พร้อม search แล้ว!")
        else:
            print("\n[WARNING] ยังไม่พร้อม - ตรวจสอบปัญหาด้านบน")
    else:
        print("\n[ERROR] ไม่สามารถหา resume index ได้")


if __name__ == "__main__":
    main()

