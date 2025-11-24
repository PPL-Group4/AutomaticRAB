from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import re
from pdf_parser.services.header_mapper import PdfHeaderMapper, TextFragment
from pdf_parser.services.normalizer import _UNIT_TOKENS   # ✅ import tokens

@dataclass
class ParsedRow:
    page: int
    y: float
    values: Dict[str, str]   # {"no": "1", "uraian": "Pekerjaan A", "volume": "10", "satuan": "m2"}

class PdfRowParser:
    """
    Parse table-like rows from PDF text fragments:
    1) Detect header row (via PdfHeaderMapper).
    2) Compute x-boundaries from mapped header fragments.
    3) Group fragments into data rows by y.
    4) Assign each fragment to a column by x-boundary and merge cell text.
    """

    def __init__(
        self,
        y_bucket_precision: int = 1,
        y_tolerance: float = 0.8,
        header_gap_px: float = 6.0,
        x_merge_gap: float = 40.0
    ):
        self.mapper = PdfHeaderMapper(y_tolerance=y_tolerance)
        self.y_bucket_precision = y_bucket_precision
        self.y_tolerance = y_tolerance
        self.header_gap_px = header_gap_px
        self.x_merge_gap = x_merge_gap

    def parse(self, fragments, vlines_by_page=None):
        parsed_rows = []
        last_boundaries = {}
        last_header_y = None

        frags_by_page = self._group_fragments_by_page(fragments)

        for page in sorted(frags_by_page.keys()):
            page_frags = frags_by_page[page]
            vlines = (vlines_by_page or {}).get(page) or []

            boundaries, header_y = self._detect_headers_and_boundaries(
                page_frags, last_boundaries, last_header_y, vlines
            )

            if boundaries is None:
                continue

            # update state
            last_boundaries = boundaries
            last_header_y = header_y

            # 3. body fragments
            body_frags = [f for f in page_frags if f.y > header_y + self.header_gap_px]

            # 4. rows grouped by y
            grouped_rows = self._group_by_y(body_frags)

            # 5. assign & merge
            for y, row_frags in grouped_rows:
                cells = self._assign_to_columns(row_frags, boundaries)
                values = {k: self._merge_cell_text(v) for k, v in cells.items()}

                # heuristic
                if not any(ch.isdigit() for ch in values.get("volume", "")) \
                        and values.get("satuan", "").lower() not in _UNIT_TOKENS:
                    values["satuan"] = ""
                    values["volume"] = "0"

                parsed_rows.append(ParsedRow(page=page, y=y, values=values))

        return parsed_rows, last_boundaries



    def _compute_x_boundaries_with_lines(
        self,
        header_map: Dict[str, TextFragment],
        vlines: List[float],
    ) -> Dict[str, Tuple[float, float]]:
        keys_positions = sorted([(k, v.x) for k, v in header_map.items()], key=lambda kv: kv[1])
        vxs = sorted(vlines)

        def span_around(x):
            left = float("-inf")
            right = float("inf")
            for i in range(len(vxs) - 1):
                if vxs[i] <= x < vxs[i + 1]:
                    left, right = vxs[i], vxs[i + 1]
                    break
            if x < vxs[0]:
                left, right = float("-inf"), vxs[0]
            elif x >= vxs[-1]:
                left, right = vxs[-1], float("inf")
            return (left, right)

        boundaries: Dict[str, Tuple[float, float]] = {}
        for key, x in keys_positions:
            boundaries[key] = span_around(x)
        return boundaries
    def _compute_x_boundaries(
        self,
        header_map: Dict[str, TextFragment]
    ) -> Dict[str, Tuple[float, float]]:
        """
        Compute x-boundaries between header columns without vertical lines.
        Falls back to midpoint between consecutive headers.
        """
        keys_positions = sorted(
            [(k, v.x) for k, v in header_map.items()],
            key=lambda kv: kv[1]
        )
        xs = [x for _k, x in keys_positions]

        mids = []
        for i in range(len(xs) - 1):
            mids.append((xs[i] + xs[i + 1]) / 2.0)

        boundaries: Dict[str, Tuple[float, float]] = {}
        for idx, (key, x) in enumerate(keys_positions):
            if idx == 0:
                xmin = float("-inf")
                xmax = mids[0] if mids else float("inf")
            elif idx == len(keys_positions) - 1:
                xmin = mids[-1] if mids else float("-inf")
                xmax = float("inf")
            else:
                xmin = mids[idx - 1]
                xmax = mids[idx]
            boundaries[key] = (xmin, xmax)
        return boundaries

    def _group_by_y(self, row_frags: List[TextFragment]) -> List[Tuple[float, List[TextFragment]]]:
        if not row_frags:
            return []
        buckets = defaultdict(list)
        for f in row_frags:
            buckets[round(f.y, self.y_bucket_precision)].append(f)

        normalized_rows = []
        for y_key, frags in buckets.items():
            frags_sorted = sorted(frags, key=lambda f: f.y)
            current_group = [frags_sorted[0]]
            groups = []
            for f in frags_sorted[1:]:
                if abs(f.y - current_group[-1].y) <= self.y_tolerance:
                    current_group.append(f)
                else:
                    groups.append(current_group)
                    current_group = [f]
            groups.append(current_group)
            for g in groups:
                avg_y = sum(f.y for f in g) / len(g)
                normalized_rows.append((avg_y, g))
        normalized_rows.sort(key=lambda t: t[0])
        normalized_rows = [(y, sorted(g, key=lambda f: f.x)) for y, g in normalized_rows]
        return normalized_rows

    def _assign_to_columns(
            self,
            row_frags: List[TextFragment],
            boundaries: Dict[str, Tuple[float, float]],
            header_map: Optional[Dict[str, TextFragment]] = None,
    ) -> Dict[str, List[TextFragment]]:
        cells: Dict[str, List[TextFragment]] = {k: [] for k in boundaries.keys()}

        header_map = header_map or {}
        centers: Dict[str, float] = {}
        for key, (xmin, xmax) in boundaries.items():
            header_fragment = header_map.get(key)
            if header_fragment:
                centers[key] = header_fragment.x
                continue

            if xmin == float("-inf") and xmax == float("inf"):
                centers[key] = 0.0
            elif xmin == float("-inf"):
                centers[key] = xmax - 50.0
            elif xmax == float("inf"):
                centers[key] = xmin + 50.0
            else:
                centers[key] = (xmin + xmax) / 2.0

        for f in row_frags:
            # pick nearest column center
            key = min(boundaries.keys(), key=lambda k: abs(f.x - centers[k]))

            # ✅ Smarter fallback:
            if key == "satuan":
                # if text looks too long or has multiple words → it's probably a description
                if len(f.text.split()) > 2 or len(f.text) > 15:
                    key = "uraian"
                else:
                    token = re.sub(r"[^a-z0-9]", "", (f.text or "").lower())
                    if token and token not in _UNIT_TOKENS and cells.get("uraian"):
                        key = "uraian"

            cells[key].append(f)

        for key in cells:
            cells[key].sort(key=lambda f: f.x)
        return cells

    def _merge_cell_text(self, frags: List[TextFragment]) -> str:
        """
        Merge text fragments into a single cell string.
        Joins consecutive fragments with spaces, trims whitespace.
        """
        if not frags:
            return ""
        pieces = []
        for frag in frags:
            if frag.text and frag.text.strip():
                pieces.append(frag.text.strip())
        return " ".join(pieces).strip()
    
    def _group_fragments_by_page(self, fragments):
        frags_by_page = defaultdict(list)
        for f in fragments:
            frags_by_page[f.page].append(f)
        return frags_by_page


    def _detect_headers_and_boundaries(self, page_frags, last_boundaries, last_header_y, vlines):
        mapping, missing, _originals = self.mapper.map_headers(page_frags)
        core_headers = {"uraian", "satuan", "volume"}

        if mapping and core_headers.issubset(mapping.keys()):
            header_y = self.mapper.find_header_y(page_frags)
            boundaries = (self._compute_x_boundaries_with_lines(mapping, vlines)
                        if vlines else self._compute_x_boundaries(mapping))
            return boundaries, header_y

        if last_boundaries and last_header_y is not None:
            # reuse last valid header
            boundaries = last_boundaries
            header_y = (min(f.y for f in page_frags) - self.header_gap_px - 1.0 
                        if page_frags else last_header_y)
            return boundaries, header_y

        return None, None




