"""
Test Bedrock Rerank Model
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
from app.core.logging import get_logger

logger = get_logger(__name__)

def test_rerank():
    """Test Bedrock rerank functionality"""
    print("=" * 60)
    print("  Bedrock Rerank Model Test")
    print("=" * 60)
    print()
    
    # Display configuration
    print("Configuration:")
    print(f"  USE_MOCK: {settings.USE_MOCK}")
    print(f"  BEDROCK_REGION: {settings.BEDROCK_REGION}")
    print(f"  BEDROCK_RERANK_MODEL: {settings.BEDROCK_RERANK_MODEL}")
    print()
    
    if settings.USE_MOCK:
        print("[INFO] MOCK MODE: Testing mock rerank")
        print()
        
        # Test mock rerank
        query = "Looking for a Full Stack Developer with React and Python experience"
        candidates = [
            {
                "id": "job_1",
                "title": "Full Stack Developer",
                "text_excerpt": "We are looking for a Full Stack Developer with React, Node.js, and Python experience..."
            },
            {
                "id": "job_2",
                "title": "Frontend Developer",
                "text_excerpt": "Frontend Developer position requiring React and TypeScript..."
            },
            {
                "id": "job_3",
                "title": "Backend Developer",
                "text_excerpt": "Backend Developer with Python and Django experience needed..."
            }
        ]
        
        try:
            results = bedrock_client.rerank_candidates(query, candidates, top_k=3)
            print(f"[OK] Mock rerank completed: {len(results)} results")
            for i, result in enumerate(results, 1):
                print(f"  [{i}] {result.get('title', 'N/A')}")
                print(f"      Score: {result.get('rerank_score', 0):.2f}")
                print(f"      Reason: {result.get('rerank_reason', 'N/A')}")
            print()
            print("[SUCCESS] Mock rerank test passed!")
            return True
        except Exception as e:
            print(f"[ERROR] Mock rerank failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print("Testing Real Bedrock Rerank:")
        print()
        
        # Test data
        query = "กำลังหางาน Full Stack Developer ที่มีประสบการณ์ React และ Python"
        candidates = [
            {
                "id": "job_fullstack_001",
                "title": "Full Stack Developer",
                "text_excerpt": "ตำแหน่ง Full Stack Developer ต้องการประสบการณ์ React, Node.js, Python, และ PostgreSQL. ทำงานกับทีมพัฒนาแอปพลิเคชัน web และ mobile..."
            },
            {
                "id": "job_frontend_001",
                "title": "Frontend Developer",
                "text_excerpt": "ตำแหน่ง Frontend Developer ต้องการประสบการณ์ React, TypeScript, และ CSS. ทำงานกับทีมออกแบบ UI/UX..."
            },
            {
                "id": "job_backend_001",
                "title": "Backend Developer",
                "text_excerpt": "ตำแหน่ง Backend Developer ต้องการประสบการณ์ Python, Django, และ PostgreSQL. ทำงานกับทีมพัฒนา API..."
            },
            {
                "id": "job_data_001",
                "title": "Data Analyst",
                "text_excerpt": "ตำแหน่ง Data Analyst ต้องการประสบการณ์ Python, SQL, และ Excel. วิเคราะห์ข้อมูลและสร้างรายงาน..."
            }
        ]
        
        print(f"Query: {query}")
        print(f"Candidates: {len(candidates)} items")
        print()
        
        try:
            print("Calling Bedrock rerank API...")
            results = bedrock_client.rerank_candidates(query, candidates, top_k=3)
            
            print()
            print("[SUCCESS] Rerank completed!")
            print()
            print("Results:")
            print("-" * 60)
            
            for i, result in enumerate(results, 1):
                print(f"[{i}] {result.get('title', 'N/A')}")
                print(f"    ID: {result.get('id', 'N/A')}")
                print(f"    Rerank Score: {result.get('rerank_score', 0):.2f} ({result.get('rerank_score', 0)*100:.1f}%)")
                print(f"    Reason: {result.get('rerank_reason', 'N/A')}")
                
                highlighted = result.get('highlighted_skills', [])
                if highlighted:
                    print(f"    Highlighted Skills: {', '.join(highlighted)}")
                
                gaps = result.get('gaps', [])
                if gaps:
                    print(f"    Gaps: {', '.join(gaps)}")
                
                questions = result.get('recommended_questions', [])
                if questions:
                    print(f"    Recommended Questions: {len(questions)} questions")
                    for q in questions[:2]:  # Show first 2
                        print(f"      - {q}")
                
                print()
            
            print("[SUCCESS] Bedrock rerank test passed!")
            return True
            
        except Exception as e:
            print()
            print(f"[ERROR] Rerank failed: {e}")
            import traceback
            traceback.print_exc()
            print()
            print("Troubleshooting:")
            print("  1. Check BEDROCK_RERANK_MODEL in .env file")
            print("  2. Verify AWS credentials have Bedrock access")
            print("  3. Check if model is available in region:", settings.BEDROCK_REGION)
            print("  4. Verify model ID format: us.amazon.nova-lite-v1:0")
            return False

if __name__ == "__main__":
    success = test_rerank()
    sys.exit(0 if success else 1)

