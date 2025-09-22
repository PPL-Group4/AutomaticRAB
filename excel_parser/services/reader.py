from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import List, Dict, Iterable, Tuple

from django.core.files.uploadedfile import UploadedFile
from excel_parser.models import Project, RabEntry

class UnsupportedFileError(Exception):
    pass

class ParseError(Exception):
    pass

HEADER_ALIASES = {
    "number": {"no", "no.", "nomor", "number", "kode"},
    "description": {"uraian pekerjaan", "uraian", "deskripsi", "pekerjaan", "job description"},
    "volume": {"volume", "vol", "vol.", "qty", "jumlah", "kuantitas"},
    "unit": {"satuan", "unit"},
    "analysis_code": {"kode analisa", "kode", "analysis code"},
    "price": {"harga satuan", "harga_satuan", "price", "harga"},
    "total_price": {"jumlah harga", "total harga", "total", "total_price"}
}




def _norm(s) -> str:
    return str(s or "").strip().lower()

def _match_header(cell: str) -> Tuple[str | None, str]:
    """Return (canonical_key, raw) or (None, raw)."""
    key = None
    n = _norm(cell)
    for canon, aliases in HEADER_ALIASES.items():
        if n in aliases:
            key = canon
            break
    return key, cell

_THOUSAND_DOT_DECIMAL_COMMA = re.compile(r"^\d{1,3}(\.\d{3})+,\d+$")
_THOUSAND_COMMA_DECIMAL_DOT = re.compile(r"^\d{1,3}(,\d{3})+\.\d+$")

def parse_decimal(val) -> Decimal:
    if val is None or str(val).strip() == "":
        return Decimal("0")
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))

    s = str(val).strip()

    # If the string has no digits at all, treat as 0
    if not any(ch.isdigit() for ch in s):
        return Decimal("0")

    # 🚩 New rule: if string looks like a formula ("7 = 5 x 6"), skip it
    if "=" in s or "x" in s.lower():
        return Decimal("0")

    # Handle common formats
    if _THOUSAND_DOT_DECIMAL_COMMA.match(s):
        s = s.replace(".", "").replace(",", ".")
    elif _THOUSAND_COMMA_DECIMAL_DOT.match(s):
        s = s.replace(",", "")
    else:
        if "," in s and "." not in s:
            s = s.replace(",", ".")
        elif "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")

    s = re.sub(r"[^\d.-]", "", s)

    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")

class _BaseReader:
    def iter_rows(self, file: UploadedFile) -> Iterable[List]:
        raise NotImplementedError

class _XLSXReader(_BaseReader):
    def iter_rows(self, file: UploadedFile) -> Iterable[List]:
        from openpyxl import load_workbook
        pos = file.tell()
        file.seek(0)
        wb = load_workbook(filename=file, data_only=True, read_only=True)
        ws = wb.worksheets[0]
        for row in ws.iter_rows(values_only=True):
            yield list(row)
        file.seek(pos)

class _XLSReader(_BaseReader):
    def iter_rows(self, file: UploadedFile) -> Iterable[List]:
        import xlrd
        pos = file.tell()
        data = file.read()
        wb = xlrd.open_workbook(file_contents=data)
        sh = wb.sheet_by_index(0)
        for r in range(sh.nrows):
            yield [sh.cell_value(r, c) for c in range(sh.ncols)]
        file.seek(pos)

def _ext_of(file: UploadedFile) -> str:
    name = (file.name or "").lower()
    if name.endswith(".xlsx"):
        return "xlsx"
    if name.endswith(".xls"):
        return "xls"
    return ""

def make_reader(file: UploadedFile) -> _BaseReader:
    ext = _ext_of(file)
    if ext == "xlsx":
        return _XLSXReader()
    if ext == "xls":
        return _XLSReader()
    raise UnsupportedFileError("Only .xls and .xlsx are supported")

@dataclass
class ParsedRow:
    number: str
    description: str
    volume: Decimal
    unit: str
    analysis_code: str
    price: Decimal
    total_price: Decimal

def _find_header_map(rows: Iterable[List]) -> Tuple[Dict[str, int], int]:
    """
    Scan up to first 50 rows to detect header line and map columns.
    Returns (mapping, header_row_index)
    """
    cache = list(rows)
    limit = min(len(cache), 50)  # scan deeper, not just 10 rows

    for i in range(limit):
        row = cache[i]
        seen = {}
        for idx, cell in enumerate(row):
            canon, _ = _match_header(cell)
            if canon and canon not in seen:
                seen[canon] = idx

        # require at least number + description + unit
        if {"number", "description", "unit"} <= set(seen.keys()):
            # optional: add volume/price/total_price if present
            return seen, i

    raise ParseError("Required headers not found (No, Uraian Pekerjaan, Volume, Satuan)")

def _rows_after(cache: List[List], start_idx: int) -> Iterable[List]:
    for r in range(start_idx + 1, len(cache)):
        yield cache[r]

def _parse_rows(cache: List[List], colmap: Dict[str, int]) -> List[ParsedRow]:
    out: List[ParsedRow] = []

    for idx, row in enumerate(_rows_after(cache, start_idx=colmap["_header_row"])):  # type: ignore
        def cell(col):
            i = colmap.get(col)
            return row[i] if i is not None and i < len(row) else None

        desc = (cell("description") or "").strip() if isinstance(cell("description"), str) else cell("description")
        if not desc:
            continue

        out.append(ParsedRow(
            number=str(cell("number") or "").strip(),
            description=str(desc),
            volume=parse_decimal(cell("volume")),
            unit=str(cell("unit") or "").strip(),
            analysis_code=str(cell("analysis_code") or "").strip(),
            price=parse_decimal(cell("price")),
            total_price=parse_decimal(cell("total_price")),
        ))

    return out

class ExcelImporter:
    """
    High-level façade used by views/tasks/tests.
    SRP: import an uploaded excel into RabEntry rows
    OCP: new readers can be added without modifying this class
    """
    def import_file(self, file: UploadedFile) -> int:
        reader = make_reader(file)
        # materialize all rows to detect header first
        cache = list(reader.iter_rows(file))
        colmap, header_row = _find_header_map(cache)
        colmap["_header_row"] = header_row  # keep header position

        project, created = Project.objects.get_or_create(
            program="Default Program",
            kegiatan="Default Activity",
            pekerjaan="Imported from Excel",
            lokasi="Not Specified",
            tahun_anggaran=2025, # Or get this from the file/user
            defaults={'source_filename': file.name}
        )

        parsed = _parse_rows(cache, colmap)
        count = 0
        for idx, p in enumerate(parsed, start=1):
            RabEntry.objects.create(
                project=project,
                entry_type=RabEntry.EntryType.ITEM, # Defaulting to ITEM for now
                item_number=p.number,
                description=p.description,
                volume=p.volume,
                unit=p.unit,
                row_index=idx,
            )
            count += 1
        return count

def preview_file(file: UploadedFile):
    reader = make_reader(file)
    cache = list(reader.iter_rows(file))
    colmap, header_row = _find_header_map(cache)
    colmap["_header_row"] = header_row

    parsed = _parse_rows(cache, colmap)
    return [
        {
            "number": row.number,
            "description": row.description,
            "volume": float(row.volume),
            "unit": row.unit,
            "analysis_code": row.analysis_code,
            "price": float(row.price),
            "total_price": float(row.total_price),
        }
        for row in parsed
    ]
