"""
File Processing Service
Extracts text from PDF, DOCX, and TXT files
"""
import io
from typing import Optional
from PyPDF2 import PdfReader
from docx import Document

from app.core.logging import get_logger
from app.core.exceptions import FileProcessingError

logger = get_logger(__name__)


class FileProcessor:
    """Service for processing uploaded files"""
    
    @staticmethod
    def extract_text(file_content: bytes, file_name: str) -> str:
        """
        Extract text from file based on extension
        
        Args:
            file_content: File content as bytes
            file_name: Original file name
            
        Returns:
            Extracted text
        """
        try:
            file_ext = file_name.lower().split('.')[-1]
            
            if file_ext == 'pdf':
                return FileProcessor._extract_from_pdf(file_content)
            elif file_ext in ['docx', 'doc']:
                return FileProcessor._extract_from_docx(file_content)
            elif file_ext == 'txt':
                return file_content.decode('utf-8', errors='ignore')
            else:
                raise FileProcessingError(f"Unsupported file type: {file_ext}")
                
        except Exception as e:
            logger.error(f"Error extracting text from {file_name}: {e}")
            raise FileProcessingError(f"Failed to extract text: {str(e)}")
    
    @staticmethod
    def _extract_from_pdf(file_content: bytes) -> str:
        """Extract text from PDF"""
        try:
            pdf_file = io.BytesIO(file_content)
            reader = PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            raise FileProcessingError(f"PDF extraction error: {str(e)}")
    
    @staticmethod
    def _extract_from_docx(file_content: bytes) -> str:
        """Extract text from DOCX"""
        try:
            doc_file = io.BytesIO(file_content)
            doc = Document(doc_file)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            raise FileProcessingError(f"DOCX extraction error: {str(e)}")


file_processor = FileProcessor()

