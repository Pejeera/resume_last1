"""
Test script for Nova Lite v1 reranking
Tests the Bedrock Nova Lite model directly
"""

import json
import boto3
import sys

# Config
BEDROCK_REGION = "us-east-1"
BEDROCK_RERANK_MODEL = "us.amazon.nova-lite-v1:0"

# Sample resume text
SAMPLE_RESUME = """
Jeera Seedaddee
Software Engineer

Skills:
- Python, JavaScript, React, Node.js
- AWS, Docker, Kubernetes
- Machine Learning, NLP
- Database Design (PostgreSQL, MongoDB)

Experience:
- 5 years of full-stack development
- Built scalable web applications
- Experience with microservices architecture
"""

# Sample job candidates
SAMPLE_JOBS = [
    {
        "index": 0,
        "title": "Full Stack Developer - React & Node.js",
        "description": "Looking for experienced full-stack developer with React and Node.js skills. Must have AWS experience."
    },
    {
        "index": 1,
        "title": "Senior Software Engineer - Python",
        "description": "Senior Python developer needed for backend services. Experience with microservices required."
    },
    {
        "index": 2,
        "title": "Data Engineer - AWS & Big Data",
        "description": "Data engineer position focusing on AWS infrastructure and big data processing."
    }
]

def test_nova_lite():
    """Test Nova Lite v1 reranking"""
    print("=" * 60)
    print("Testing Nova Lite v1 Reranking")
    print("=" * 60)
    print(f"Region: {BEDROCK_REGION}")
    print(f"Model: {BEDROCK_RERANK_MODEL}")
    print()
    
    try:
        # Create Bedrock client
        bedrock_runtime = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        print("[OK] Bedrock client created successfully")
        print()
        
        # Build prompt
        resume_summary = SAMPLE_RESUME[:500] + "..." if len(SAMPLE_RESUME) > 500 else SAMPLE_RESUME
        candidates_text = "\n".join([
            f"{i+1}. {job['title']} - {job['description'][:200]}..."
            for i, job in enumerate(SAMPLE_JOBS)
        ])
        
        rerank_prompt = f"""คุณเป็น AI ที่เชี่ยวชาญในการจับคู่ Resume กับ Job

**Resume Summary:**
{resume_summary}

**รายการตำแหน่งงาน (Jobs):**
{candidates_text}

**งานของคุณ:**
1. วิเคราะห์และจัดอันดับ Top 3 ตำแหน่งงานที่เหมาะสมที่สุดกับ Resume นี้
2. ให้เหตุผลสั้นๆ กระชับ (2-3 ประโยค) ว่าทำไมถึงเหมาะ
3. ระบุจุดเด่น (highlighted_skills) และจุดที่ขาด (gaps) ถ้ามี
4. แนะนำคำถามสำหรับสัมภาษณ์ (recommended_questions_for_interview)

**ข้อกำหนด:**
- ห้ามสร้างข้อมูลที่ไม่มีในรายการ
- ถ้าข้อมูลไม่พอ ให้ระบุว่า "ข้อมูลไม่เพียงพอ"
- ใช้ภาษาไทยในการให้เหตุผล
- คะแนน rerank_score ควรอยู่ระหว่าง 0.0-1.0

**รูปแบบผลลัพธ์ (JSON):**
{{
  "ranked_candidates": [
    {{
      "candidate_index": 0,
      "rerank_score": 0.95,
      "reasons": "เหตุผลสั้นๆ",
      "highlighted_skills": ["skill1", "skill2"],
      "gaps": ["gap1"],
      "recommended_questions_for_interview": ["คำถาม1", "คำถาม2"]
    }}
  ]
}}

กรุณาให้ผลลัพธ์เป็น JSON เท่านั้น:"""
        
        print("[INFO] Prompt prepared:")
        print("-" * 60)
        print(rerank_prompt[:500] + "...")
        print("-" * 60)
        print()
        
        # Prepare request body (Nova Lite format)
        rerank_body = json.dumps({
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": rerank_prompt
                        }
                    ]
                }
            ],
            "inferenceConfig": {
                "maxTokens": 2000,
                "temperature": 0.3,
                "topP": 0.9
            }
        })
        
        print("[*] Calling Nova Lite API...")
        print()
        
        # Call Nova Lite
        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_RERANK_MODEL,
            body=rerank_body,
            contentType="application/json",
            accept="application/json"
        )
        
        print("[OK] API call successful!")
        print()
        
        # Parse response (Nova Lite format)
        result = json.loads(response["body"].read())
        
        # Nova Lite returns: {"output": {"message": {"content": [{"text": "..."}]}}}
        output = result.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        
        if not content:
            print("[ERROR] No content in response")
            print(f"Full response: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return False
        
        result_text = content[0].get("text", "{}")
        
        # Extract JSON from markdown code blocks if present
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        print("[RESPONSE] Raw response:")
        print("-" * 60)
        print(result_text)
        print("-" * 60)
        print()
        
        # Parse JSON
        try:
            ranked_data = json.loads(result_text)
            ranked_list = ranked_data.get("ranked_candidates", [])
            
            if not ranked_list:
                print("[ERROR] No ranked candidates in response")
                return False
            
            print("[SUCCESS] Reranking Results:")
            print("=" * 60)
            
            for rank_num, item in enumerate(ranked_list, 1):
                idx = item.get("candidate_index", -1)
                if 0 <= idx < len(SAMPLE_JOBS):
                    job = SAMPLE_JOBS[idx]
                    print(f"\n[Rank #{rank_num}]")
                    print(f"   Job: {job['title']}")
                    print(f"   Rerank Score: {item.get('rerank_score', 0.0):.2f}")
                    print(f"   Reasons: {item.get('reasons', 'N/A')}")
                    
                    skills = item.get("highlighted_skills", [])
                    if skills:
                        print(f"   Highlighted Skills: {', '.join(skills)}")
                    
                    gaps = item.get("gaps", [])
                    if gaps:
                        print(f"   Gaps: {', '.join(gaps)}")
                    
                    questions = item.get("recommended_questions_for_interview", [])
                    if questions:
                        print(f"   Interview Questions:")
                        for q in questions:
                            print(f"     - {q}")
            
            print("\n" + "=" * 60)
            print("[SUCCESS] Test completed successfully!")
            return True
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] Error parsing JSON: {str(e)}")
            print(f"Response text: {result_text}")
            return False
        
    except Exception as e:
        print(f"[ERROR] Error: {str(e)}")
        import traceback
        print("\nFull traceback:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    print()
    success = test_nova_lite()
    print()
    sys.exit(0 if success else 1)

