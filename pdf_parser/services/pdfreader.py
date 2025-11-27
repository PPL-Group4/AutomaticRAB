from dataclasses import dataclass
from typing import List, Protocol

import pdfplumber


@dataclass
class TextFragment:
    page: int
    x: float
    y: float
    text: str


class FragmentExtractor(Protocol):
    """Interface for fragment extraction strategies."""
    def extract(self, file_path: str) -> List[TextFragment]:
        ...


class PdfReader(FragmentExtractor):
    """Extracts text fragments with coordinates from PDF files."""

    def extract(self, file_path: str) -> List[TextFragment]:
        fragments: List[TextFragment] = []

        with pdfplumber.open(file_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                words = page.extract_words(x_tolerance=1, y_tolerance=1, keep_blank_chars=False)

                for w in words:
                    fragments.append(TextFragment(
                        page=page_number,
                        x=w["x0"],
                        y=w["top"],
                        text=w["text"]
                    ))

        return fragments
