"""
Matching Service
Core business logic for resume-job matching
"""
from typing import List, Dict, Any, Optional
from app.clients.bedrock_client import bedrock_client
from app.clients.opensearch_client import opensearch_client
from app.core.logging import get_logger
from app.core.config import settings
from app.core.exceptions import EmbeddingError, RerankError, OpenSearchError

logger = get_logger(__name__)


class MatchingService:
    """Service for matching resumes and jobs"""
    
    JOBS_INDEX = "jobs_index"
    RESUMES_INDEX = "resumes_index"
    
    def __init__(self):
        self.bedrock = bedrock_client
        self.opensearch = opensearch_client
    
    def search_jobs_by_resume(
        self,
        resume_text: str,
        resume_id: str,
        top_k_initial: int = 50,
        top_k_final: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Mode A: Find top jobs for a resume
        
        Args:
            resume_text: Extracted text from resume
            resume_id: Resume identifier
            top_k_initial: Initial candidates from vector search
            top_k_final: Final results after reranking
            
        Returns:
            List of top matching jobs with scores and reasons
        """
        try:
            # 1. Generate embedding for resume
            logger.info(f"Generating embedding for resume {resume_id}")
            resume_embedding = self.bedrock.generate_embedding(resume_text)
            
            # 2. Vector search in jobs index
            logger.info(f"Searching jobs index (top_k={top_k_initial})")
            
            # Log available jobs count
            available_jobs_count = None
            if settings.USE_MOCK:
                from app.clients.opensearch_client import opensearch_client
                available_jobs = opensearch_client._mock_data_storage.get(self.JOBS_INDEX, [])
                available_jobs_count = len(available_jobs)
                logger.info(f"Available jobs in index: {available_jobs_count}")
                if available_jobs:
                    job_titles = [job.get("title", "N/A") for job in available_jobs[:10]]
                    logger.info(f"Sample job titles: {job_titles}")
            
            candidates = self.opensearch.vector_search(
                index_name=self.JOBS_INDEX,
                query_vector=resume_embedding,
                top_k=top_k_initial
            )
            
            if not candidates:
                logger.warning(f"No jobs found in vector search. Available jobs in index: {available_jobs_count if available_jobs_count is not None else 'N/A'}")
                return []
            
            logger.info(f"Found {len(candidates)} candidates from vector search")
            
            # 3. Prepare candidates for reranking
            candidates_for_rerank = []
            for candidate in candidates[:top_k_initial]:
                candidates_for_rerank.append({
                    "candidate_index": len(candidates_for_rerank),
                    "title": candidate.get("title", "N/A"),
                    "text_excerpt": candidate.get("text_excerpt", ""),
                    "metadata": candidate.get("metadata", {}),
                    "vector_score": candidate.get("_score", 0.0),
                    "job_id": candidate.get("_id", "")
                })
            
            # 4. Rerank with Bedrock LLM
            logger.info(f"Reranking {len(candidates_for_rerank)} candidates")
            query_summary = f"Resume Summary: {resume_text[:500]}..."
            reranked = self.bedrock.rerank_candidates(
                query=query_summary,
                candidates=candidates_for_rerank,
                top_k=top_k_final
            )
            
            # 5. Format results
            results = []
            for item in reranked:
                results.append({
                    "rank": item.get("rank", 0),
                    "job_id": item.get("job_id", ""),
                    "job_title": item.get("title", "N/A"),
                    "match_score": item.get("vector_score", 0.0),
                    "rerank_score": item.get("rerank_score", 0.0),
                    "reasons": item.get("rerank_reason", ""),
                    "highlighted_skills": item.get("highlighted_skills", []),
                    "gaps": item.get("gaps", []),
                    "recommended_questions_for_interview": item.get("recommended_questions", []),
                    "metadata": item.get("metadata", {})
                })
            
            logger.info(f"Returning {len(results)} top jobs")
            return results
            
        except (EmbeddingError, OpenSearchError, RerankError) as e:
            logger.error(f"Error in search_jobs_by_resume: {e}")
            raise
    
    def search_resumes_by_job(
        self,
        job_description: str,
        job_id: Optional[str] = None,
        top_k_initial: int = 100,
        top_k_final: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Mode B: Find top resumes for a job
        
        Args:
            job_description: Job description text
            job_id: Optional job identifier
            top_k_initial: Initial candidates from vector search
            top_k_final: Final results after reranking
            
        Returns:
            List of top matching resumes with scores and reasons
        """
        try:
            # 1. Generate embedding for job
            logger.info(f"Generating embedding for job {job_id or 'new'}")
            job_embedding = self.bedrock.generate_embedding(job_description)
            
            # 2. Vector search in resumes index
            logger.info(f"Searching resumes index (top_k={top_k_initial})")
            
            # Log available resumes count
            available_resumes_count = None
            if settings.USE_MOCK:
                from app.clients.opensearch_client import opensearch_client
                available_resumes = opensearch_client._mock_data_storage.get(self.RESUMES_INDEX, [])
                available_resumes_count = len(available_resumes)
                logger.info(f"Available resumes in index: {available_resumes_count}")
            
            candidates = self.opensearch.vector_search(
                index_name=self.RESUMES_INDEX,
                query_vector=job_embedding,
                top_k=top_k_initial
            )
            
            if not candidates:
                logger.warning(f"No resumes found in vector search. Available resumes in index: {available_resumes_count if available_resumes_count is not None else 'N/A'}")
                return []
            
            logger.info(f"Found {len(candidates)} candidates from vector search")
            
            # 3. Prepare candidates for reranking
            candidates_for_rerank = []
            for candidate in candidates[:top_k_initial]:
                candidates_for_rerank.append({
                    "candidate_index": len(candidates_for_rerank),
                    "title": candidate.get("name", "N/A"),
                    "text_excerpt": candidate.get("text_excerpt", ""),
                    "metadata": candidate.get("metadata", {}),
                    "vector_score": candidate.get("_score", 0.0),
                    "resume_id": candidate.get("_id", "")
                })
            
            # 4. Rerank with Bedrock LLM
            logger.info(f"Reranking {len(candidates_for_rerank)} candidates")
            query_summary = f"Job Description: {job_description[:500]}..."
            reranked = self.bedrock.rerank_candidates(
                query=query_summary,
                candidates=candidates_for_rerank,
                top_k=top_k_final
            )
            
            # 5. Format results
            results = []
            for item in reranked:
                results.append({
                    "rank": item.get("rank", 0),
                    "resume_id": item.get("resume_id", ""),
                    "resume_name": item.get("title", "N/A"),
                    "experience_summary": item.get("text_excerpt", "")[:300],
                    "match_score": item.get("vector_score", 0.0),
                    "rerank_score": item.get("rerank_score", 0.0),
                    "fit_reasons": item.get("rerank_reason", ""),
                    "risks": item.get("gaps", []),
                    "highlighted_skills": item.get("highlighted_skills", []),
                    "suggested_next_step": "ติดต่อเพื่อสัมภาษณ์" if item.get("rerank_score", 0) > 0.7 else "พิจารณาเพิ่มเติม",
                    "metadata": item.get("metadata", {})
                })
            
            logger.info(f"Returning {len(results)} top resumes")
            return results
            
        except (EmbeddingError, OpenSearchError, RerankError) as e:
            logger.error(f"Error in search_resumes_by_job: {e}")
            raise


matching_service = MatchingService()

