"""
Test Full Matching Flow
ทดสอบ flow ทั้งหมด: Embedding → Vector Search → LLM Reranking
"""
import sys
import os
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.core.config import settings
from app.clients.bedrock_client import bedrock_client
from app.clients.opensearch_client import opensearch_client
from app.services.matching_service import matching_service
from app.core.logging import get_logger

logger = get_logger(__name__)

def test_full_flow():
    """Test complete matching flow"""
    print("=" * 70)
    print("  Full Matching Flow Test")
    print("  Embedding → Vector Search → LLM Reranking")
    print("=" * 70)
    print()
    
    # Display configuration
    print("Configuration:")
    print(f"  USE_MOCK: {settings.USE_MOCK}")
    print(f"  BEDROCK_REGION: {settings.BEDROCK_REGION}")
    print(f"  BEDROCK_EMBEDDING_MODEL: {settings.BEDROCK_EMBEDDING_MODEL}")
    print(f"  BEDROCK_RERANK_MODEL: {settings.BEDROCK_RERANK_MODEL}")
    print(f"  OPENSEARCH_ENDPOINT: {settings.OPENSEARCH_ENDPOINT}")
    print()
    
    # Test data
    resume_text = """
    ประวัติส่วนตัว
    ชื่อ: สมชาย ใจดี
    ตำแหน่ง: Full Stack Developer
    
    ประสบการณ์การทำงาน:
    - พัฒนาเว็บแอปพลิเคชันด้วย React และ Node.js 3 ปี
    - พัฒนา Backend API ด้วย Python (Django, FastAPI) 2 ปี
    - ใช้งาน PostgreSQL และ MongoDB
    - มีประสบการณ์กับ AWS (S3, Lambda, API Gateway)
    
    ทักษะ:
    - Frontend: React, TypeScript, HTML/CSS
    - Backend: Python, Node.js, Django, FastAPI
    - Database: PostgreSQL, MongoDB
    - Cloud: AWS, Docker
    """
    
    print("=" * 70)
    print("  Step 1: Generate Embedding")
    print("=" * 70)
    print()
    print(f"Resume text length: {len(resume_text)} characters")
    print()
    
    try:
        print("Generating embedding...")
        resume_embedding = bedrock_client.generate_embedding(resume_text)
        print(f"[OK] Generated embedding")
        print(f"  Dimension: {len(resume_embedding)}")
        print(f"  Sample values: {resume_embedding[:5]}...")
        print()
    except Exception as e:
        print(f"[FAIL] Failed to generate embedding: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("=" * 70)
    print("  Step 2: Vector Search")
    print("=" * 70)
    print()
    
    try:
        # Check if jobs exist in index
        if not settings.USE_MOCK:
            try:
                stats = opensearch_client.client.indices.stats(index="jobs_index")
                doc_count = stats['indices']['jobs_index']['total']['docs']['count']
                print(f"Jobs in index: {doc_count}")
                if doc_count == 0:
                    print("[WARNING] No jobs in index! Please add jobs first.")
                    print()
            except Exception as e:
                print(f"[WARNING] Could not check jobs count: {e}")
                print()
        
        print("Performing vector search...")
        candidates = opensearch_client.vector_search(
            index_name="jobs_index",
            query_vector=resume_embedding,
            top_k=50
        )
        
        if not candidates:
            print("[WARNING] No candidates found from vector search")
            print("  This might be because:")
            print("  1. No jobs in index")
            print("  2. ANN structure not built yet")
            print("  3. Vector search not working")
            print()
            return False
        
        print(f"[OK] Vector search completed")
        print(f"  Found {len(candidates)} candidates")
        if candidates:
            print(f"  Top candidate score: {candidates[0].get('_score', 'N/A')}")
            print(f"  Top candidate title: {candidates[0].get('title', 'N/A')}")
        print()
        
    except Exception as e:
        print(f"[FAIL] Vector search failed: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("Possible issues:")
        print("  1. ANN structure not built (wait a few minutes)")
        print("  2. No jobs in index")
        print("  3. OpenSearch connection issue")
        return False
    
    print("=" * 70)
    print("  Step 3: Prepare Candidates for Reranking")
    print("=" * 70)
    print()
    
    try:
        candidates_for_rerank = []
        for i, candidate in enumerate(candidates[:10]):  # Use top 10 for rerank test
            candidates_for_rerank.append({
                "candidate_index": i,
                "title": candidate.get("title", "N/A"),
                "text_excerpt": candidate.get("text_excerpt", candidate.get("description", ""))[:200],
                "metadata": candidate.get("metadata", {}),
                "vector_score": candidate.get("_score", 0.0),
                "job_id": candidate.get("_id", "")
            })
        
        print(f"[OK] Prepared {len(candidates_for_rerank)} candidates for reranking")
        print(f"  Sample candidates:")
        for i, c in enumerate(candidates_for_rerank[:3], 1):
            print(f"    [{i}] {c['title']} (score: {c['vector_score']:.4f})")
        print()
        
    except Exception as e:
        print(f"[FAIL] Failed to prepare candidates: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("=" * 70)
    print("  Step 4: LLM Reranking")
    print("=" * 70)
    print()
    
    try:
        query_summary = f"Resume Summary: {resume_text[:500]}..."
        print(f"Query: {query_summary[:100]}...")
        print(f"Candidates: {len(candidates_for_rerank)} items")
        print()
        print("Calling Bedrock rerank API...")
        
        reranked = bedrock_client.rerank_candidates(
            query=query_summary,
            candidates=candidates_for_rerank,
            top_k=5
        )
        
        if not reranked:
            print("[WARNING] No reranked results")
            return False
        
        print(f"[OK] Reranking completed")
        print(f"  Returned {len(reranked)} reranked results")
        print()
        print("Reranked Results:")
        print("-" * 70)
        for i, item in enumerate(reranked, 1):
            print(f"[{i}] {item.get('title', 'N/A')}")
            print(f"    Vector Score: {item.get('vector_score', 0):.4f}")
            print(f"    Rerank Score: {item.get('rerank_score', 0):.4f} ({item.get('rerank_score', 0)*100:.1f}%)")
            print(f"    Reason: {item.get('rerank_reason', 'N/A')[:100]}...")
            if item.get('highlighted_skills'):
                print(f"    Skills: {', '.join(item.get('highlighted_skills', [])[:5])}")
            print()
        
    except Exception as e:
        print(f"[FAIL] Reranking failed: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("Possible issues:")
        print("  1. Bedrock rerank model not available")
        print("  2. AWS credentials issue")
        print("  3. Model region mismatch")
        return False
    
    print("=" * 70)
    print("  Step 5: Full Flow Test (Matching Service)")
    print("=" * 70)
    print()
    
    try:
        print("Testing complete matching service flow...")
        results = matching_service.search_jobs_by_resume(
            resume_text=resume_text,
            resume_id="test_resume_001",
            top_k_initial=50,
            top_k_final=5
        )
        
        if not results:
            print("[WARNING] No results from matching service")
            return False
        
        print(f"[OK] Full flow completed successfully!")
        print(f"  Returned {len(results)} final results")
        print()
        print("Final Results:")
        print("-" * 70)
        for i, result in enumerate(results, 1):
            print(f"[{i}] {result.get('job_title', 'N/A')}")
            print(f"    Match Score: {result.get('match_score', 0):.4f}")
            print(f"    Rerank Score: {result.get('rerank_score', 0):.4f} ({result.get('rerank_score', 0)*100:.1f}%)")
            print(f"    Reasons: {result.get('reasons', 'N/A')[:100]}...")
            print()
        
        print()
        print("[SUCCESS] Full flow test passed!")
        return True
        
    except Exception as e:
        print(f"[FAIL] Full flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_full_flow()
    sys.exit(0 if success else 1)

