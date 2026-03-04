"""
Text extraction for PDF and DOCX for RAG indexing (US-rag-pdf-docx).

- PDF: pypdf for native text; OCR fallback (PyMuPDF + Tesseract) when text is negligible.
- DOCX: python-docx for paragraph text.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Below this many characters per page (on average), treat PDF as image and run OCR
MIN_CHARS_PER_PAGE_OCR_THRESHOLD = 50


def extract_text_from_pdf(
    path: Path,
    *,
    ocr_enabled: bool = True,
    ocr_lang: str = "eng",
) -> str | None:
    """
    Extract text from a PDF. Uses pypdf first; if text is negligible, runs OCR fallback.

    Returns None on failure or if OCR is disabled and no text was extracted.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("pypdf not installed; cannot index PDF %s", path)
        return None

    try:
        reader = PdfReader(path)
        parts: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text and text.strip():
                parts.append(text.strip())
        text = "\n\n".join(parts) if parts else ""

        num_pages = len(reader.pages)
        if num_pages == 0:
            return None
        chars_per_page = len(text) / num_pages if num_pages else 0
        if text.strip() and chars_per_page >= MIN_CHARS_PER_PAGE_OCR_THRESHOLD:
            return text

        if ocr_enabled and (
            not text.strip() or chars_per_page < MIN_CHARS_PER_PAGE_OCR_THRESHOLD
        ):
            ocr_text = extract_text_from_pdf_ocr(path, lang=ocr_lang)
            if ocr_text and ocr_text.strip():
                return ocr_text
            if text.strip():
                return text  # use whatever pypdf got

        return text if text.strip() else None
    except Exception as e:
        logger.warning("PDF extraction failed for %s: %s", path, e)
        return None


def extract_text_from_pdf_ocr(path: Path, *, lang: str = "eng") -> str | None:
    """
    Render PDF pages to images and run Tesseract OCR. Returns concatenated text or None.

    Requires: PyMuPDF (pymupdf), Pillow, pytesseract, and Tesseract binary installed
    (e.g. brew install tesseract on macOS).
    """
    try:
        import pymupdf
    except ImportError:
        logger.debug("pymupdf not installed; cannot run PDF OCR for %s", path)
        return None
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        logger.debug("pytesseract or Pillow not installed for PDF OCR: %s", e)
        return None

    try:
        doc = pymupdf.open(path)
        parts: list[str] = []
        try:
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                if pix.width == 0 or pix.height == 0:
                    continue
                # Convert to PIL Image for pytesseract
                if pix.n == 4:
                    img = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
                    img = img.convert("RGB")
                elif pix.n == 3:
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                else:
                    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                    img = img.convert("RGB")
                page_text = pytesseract.image_to_string(img, lang=lang)
                if page_text and page_text.strip():
                    parts.append(page_text.strip())
        finally:
            doc.close()
        return "\n\n".join(parts) if parts else None
    except pytesseract.TesseractNotFoundError:
        logger.warning(
            "Tesseract not installed or not on PATH; cannot OCR PDF %s. "
            "Install e.g. brew install tesseract (macOS).",
            path,
        )
        return None
    except Exception as e:
        logger.warning("PDF OCR failed for %s: %s", path, e)
        return None


def extract_text_from_docx(path: Path) -> str | None:
    """Extract paragraph text from a Word .docx file. Returns None on failure."""
    try:
        from docx import Document
    except ImportError:
        logger.warning("python-docx not installed; cannot index DOCX %s", path)
        return None

    try:
        doc = Document(path)
        parts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        return "\n\n".join(parts) if parts else None
    except Exception as e:
        logger.warning("DOCX extraction failed for %s: %s", path, e)
        return None
