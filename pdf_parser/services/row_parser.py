from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
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

    def parse(
        self,
        fragments: List[TextFragment],
        vlines_by_page: Optional[Dict[int, List[float]]] = None
    ) -> Tuple[List[ParsedRow], Dict[str, Tuple[float, float]]]:
        parsed_rows: List[ParsedRow] = []
        last_boundaries: Dict[str, Tuple[float, float]] = {}

        # 1. Group fragments by page
        frags_by_page = defaultdict(list)
        for f in fragments:
            frags_by_page[f.page].append(f)

        # 2. Process each page
        for page in sorted(frags_by_page.keys()):
            page_frags = frags_by_page[page]

            # Detect headers
            mapping, missing, _originals = self.mapper.map_headers(page_frags)
            core_headers = {"uraian", "satuan", "volume"}
            if not mapping or not core_headers.issubset(mapping.keys()):
                continue  # skip if no valid header found

            header_y = self.mapper.find_header_y(page_frags)

            # Boundaries: use vertical lines if available, else fallback
            vlines = (vlines_by_page or {}).get(page) or []
            if vlines:
                boundaries = self._compute_x_boundaries_with_lines(mapping, vlines)
            else:
                boundaries = self._compute_x_boundaries(mapping)

            last_boundaries = boundaries

            # 3. Take only fragments below the header row
            body_frags = [f for f in page_frags if f.y > header_y + self.header_gap_px]

            # 4. Group by row (y-axis)
            grouped_rows = self._group_by_y(body_frags)

            # 5. Assign fragments to columns & merge
            for y, row_frags in grouped_rows:
                cells = self._assign_to_columns(row_frags, boundaries)
                values = {k: self._merge_cell_text(v) for k, v in cells.items()}

                # ✅ Section-row heuristic:
                # If no volume and no valid unit, treat as a section header
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
            boundaries: Dict[str, Tuple[float, float]]
    ) -> Dict[str, List[TextFragment]]:
        cells: Dict[str, List[TextFragment]] = {k: [] for k in boundaries.keys()}

        centers = {
            k: (xmin + xmax) / 2 if xmax < float("inf") else xmin + 200
            for k, (xmin, xmax) in boundaries.items()
        }

        for f in row_frags:
            # pick nearest column center
            key = min(boundaries.keys(), key=lambda k: abs(f.x - centers[k]))

            # ✅ Smarter fallback:
            if key == "satuan":
                # if text looks too long or has multiple words → it's probably a description
                if len(f.text.split()) > 2 or len(f.text) > 15:
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



