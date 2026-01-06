"""
Custom Exceptions
"""
from fastapi import HTTPException, status


class ResumeMatchingException(HTTPException):
    """Base exception for resume matching errors"""
    pass


class FileProcessingError(ResumeMatchingException):
    """Error processing uploaded file"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File processing error: {detail}"
        )


class EmbeddingError(ResumeMatchingException):
    """Error generating embeddings"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation error: {detail}"
        )


class OpenSearchError(ResumeMatchingException):
    """Error with OpenSearch operations"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OpenSearch error: {detail}"
        )


class RerankError(ResumeMatchingException):
    """Error during reranking"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reranking error: {detail}"
        )

