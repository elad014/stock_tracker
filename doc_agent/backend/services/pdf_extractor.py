from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

_PDF_MAGIC = b"%PDF-"


class PdfExtractError(ValueError):
    """Raised when PDF bytes cannot be turned into usable text."""


def extract_pdf_text(data: bytes) -> str:
    """Extract concatenated page text from a PDF payload."""
    if not data.startswith(_PDF_MAGIC):
        raise PdfExtractError("File is not a valid PDF")

    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            # Many public filings set encryption flags but use an empty password.
            unlocked = reader.decrypt("")
            if not unlocked:
                raise PdfExtractError("PDF is encrypted")

        pages: list[str] = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            stripped = extracted.strip()
            if stripped:
                pages.append(stripped)
    except PdfExtractError:
        raise
    except PdfReadError as exc:
        raise PdfExtractError("File is not a valid PDF") from exc
    except Exception as exc:
        raise PdfExtractError("Failed to read PDF") from exc

    joined = "\n\n".join(pages).strip()
    if not joined:
        raise PdfExtractError("PDF contains no extractable text")
    return joined
