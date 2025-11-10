import io
import logging

logger = logging.getLogger(__name__)

class DocumentProcessingService:
    def extract_text_from_file(self, file_content: bytes, filename: str) -> str:
        """Extract text from various document formats"""
        try:
            # Handle text files
            if filename.endswith('.txt'):
                return file_content.decode('utf-8', errors='ignore')

            # Handle PDF files
            elif filename.endswith('.pdf'):
                try:
                    import PyPDF2
                    pdf_file = io.BytesIO(file_content)
                    pdf_reader = PyPDF2.PdfReader(pdf_file)

                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"

                    return text.strip()

                except ImportError:
                    logger.error("PyPDF2 not available for PDF processing")
                    return "PDF text extraction failed - PyPDF2 not available"
                except Exception as e:
                    logger.error(f"PDF processing error: {e}")
                    return f"PDF text extraction failed: {str(e)}"

            # Handle DOCX files
            elif filename.endswith('.docx'):
                try:
                    from docx import Document
                    docx_file = io.BytesIO(file_content)
                    doc = Document(docx_file)

                    text = ""
                    for paragraph in doc.paragraphs:
                        text += paragraph.text + "\n"

                    return text.strip()

                except ImportError:
                    logger.error("python-docx not available for DOCX processing")
                    return "DOCX text extraction failed - python-docx not available"
                except Exception as e:
                    logger.error(f"DOCX processing error: {e}")
                    return f"DOCX text extraction failed: {str(e)}"

            # Handle other file types
            else:
                return f"Unsupported file format: {filename}. Supported formats: txt, pdf, docx"

        except Exception as e:
            logger.error(f"Document processing error: {e}")
            return f"Document processing failed: {str(e)}"
