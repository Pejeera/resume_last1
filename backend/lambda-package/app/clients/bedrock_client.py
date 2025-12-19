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
            logger.info("BedrockClient initialized in MOCK mode")
        else:
            # In Lambda, always use IAM role - don't pass credentials
            # boto3 will automatically use the Lambda execution role
            # Only use explicit credentials if we're NOT in Lambda environment
            import os
            
            # Check if we're in Lambda (Lambda sets AWS_LAMBDA_FUNCTION_NAME)
            is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
            
            if is_lambda:
                # In Lambda: Use IAM role only - don't pass any credentials
                self.client = boto3.client(
                    'bedrock-runtime',
                    region_name=settings.BEDROCK_REGION
                )
                logger.info(f"BedrockClient initialized using IAM role (Lambda) for region: {settings.BEDROCK_REGION}")
            else:
                # Local dev: Use explicit credentials if provided
                client_kwargs = {
                    'service_name': 'bedrock-runtime',
                    'region_name': settings.BEDROCK_REGION
                }
                
                # Only add credentials if explicitly provided (for local dev)
                if (settings.AWS_ACCESS_KEY_ID and 
                    settings.AWS_SECRET_ACCESS_KEY and 
                    settings.AWS_ACCESS_KEY_ID.strip() != "" and 
                    settings.AWS_SECRET_ACCESS_KEY.strip() != ""):
                    client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
                    client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
                    logger.info(f"BedrockClient initialized with explicit credentials for region: {settings.BEDROCK_REGION}")
                else:
                    # Use default credentials (from ~/.aws/credentials or environment)
                    logger.info(f"BedrockClient initialized using default credentials for region: {settings.BEDROCK_REGION}")
                
                self.client = boto3.client(**client_kwargs)
    
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
            
            body = json.dumps({
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": 2000,
                    "temperature": 0.3,
                    "topP": 0.9
                },
                "responseFormat": {
                    "type": "json"
                }
            })
            
            response = self.client.invoke_model(
                modelId=settings.BEDROCK_RERANK_MODEL,
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            
            response_body = json.loads(response['body'].read())
            
            # Extract JSON from response
            content = response_body.get('content', [])
            if content:
                result_text = content[0].get('text', '{}')
                result_json = json.loads(result_text)
                
                # Validate and format results
                reranked = self._parse_rerank_results(result_json, candidates)
                logger.info(f"Reranked {len(reranked)} candidates")
                return reranked
            else:
                raise RerankError("Empty response from Bedrock")
                
        except (ClientError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Bedrock rerank error: {e}")
            raise RerankError(f"Failed to rerank candidates: {str(e)}")
    
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
1. วิเคราะห์และจัดอันดับผู้สมัคร Top {top_k} ที่เหมาะสมที่สุด
2. ให้เหตุผลสั้นๆ กระชับ (2-3 ประโยค) ว่าทำไมถึงเหมาะ
3. ระบุจุดเด่น (highlighted_skills) และจุดที่ขาด (gaps) ถ้ามี

**ข้อกำหนด:**
- ห้ามสร้างข้อมูลที่ไม่มีใน candidates
- ถ้าข้อมูลไม่พอ ให้ระบุว่า "ข้อมูลไม่เพียงพอ"
- ใช้ภาษาไทยในการให้เหตุผล
- คะแนน rerank_score ควรอยู่ระหว่าง 0.0-1.0

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
    
    def _parse_rerank_results(self, result_json: Dict, original_candidates: List[Dict]) -> List[Dict]:
        """Parse and validate rerank results"""
        reranked = []
        ranked_list = result_json.get("ranked_candidates", [])
        
        for item in ranked_list[:10]:  # Limit to top 10
            idx = item.get("candidate_index", 0)
            if 0 <= idx < len(original_candidates):
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
        
        return reranked


# Singleton instance
bedrock_client = BedrockClient()

