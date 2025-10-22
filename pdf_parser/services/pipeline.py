# pdf_parser/services/pipeline.py
from typing import List, Dict, Any
import re, logging
from decimal import Decimal
from pdf_parser.services.pdfreader import PdfReader
from pdf_parser.services.row_parser import PdfRowParser
from pdf_parser.services.normalizer import PdfRowNormalizer
from pdf_parser.services.job_matcher import match_description  

logger = logging.getLogger(__name__)

def is_url_or_link(text: str) -> bool:
    """Check if text is a URL or contains URL-like patterns."""
    if not text:
        return False
    text_lower = text.lower().strip()
    # Check for common URL patterns
    url_patterns = [
        r'^https?://',  # starts with http:// or https://
        r'^www\.',      # starts with www.
        r'\.com',       # contains .com
        r'\.id',        # contains .id
        r'\.org',       # contains .org
        r'\.net',       # contains .net
        r'\.gov',       # contains .gov
    ]
    return any(re.search(pattern, text_lower) for pattern in url_patterns)

def filter_url_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove rows that are URLs or links."""
    filtered = []
    for row in rows:
        desc = row.get("description", "")
        # Skip rows where description is a URL
        if not is_url_or_link(desc):
            filtered.append(row)
    return filtered

def merge_broken_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge rows where description got split across multiple lines.
    Example:
      row1 = {"description": "Fasilitas Sarana, Prasarana dan Alat", "unit": "", "volume": 0}
      row2 = {"description": "Kesehatan", "unit": "", "volume": 0}
    → merge into one: {"description": "Fasilitas Sarana, Prasarana dan Alat Kesehatan", ...}
    """
    merged = []
    measurement_units = {"mm", "cm", "cm2", "cm3", "m2", "m3"}
    for row in rows:
        if merged and not row.get("number") and row["volume"] == 0:
            if not row["unit"]:
                merged[-1]["description"] = (
                    merged[-1]["description"] + " " + row["description"]
                ).strip()
                continue
            unit_lower = row["unit"].strip().lower()
            if unit_lower in measurement_units:
                suffix = row["description"].strip()
                if row["unit"]:
                    suffix = f"{suffix} {row['unit']}".strip()
                merged[-1]["description"] = (
                    merged[-1]["description"] + " " + suffix
                ).strip()
                continue

            merged[-1]["description"] = (
                merged[-1]["description"] + " " + row["description"]
            ).strip()
        else:
            merged.append(row)
    return merged


def parse_pdf_to_dtos(path: str) -> List[Dict[str, Any]]:
    """
    Orchestrates full pipeline:
    1. Extract raw text fragments (PdfReader).
    2. Parse into row structures (PdfRowParser).
    3. Normalize into clean DTO dicts (PdfRowNormalizer).
    4. Merge broken rows.
    5. Filter out URL/link rows.
    6. Run automatic job matching on each description.
    """
    reader = PdfReader()
    fragments = reader.extract(path)

    if not fragments:
        return []

    row_parser = PdfRowParser()
    parsed_rows, *boundaries = row_parser.parse(fragments)

    normalized = [PdfRowNormalizer.normalize(r.values) for r in parsed_rows]
    normalized = merge_broken_rows(normalized)
    normalized = filter_url_rows(normalized)

    # 🆕 Step 6: perform automatic job matching
    enriched_rows = []
    for row in normalized:
        desc = row.get("description") or ""
        match_info = match_description(desc)

        try:
            volume = Decimal(str(row.get("volume") or "0"))
            price = Decimal(str(row.get("harga satuan") or row.get("price") or "0"))
            total_price = volume * price
        except Exception:
            volume = Decimal("0")
            price = Decimal("0")
            total_price = Decimal("0")

        enriched_rows.append({
            **row,
            "volume": float(volume),
            "price": float(price),
            "total_price": float(total_price),
            "job_match_status": match_info.get("status"),
            "job_match": match_info.get("match"),
            "job_match_error": match_info.get("error"),
        })

    logger.info("Parsed %d rows with job matching from %s", len(enriched_rows), path)
    return enriched_rows
