"""
AWS Bedrock Client for Embeddings and LLM Reranking
"""
import boto3
import json
from typing import List, Dict, Any
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import EmbeddingError, RerankError

logger = get_logger(__name__)


class BedrockClient:
    """Bedrock client for embeddings and LLM operations"""
    
    def __init__(self):
        if settings.USE_MOCK:
            self.client = None
            self.rerank_client = None
            logger.info("BedrockClient initialized in MOCK mode")
        else:
            # In Lambda, always use IAM role - don't pass credentials
            # boto3 will automatically use the Lambda execution role
            # Only use explicit credentials if we're NOT in Lambda environment
            import os
            
            # Check if we're in Lambda (Lambda sets AWS_LAMBDA_FUNCTION_NAME)
            is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
            
            # Helper function to create client
            def create_client(region):
                if is_lambda:
                    # In Lambda: Use IAM role only - don't pass any credentials
                    return boto3.client(
                        'bedrock-runtime',
                        region_name=region
                    )
                else:
                    # Local dev: Use explicit credentials if provided
                    client_kwargs = {
                        'service_name': 'bedrock-runtime',
                        'region_name': region
                    }
                    
                    # Only add credentials if explicitly provided (for local dev)
                    if (settings.AWS_ACCESS_KEY_ID and 
                        settings.AWS_SECRET_ACCESS_KEY and 
                        settings.AWS_ACCESS_KEY_ID.strip() != "" and 
                        settings.AWS_SECRET_ACCESS_KEY.strip() != ""):
                        client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
                        client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
                    
                    return boto3.client(**client_kwargs)
            
            # Client for embeddings (uses BEDROCK_REGION)
            self.client = create_client(settings.BEDROCK_REGION)
            logger.info(f"BedrockClient initialized for embeddings region: {settings.BEDROCK_REGION}")
            
            # Client for rerank (uses BEDROCK_RERANK_REGION if set, otherwise BEDROCK_REGION)
            rerank_region = getattr(settings, 'BEDROCK_RERANK_REGION', None) or settings.BEDROCK_REGION
            self.rerank_client = create_client(rerank_region)
            logger.info(f"BedrockClient initialized for rerank region: {rerank_region}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Bedrock
        
        Args:
            text: Input text to embed
            
        Returns:
            List of float values representing the embedding vector
        """
        if settings.USE_MOCK:
            # Return mock embedding (1024 dimensions for cohere.embed-multilingual-v3)
            import random
            mock_embedding = [random.gauss(0, 0.1) for _ in range(1024)]
            # Normalize
            norm = sum(x*x for x in mock_embedding) ** 0.5
            mock_embedding = [x/norm for x in mock_embedding]
            logger.info(f"MOCK: Generated embedding for text (length: {len(text)})")
            return mock_embedding
        
        try:
            # Cohere embedding model has max length limit of 2048 characters
            MAX_TEXT_LENGTH = 2048
            original_length = len(text)
            
            if original_length > MAX_TEXT_LENGTH:
                # Truncate text to fit within limit
                # Try to truncate at word boundary if possible
                truncated = text[:MAX_TEXT_LENGTH]
                last_space = truncated.rfind(' ')
                if last_space > MAX_TEXT_LENGTH * 0.9:  # If we can find a space in last 10%
                    truncated = truncated[:last_space]
                else:
                    truncated = truncated[:MAX_TEXT_LENGTH]
                
                logger.warning(f"Text truncated from {original_length} to {len(truncated)} characters (max: {MAX_TEXT_LENGTH})")
                text = truncated
            
            # Cohere embedding model
            if "cohere" in settings.BEDROCK_EMBEDDING_MODEL.lower():
                body = json.dumps({
                    "texts": [text],
                    "input_type": "search_document"
                })
            else:
                # Titan embedding model
                body = json.dumps({
                    "inputText": text
                })
            
            response = self.client.invoke_model(
                modelId=settings.BEDROCK_EMBEDDING_MODEL,
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            
            response_body = json.loads(response['body'].read())
            
            if "cohere" in settings.BEDROCK_EMBEDDING_MODEL.lower():
                embedding = response_body['embeddings'][0]
            else:
                embedding = response_body['embedding']
            
            logger.info(f"Generated embedding (dimensions: {len(embedding)})")
            return embedding
            
        except ClientError as e:
            logger.error(f"Bedrock embedding error: {e}")
            raise EmbeddingError(f"Failed to generate embedding: {str(e)}")
    
    def rerank_candidates(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Rerank candidates using Bedrock LLM (Nova 2 Lite)
        
        Args:
            query: The search query (resume summary or job description)
            candidates: List of candidate items with metadata
            top_k: Number of top results to return
            
        Returns:
            List of reranked candidates with scores and reasons
        """
        if settings.USE_MOCK:
            # Mock reranking - just return candidates with mock scores
            logger.info(f"MOCK: Reranking {len(candidates)} candidates")
            reranked = []
            for i, candidate in enumerate(candidates[:top_k]):
                reranked.append({
                    **candidate,
                    "rerank_score": 0.95 - (i * 0.05),
                    "rerank_reason": f"Mock reason: Good match based on {candidate.get('title', 'N/A')}",
                    "rank": i + 1
                })
            return reranked
        
        try:
            # Prepare prompt for Nova 2 Lite
            prompt = self._build_rerank_prompt(query, candidates, top_k)
            
            # Nova Lite format: content must be an array with text object
            body = json.dumps({
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
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
            
            # Use rerank_client which may be in different region (us-east-1 for Nova models)
            rerank_client = getattr(self, 'rerank_client', self.client)
            response = rerank_client.invoke_model(
                modelId=settings.BEDROCK_RERANK_MODEL,
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            
            # Parse Nova Lite response format: {"output": {"message": {"content": [{"text": "..."}]}}}
            response_body = json.loads(response['body'].read())
            
            # Debug: log response structure
            logger.debug(f"Bedrock response keys: {list(response_body.keys())}")
            
            # Try different response formats
            result_text = None
            
            # Format 1: Nova Lite format {"output": {"message": {"content": [{"text": "..."}]}}}
            output = response_body.get('output', {})
            if output:
                message = output.get('message', {})
                if message:
                    content = message.get('content', [])
                    if content and len(content) > 0:
                        result_text = content[0].get('text', '')
            
            # Format 2: Direct content format {"content": [{"text": "..."}]}
            if not result_text:
                content = response_body.get('content', [])
                if content and len(content) > 0:
                    result_text = content[0].get('text', '')
            
            # Format 3: Direct text field
            if not result_text:
                result_text = response_body.get('text', '')
            
            # Format 4: Direct JSON in response
            if not result_text and 'ranked_candidates' in response_body:
                # Response is already the JSON we need
                reranked = self._parse_rerank_results(response_body, candidates, top_k)
                logger.info(f"Reranked {len(reranked)} candidates")
                return reranked
            
            if not result_text or result_text.strip() == '':
                logger.error(f"Empty response text. Full response: {response_body}")
                raise RerankError("Empty response text from Bedrock")
            
            # Clean up markdown code blocks if present
            result_text = result_text.strip()
            if result_text.startswith('```json'):
                # Remove ```json and ``` markers
                result_text = result_text[7:]  # Remove ```json
                if result_text.endswith('```'):
                    result_text = result_text[:-3]  # Remove ```
            elif result_text.startswith('```'):
                # Remove ``` markers
                result_text = result_text[3:]
                if result_text.endswith('```'):
                    result_text = result_text[:-3]
            result_text = result_text.strip()
            
            # Try to parse JSON from text
            try:
                result_json = json.loads(result_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from response. Text: {result_text[:500]}")
                raise RerankError(f"Invalid JSON in response: {str(e)}")
            
            # Validate and format results
            reranked = self._parse_rerank_results(result_json, candidates, top_k)
            logger.info(f"Reranked {len(reranked)} candidates")
            return reranked
                
        except (ClientError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Bedrock rerank error: {e}")
            raise RerankError(f"Failed to rerank candidates: {str(e)}")
    
    def extract_resume_categories(self, resume_text: str) -> Dict[str, Any]:
        """
        Extract and categorize resume information using LLM (Nova Lite)
        
        Args:
            resume_text: Full text extracted from resume
            
        Returns:
            Dictionary with categorized resume information
        """
        try:
            # Build prompt for categorization
            prompt = self._build_extract_prompt(resume_text)
            
            # Nova Lite format: content must be an array with text object
            body = json.dumps({
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": 2000,
                    "temperature": 0.2,  # Lower temperature for more consistent extraction
                    "topP": 0.9
                }
            })
            
            # Use rerank_client which uses Nova Lite in us-east-1
            rerank_client = getattr(self, 'rerank_client', self.client)
            response = rerank_client.invoke_model(
                modelId=settings.BEDROCK_RERANK_MODEL,
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            
            # Parse Nova Lite response format
            response_body = json.loads(response['body'].read())
            
            # Try different response formats
            result_text = None
            
            # Format 1: Nova Lite format {"output": {"message": {"content": [{"text": "..."}]}}}
            output = response_body.get('output', {})
            if output:
                message = output.get('message', {})
                if message:
                    content = message.get('content', [])
                    if content and len(content) > 0:
                        result_text = content[0].get('text', '')
            
            # Format 2: Direct content format
            if not result_text:
                content = response_body.get('content', [])
                if content and len(content) > 0:
                    result_text = content[0].get('text', '')
            
            # Format 3: Direct text field
            if not result_text:
                result_text = response_body.get('text', '')
            
            if not result_text or result_text.strip() == '':
                logger.error(f"Empty response text. Full response: {response_body}")
                # Fallback: return basic structure with original text
                return {
                    "personal_info": {},
                    "summary": "",
                    "skills": [],
                    "experience": [],
                    "education": [],
                    "languages": [],
                    "structured_text": resume_text[:2048]  # Use original text for embedding
                }
            
            # Clean up markdown code blocks if present
            result_text = result_text.strip()
            if result_text.startswith('```json'):
                result_text = result_text[7:]
                if result_text.endswith('```'):
                    result_text = result_text[:-3]
            elif result_text.startswith('```'):
                result_text = result_text[3:]
                if result_text.endswith('```'):
                    result_text = result_text[:-3]
            result_text = result_text.strip()
            
            # Try to parse JSON from text
            try:
                result_json = json.loads(result_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from response. Text: {result_text[:500]}")
                # Fallback: return basic structure with original text
                return {
                    "personal_info": {},
                    "summary": "",
                    "skills": [],
                    "experience": [],
                    "education": [],
                    "languages": [],
                    "structured_text": resume_text[:2048]
                }
            
            # Validate and format results
            categorized = self._parse_extract_results(result_json, resume_text)
            logger.info(f"Extracted categories from resume")
            return categorized
                
        except (ClientError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Bedrock extract categories error: {e}")
            # Fallback: return basic structure with original text
            return {
                "personal_info": {},
                "summary": "",
                "skills": [],
                "experience": [],
                "education": [],
                "languages": [],
                "structured_text": resume_text[:2048]
            }
    
    def _build_extract_prompt(self, resume_text: str) -> str:
        """Build prompt for extracting resume categories"""
        # Truncate resume text if too long (Nova has token limits)
        max_text_length = 4000  # Leave room for prompt
        if len(resume_text) > max_text_length:
            resume_text = resume_text[:max_text_length] + "..."
        
        prompt = f"""คุณเป็น AI ที่เชี่ยวชาญในการแยกประเภทและจัดโครงสร้างข้อมูลจาก Resume/CV

**Resume Text:**
{resume_text}

**งานของคุณ:**
แยกประเภทและจัดโครงสร้างข้อมูลจาก Resume ให้เป็น JSON ตามรูปแบบด้านล่าง

**ข้อกำหนด:**
- แยกข้อมูลให้ครบถ้วนและถูกต้อง
- ถ้าไม่พบข้อมูลในส่วนใด ให้ใช้ค่า null หรือ array ว่าง
- ใช้ภาษาไทยหรือภาษาอังกฤษตามที่พบใน Resume
- สำหรับ structured_text ให้สร้างข้อความที่เหมาะสำหรับการทำ embedding โดยรวมข้อมูลสำคัญทั้งหมด

**รูปแบบผลลัพธ์ (JSON):**
{{
  "personal_info": {{
    "name": "ชื่อ-นามสกุล",
    "email": "email@example.com",
    "phone": "เบอร์โทรศัพท์",
    "location": "ที่อยู่/เมือง"
  }},
  "summary": "สรุปประวัติหรือ objective",
  "skills": ["skill1", "skill2", "skill3"],
  "experience": [
    {{
      "title": "ตำแหน่งงาน",
      "company": "ชื่อบริษัท",
      "duration": "ระยะเวลา (เช่น 2020-2024)",
      "description": "รายละเอียดงาน"
    }}
  ],
  "education": [
    {{
      "degree": "ระดับการศึกษา",
      "institution": "สถาบันการศึกษา",
      "year": "ปีที่จบ"
    }}
  ],
  "languages": ["ภาษา1", "ภาษา2"],
  "structured_text": "ข้อความที่รวมข้อมูลสำคัญทั้งหมดสำหรับ embedding (ควรมีชื่อ, ทักษะ, ประสบการณ์, การศึกษา)"
}}

กรุณาให้ผลลัพธ์เป็น JSON เท่านั้น:"""
        
        return prompt
    
    def _build_structured_text_by_category(self, categorized: Dict[str, Any]) -> Dict[str, str]:
        """
        Build structured text for each category separately
        
        Returns:
            Dictionary with structured text for each category
        """
        structured_texts = {}
        
        # Personal info
        personal_info = categorized.get("personal_info", {})
        if personal_info:
            personal_parts = []
            if personal_info.get("name"):
                personal_parts.append(f"Name: {personal_info['name']}")
            if personal_info.get("email"):
                personal_parts.append(f"Email: {personal_info['email']}")
            if personal_info.get("phone"):
                personal_parts.append(f"Phone: {personal_info['phone']}")
            if personal_info.get("location"):
                personal_parts.append(f"Location: {personal_info['location']}")
            if personal_parts:
                structured_texts["personal_info"] = "\n".join(personal_parts)
        
        # Summary
        summary = categorized.get("summary", "")
        if summary:
            structured_texts["summary"] = summary
        
        # Skills
        skills = categorized.get("skills", [])
        if skills:
            structured_texts["skills"] = ", ".join(skills)
        
        # Experience
        experience = categorized.get("experience", [])
        if experience:
            exp_parts = []
            for exp in experience:
                exp_text = f"{exp.get('title', '')} at {exp.get('company', '')}"
                if exp.get('duration'):
                    exp_text += f" ({exp['duration']})"
                if exp.get('description'):
                    exp_text += f": {exp['description']}"
                exp_parts.append(exp_text)
            if exp_parts:
                structured_texts["experience"] = " | ".join(exp_parts)
        
        # Education
        education = categorized.get("education", [])
        if education:
            edu_parts = []
            for edu in education:
                edu_text = f"{edu.get('degree', '')} from {edu.get('institution', '')}"
                if edu.get('year'):
                    edu_text += f" ({edu['year']})"
                edu_parts.append(edu_text)
            if edu_parts:
                structured_texts["education"] = " | ".join(edu_parts)
        
        # Languages
        languages = categorized.get("languages", [])
        if languages:
            structured_texts["languages"] = ", ".join(languages)
        
        # Limit each text to 2048 chars for embedding
        for key in structured_texts:
            if len(structured_texts[key]) > 2048:
                structured_texts[key] = structured_texts[key][:2048]
        
        return structured_texts
    
    def generate_category_embeddings(self, categorized: Dict[str, Any]) -> Dict[str, List[float]]:
        """
        Generate embeddings for each category separately
        
        Args:
            categorized: Dictionary with categorized resume information
            
        Returns:
            Dictionary with embeddings for each category
        """
        embeddings = {}
        structured_texts = self._build_structured_text_by_category(categorized)
        
        for category, text in structured_texts.items():
            try:
                embedding = self.generate_embedding(text)
                embeddings[category] = embedding
                logger.info(f"Generated embedding for category '{category}' (text length: {len(text)})")
            except Exception as e:
                logger.error(f"Error generating embedding for category '{category}': {e}")
                # Continue with other categories even if one fails
                continue
        
        return embeddings
    
    def _parse_extract_results(self, result_json: Dict, original_text: str) -> Dict[str, Any]:
        """Parse and validate extract results"""
        # Build structured text for embedding from categorized data
        structured_parts = []
        
        # Personal info
        personal_info = result_json.get("personal_info", {})
        if personal_info:
            if personal_info.get("name"):
                structured_parts.append(f"Name: {personal_info['name']}")
            if personal_info.get("email"):
                structured_parts.append(f"Email: {personal_info['email']}")
            if personal_info.get("phone"):
                structured_parts.append(f"Phone: {personal_info['phone']}")
            if personal_info.get("location"):
                structured_parts.append(f"Location: {personal_info['location']}")
        
        # Summary
        summary = result_json.get("summary", "")
        if summary:
            structured_parts.append(f"Summary: {summary}")
        
        # Skills
        skills = result_json.get("skills", [])
        if skills:
            structured_parts.append(f"Skills: {', '.join(skills)}")
        
        # Experience
        experience = result_json.get("experience", [])
        if experience:
            structured_parts.append("Experience:")
            for exp in experience:
                exp_text = f"  - {exp.get('title', '')} at {exp.get('company', '')}"
                if exp.get('duration'):
                    exp_text += f" ({exp['duration']})"
                if exp.get('description'):
                    exp_text += f": {exp['description']}"
                structured_parts.append(exp_text)
        
        # Education
        education = result_json.get("education", [])
        if education:
            structured_parts.append("Education:")
            for edu in education:
                edu_text = f"  - {edu.get('degree', '')} from {edu.get('institution', '')}"
                if edu.get('year'):
                    edu_text += f" ({edu['year']})"
                structured_parts.append(edu_text)
        
        # Languages
        languages = result_json.get("languages", [])
        if languages:
            structured_parts.append(f"Languages: {', '.join(languages)}")
        
        # Combine structured text (limit to 2048 chars for embedding)
        structured_text = "\n".join(structured_parts)
        if len(structured_text) > 2048:
            structured_text = structured_text[:2048]
        
        # If structured text is too short, use original text as fallback
        if len(structured_text) < 100:
            structured_text = original_text[:2048]
        
        return {
            "personal_info": personal_info,
            "summary": summary,
            "skills": skills,
            "experience": experience,
            "education": education,
            "languages": languages,
            "structured_text": structured_text
        }
    
    def _build_rerank_prompt(self, query: str, candidates: List[Dict[str, Any]], top_k: int) -> str:
        """Build prompt for reranking"""
        candidates_text = "\n".join([
            f"{i+1}. {candidate.get('title', 'N/A')} - {candidate.get('text_excerpt', '')[:200]}..."
            for i, candidate in enumerate(candidates)
        ])
        
        prompt = f"""คุณเป็น AI ที่เชี่ยวชาญในการจับคู่ Resume กับ Job หรือ Job กับ Resume

**คำถาม/Query:**
{query}

**รายการผู้สมัคร (Candidates):**
{candidates_text}

**งานของคุณ:**
1. วิเคราะห์และจัดอันดับผู้สมัครทุกคนที่ให้มา โดยต้องให้คะแนน rerank_score (0.0-1.0) กับผู้สมัครทุกคน (ห้ามตัดผู้สมัครออกเอง) และใช้คะแนนนี้ในการเลือก Top {top_k} ที่เหมาะสมที่สุด
2. เขียน reason แบบมีโครงสร้าง แยกเป็นหัวข้อชัดเจน ภายในข้อความเดียวกัน (string เดียว) เช่น:
   - "ภาพรวมความเหมาะสม:" อธิบายภาพรวม 1-2 ประโยค
   - "ทักษะที่เกี่ยวข้อง:" สรุปสกิลหลัก ๆ ที่ตรงกับงาน
   - "ประสบการณ์ที่เกี่ยวข้อง:" ยกตัวอย่างประสบการณ์ / โปรเจกต์ / domain ที่ตรง
   - "ตำแหน่งและระดับ:" อธิบายความเหมาะสมของระดับตำแหน่ง (เช่น junior / senior / manager) ถ้าพออนุมานได้
   - "ที่ตั้ง / รูปแบบงาน:" ถ้ามีข้อมูลเรื่องสถานที่ทำงาน, remote, hybrid ฯลฯ ให้พูดถึงด้วย ถ้าไม่มีให้ข้ามได้
   - "ความเสี่ยง / ช่องว่าง:" อธิบายสิ่งที่อาจยังขาดเมื่อเทียบกับ JD
3. ระบุจุดเด่น (highlighted_skills) และจุดที่ขาด (gaps) เป็นรายการ (list) ให้ชัดเจน
4. ถ้าเห็นว่าควรถามอะไรเพิ่มในการสัมภาษณ์ ให้ใส่ใน recommended_questions อย่างน้อย 2-3 ข้อ

**ข้อกำหนด:**
- ห้ามสร้างข้อมูลที่ไม่มีใน candidates (ต้องอิงจากข้อความที่ให้มาเท่านั้น)
- ถ้าข้อมูลไม่พอ ให้ระบุใน reason ว่า "ข้อมูลไม่เพียงพอ" และอย่าเดา
- ใช้ภาษาไทยในการให้เหตุผลทั้งหมด
- คะแนน rerank_score ควรอยู่ระหว่าง 0.0-1.0 (ยิ่งใกล้ 1.0 แปลว่ายิ่งเหมาะสม)
 - ต้องคืนค่า ranked_candidates ให้มี 1 แถวต่อ 1 ผู้สมัครที่ให้มา (ครบทุก candidate_index ที่อยู่ในรายการผู้สมัครด้านบน) แม้ว่าบางคนจะได้คะแนนต่ำหรือไม่เหมาะสม

**รูปแบบผลลัพธ์ (JSON):**
{{
  "ranked_candidates": [
    {{
      "candidate_index": 0,
      "rerank_score": 0.95,
      "reason": "เหตุผลสั้นๆ",
      "highlighted_skills": ["skill1", "skill2"],
      "gaps": ["gap1"],
      "recommended_questions": ["คำถาม1", "คำถาม2"]
    }}
  ]
}}

กรุณาให้ผลลัพธ์เป็น JSON เท่านั้น:"""
        
        return prompt
    
    def _parse_rerank_results(self, result_json: Dict, original_candidates: List[Dict], top_k: int = 10) -> List[Dict]:
        """Parse and validate rerank results"""
        reranked = []
        ranked_list = result_json.get("ranked_candidates", [])
        
        # ต้องการจำนวนผลลัพธ์สูงสุดเท่ากับ top_k หรือจำนวนผู้สมัครที่มีจริง (whichever is smaller)
        desired_count = min(top_k, len(original_candidates))
        
        used_indices = set()
        
        # 1) ใส่ข้อมูลตามที่โมเดลส่งมา (ถ้ามี)
        for item in ranked_list:
            if len(reranked) >= desired_count:
                break
            idx = item.get("candidate_index", 0)
            if not isinstance(idx, int):
                continue
            if 0 <= idx < len(original_candidates) and idx not in used_indices:
                candidate = original_candidates[idx].copy()
                candidate.update({
                    "rerank_score": float(item.get("rerank_score", 0.0)),
                    "rerank_reason": item.get("reason", "ไม่มีข้อมูล"),
                    "highlighted_skills": item.get("highlighted_skills", []),
                    "gaps": item.get("gaps", []),
                    "recommended_questions": item.get("recommended_questions", []),
                    "rank": len(reranked) + 1
                })
                reranked.append(candidate)
                used_indices.add(idx)
        
        # 2) ถ้าโมเดลไม่คืนมาครบทุก candidate (เช่น เลือกมาแค่ 1 จาก 2)
        #    ให้เติมผู้สมัครที่ขาดหายเข้าไปด้วยคะแนนต่ำ ๆ เพื่อให้ UI แสดงครบ
        if len(reranked) < desired_count:
            for idx in range(len(original_candidates)):
                if len(reranked) >= desired_count:
                    break
                if idx in used_indices:
                    continue
                
                base_candidate = original_candidates[idx].copy()
                vector_score = float(base_candidate.get("vector_score", 0.0))
                
                # ให้คะแนนต่ำมาก แต่ยังอยู่ในช่วง 0.0-1.0
                fallback_score = max(0.0, min(vector_score * 0.3, 0.3))
                
                base_candidate.update({
                    "rerank_score": fallback_score,
                    "rerank_reason": "โมเดลไม่ได้จัดอันดับผู้สมัครคนนี้โดยตรง จึงให้คะแนนต่ำและแสดงเป็นตัวเลือกเพิ่มเติม เพื่อให้เห็นผู้สมัครครบทุกคนที่เลือกไว้",
                    "highlighted_skills": base_candidate.get("highlighted_skills", []),
                    "gaps": base_candidate.get("gaps", []),
                    "recommended_questions": base_candidate.get("recommended_questions", []),
                    "rank": len(reranked) + 1
                })
                reranked.append(base_candidate)
        
        logger.info(
            f"Parsed {len(reranked)} reranked results "
            f"(requested top_k={top_k}, ranked_from_model={len(ranked_list)}, "
            f"candidates={len(original_candidates)}, desired_count={desired_count})"
        )
        return reranked


# Singleton instance
bedrock_client = BedrockClient()

