
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
        "no": ["no", "nomor", "urut"],
        "uraian": [
            "uraian",
            "uraian pekerjaan",
            "deskripsi",
            "pekerjaan",
            "jenis barang/jasa",
            "uraian pekerjaan/barang",
            "keterangan",  # <– NEW synonym
            "uraian barang",  # <– NEW synonym
        ],
        "volume": [
            "volume",
            "vol",
            "qty",
            "jumlah",
            "kuantitas"  # <– NEW synonym
        ],
        "satuan": [
            "satuan",
            "unit",
            "satuan unit",
            "uom"
        ],
        "price": [
            "harga",
            "harga satuan",
            "nilai satuan",
            "harga/unit",
            "biaya",
        ],
        "total_price": [
            "jumlah harga",
            "total harga",
            "jumlah",
            "harga total",
            "total biaya",
            "grand total"
        ]
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

            # ✅ Add here:
            core_headers = {"uraian", "satuan", "volume"}
            if best_y is not None and core_headers.issubset(found_headers):
                return best_y

        # If we found a row with header keywords, use it
        # After scoring rows
        if best_score >= 2:
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

        # Debugging output
        print("Merged header row candidates:", [frag.text for frag in merged])
        print("Mapping:", mapping, "Missing:", missing)

        # ✅ Require at least the core headers
        core_headers = {"uraian", "satuan", "volume"}
        if not core_headers.issubset(mapping.keys()):
            print("⚠️ Skipping candidate row, missing core headers")
            return {}, list(self.EXPECTED_HEADERS.keys()), originals

        # After mapping headers
        boundaries = {}
        sorted_headers = sorted(mapping.items(), key=lambda kv: kv[1].x)

        for i, (key, frag) in enumerate(sorted_headers):
            left = frag.x
            right = sorted_headers[i + 1][1].x if i + 1 < len(sorted_headers) else float("inf")
            boundaries[key] = (left, right)

        print("Column boundaries:", boundaries)

        return mapping, missing, originals

