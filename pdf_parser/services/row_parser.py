from dataclasses import dataclass
from typing import Dict, List, Tuple
from collections import defaultdict

from pdf_parser.services.header_mapper import PdfHeaderMapper, TextFragment

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
        fragments: List[TextFragment]
    ) -> Tuple[List[ParsedRow], Dict[str, Tuple[float, float]]]:
        if not fragments:
            return [], {}

        frags_by_page = defaultdict(list)
        for f in fragments:
            if f.text and str(f.text).strip():
                frags_by_page[f.page].append(f)

        all_rows: List[ParsedRow] = []
        last_boundaries: Dict[str, Tuple[float, float]] = {}

        for page in sorted(frags_by_page.keys()):
            page_frags = frags_by_page[page]

            # 1) Map headers
            mapping, missing, _originals = self.mapper.map_headers(page_frags)
            if missing:
                # No recognizable header on this page —> skip parsing this page
                continue

            header_y = self.mapper.find_header_y(page_frags)
            boundaries = self._compute_x_boundaries(mapping)
            last_boundaries = boundaries

            # 2) Keep only data fragments strictly after the header row (larger y = lower on page)
            data_frags = [f for f in page_frags if (f.y - header_y) > self.header_gap_px]

            # 3) Group into row buckets by y
            row_buckets = self._group_by_y(data_frags)

            # 4) Build ParsedRow per bucket
            for bucket_y, row_frags in row_buckets:
                cells = self._assign_to_columns(row_frags, boundaries)
                # Merge text fragments per cell (stable left-to-right)
                merged_values = {k: self._merge_cell_text(v) for k, v in cells.items()}
                all_rows.append(ParsedRow(page=page, y=bucket_y, values=merged_values))

        # Sort final rows by (page asc, y asc)
        all_rows.sort(key=lambda r: (r.page, r.y))
        return all_rows, last_boundaries


    def _compute_x_boundaries(
        self,
        header_map: Dict[str, TextFragment]
    ) -> Dict[str, Tuple[float, float]]:
        keys_positions = sorted(
            [(k, v.x) for k, v in header_map.items()],
            key=lambda kv: kv[1]
        )
        xs = [x for _k, x in keys_positions]

        mids = []
        for i in range(len(xs) - 1):
            mids.append((xs[i] + xs[i+1]) / 2.0)

        # assign boundaries
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
        for f in row_frags:
            for key, (xmin, xmax) in boundaries.items():
                if xmin <= f.x < xmax:
                    cells[key].append(f)
                    break
        for key in cells:
            cells[key].sort(key=lambda f: f.x)
        return cells

    def _merge_cell_text(self, frags: List[TextFragment]) -> str:
        if not frags:
            return ""
        pieces = [frags[0].text.strip()]
        for prev, cur in zip(frags, frags[1:]):
            gap = cur.x - prev.x
            if gap <= self.x_merge_gap:
                pieces.append(cur.text.strip())
            else:
                pieces.append(cur.text.strip())
        # clean double spaces
        return " ".join(p for p in pieces if p).strip()
