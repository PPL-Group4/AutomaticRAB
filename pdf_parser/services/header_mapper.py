from dataclasses import dataclass
import re
from collections import defaultdict


@dataclass
class TextFragment:
    page: int
    x: float
    y: float
    text: str


class PdfHeaderMapper:
    """
    Maps header fragments (from PdfReader) to standardized column names.
    """

    EXPECTED_HEADERS = {
        "no": ["no"],
        "uraian": ["uraian", "uraian pekerjaan", "deskripsi", "pekerjaan"],
        "volume": ["volume"],
        "satuan": ["satuan"],
    }

    def __init__(self, y_tolerance: float = 0.5):
        self.y_tolerance = y_tolerance

    def normalize(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", text.strip().lower())

    def find_header_y(self, fragments):
        """
        Finds the y-coordinate of the header row by looking for rows that contain
        expected header keywords, falling back to the row with most fragments.
        """
        if not fragments:
            return None
        
        y_buckets = defaultdict(list)
        for f in fragments:
            if f.text and f.text.strip():
                y_buckets[round(f.y, 1)].append(f)
        
        if not y_buckets:
            return None
        
        # First, try to find rows that contain expected header keywords
        header_keywords = set()
        for variants in self.EXPECTED_HEADERS.values():
            header_keywords.update(variants)
        
        best_y = None
        best_score = -1
        
        for y, frags in y_buckets.items():
            # Count how many expected headers are found in this row
            found_headers = set()
            for frag in frags:
                norm_text = self.normalize(frag.text)
                for keyword in header_keywords:
                    if keyword in norm_text:
                        found_headers.add(keyword)
            
            score = len(found_headers)
            if score > best_score:
                best_score = score
                best_y = y
        
        # If we found a row with header keywords, use it
        if best_score > 0:
            return best_y
        
        # Fallback: return the row with the most fragments
        return max(y_buckets.items(), key=lambda kv: len(kv[1]))[0]

    def map_headers(self, fragments):
        """
        Returns:
            mapping: dict of normalized header name -> fragment
            missing: list of expected headers not found
            originals: dict of normalized header -> original text
        """
        mapping = {}
        originals = {}
        found = set()

        if not fragments:
            return {}, list(self.EXPECTED_HEADERS.keys()), {}

        header_y = self.find_header_y(fragments)
        if header_y is None:
            return {}, list(self.EXPECTED_HEADERS.keys()), {}

        # Filter fragments close to header row
        row_frags = [
            f for f in fragments
            if f.text and f.text.strip() and abs(f.y - header_y) <= self.y_tolerance
        ]
        
        if not row_frags:
            return {}, list(self.EXPECTED_HEADERS.keys()), {}
        
        row_frags.sort(key=lambda f: f.x)

        # Merge consecutive fragments that are horizontally close
        merged = []
        current = None
        x_gap_tolerance = 50.0  # Maximum gap between fragments to merge

        for f in row_frags:
            if current is None:
                # First fragment
                current = TextFragment(f.page, f.x, f.y, f.text.strip())
            elif (abs(f.y - current.y) <= self.y_tolerance and 
                  f.x - current.x <= x_gap_tolerance):
                # Close horizontally and same row → merge
                current.text += " " + f.text.strip()
            else:
                # Too far apart, save current and start new
                merged.append(current)
                current = TextFragment(f.page, f.x, f.y, f.text.strip())

        # Don't forget the last fragment
        if current:
            merged.append(current)

        # Match merged headers against expected patterns
        for frag in merged:
            norm_text = self.normalize(frag.text)
            
            # Skip empty normalized text
            if not norm_text:
                continue
            
            # Try to match against each expected header
            for key, variants in self.EXPECTED_HEADERS.items():
                if key in found:  # Already found this header
                    continue
                    
                # Check if any variant matches
                for variant in variants:
                    if variant in norm_text:
                        mapping[key] = frag
                        originals[key] = frag.text.strip()
                        found.add(key)
                        break  # Stop checking other variants for this key

        missing = [k for k in self.EXPECTED_HEADERS if k not in found]
        return mapping, missing, originals