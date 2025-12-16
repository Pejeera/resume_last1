# Rerank Prompt Template for Bedrock Nova 2 Lite

## Overview
Prompt template สำหรับใช้กับ Amazon Nova 2 Lite เพื่อทำ reranking ของ candidates

## Prompt Structure

```
คุณเป็น AI ที่เชี่ยวชาญในการจับคู่ Resume กับ Job หรือ Job กับ Resume

**คำถาม/Query:**
{query}

**รายการผู้สมัคร (Candidates):**
{candidates_list}

**งานของคุณ:**
1. วิเคราะห์และจัดอันดับผู้สมัคร Top {top_k} ที่เหมาะสมที่สุด
2. ให้เหตุผลสั้นๆ กระชับ (2-3 ประโยค) ว่าทำไมถึงเหมาะ
3. ระบุจุดเด่น (highlighted_skills) และจุดที่ขาด (gaps) ถ้ามี

**ข้อกำหนด:**
- ห้ามสร้างข้อมูลที่ไม่มีใน candidates
- ถ้าข้อมูลไม่พอ ให้ระบุว่า "ข้อมูลไม่เพียงพอ"
- ใช้ภาษาไทยในการให้เหตุผล
- คะแนน rerank_score ควรอยู่ระหว่าง 0.0-1.0

**รูปแบบผลลัพธ์ (JSON):**
{
  "ranked_candidates": [
    {
      "candidate_index": 0,
      "rerank_score": 0.95,
      "reason": "เหตุผลสั้นๆ",
      "highlighted_skills": ["skill1", "skill2"],
      "gaps": ["gap1"],
      "recommended_questions": ["คำถาม1", "คำถาม2"]
    }
  ]
}

กรุณาให้ผลลัพธ์เป็น JSON เท่านั้น:
```

## JSON Schema

### Input Schema
```json
{
  "query": "string - Resume summary or Job description",
  "candidates": [
    {
      "candidate_index": "number",
      "title": "string",
      "text_excerpt": "string",
      "metadata": {},
      "vector_score": "number"
    }
  ],
  "top_k": "number"
}
```

### Output Schema
```json
{
  "ranked_candidates": [
    {
      "candidate_index": "number - Index from original candidates array",
      "rerank_score": "number - 0.0 to 1.0",
      "reason": "string - Short reason in Thai (2-3 sentences)",
      "highlighted_skills": ["string - Array of skills"],
      "gaps": ["string - Array of gaps/missing skills"],
      "recommended_questions": ["string - Array of interview questions"]
    }
  ]
}
```

## Example Usage

### Mode A: Resume → Jobs
```json
{
  "query": "Resume Summary: Software Engineer with 5 years experience in Python, FastAPI, AWS...",
  "candidates": [
    {
      "candidate_index": 0,
      "title": "Senior Backend Engineer",
      "text_excerpt": "Looking for experienced backend engineer...",
      "vector_score": 0.89
    }
  ],
  "top_k": 10
}
```

### Mode B: Job → Resumes
```json
{
  "query": "Job Description: We are looking for a Full-Stack Engineer...",
  "candidates": [
    {
      "candidate_index": 0,
      "title": "John Doe Resume",
      "text_excerpt": "5 years experience in web development...",
      "vector_score": 0.92
    }
  ],
  "top_k": 10
}
```

## Guardrails

1. **No Hallucination**: ห้ามสร้างข้อมูลที่ไม่มีใน candidates
2. **Data Insufficiency**: ถ้าข้อมูลไม่พอ ให้ระบุว่า "ข้อมูลไม่เพียงพอ"
3. **Language**: ใช้ภาษาไทยในการให้เหตุผล
4. **Score Range**: rerank_score ต้องอยู่ระหว่าง 0.0-1.0
5. **JSON Format**: ผลลัพธ์ต้องเป็น JSON ที่ valid เท่านั้น

## Implementation Notes

- Model: `us.amazon.nova-lite-v1:0`
- Temperature: 0.3 (เพื่อความสม่ำเสมอ)
- Max Tokens: 2000
- Response Format: JSON (strict)

