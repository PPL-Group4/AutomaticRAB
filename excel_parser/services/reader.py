from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import List, Dict, Iterable, Tuple
import string

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

_THOUSAND_DOT_DECIMAL_COMMA = re.compile(r"^\d{1,3}(\.\d{3})+,\d+$")
_THOUSAND_COMMA_DECIMAL_DOT = re.compile(r"^\d{1,3}(,\d{3})+\.\d+$")

def classify_index_token(token: str) -> str:
    """Classify a No. cell into 'letter' | 'roman' | 'numeric' | 'none'."""
    if token is None:
        return "none"
    t = str(token).strip()
    if not t:
        return "none"
    t = t.rstrip(" .)")
    up = t.upper()
    if len(up) == 1 and up in string.ascii_uppercase:
        return "letter"
    if re.fullmatch(r"[IVXLCDM]+", up):
        return "roman"
    tn = up.replace(".", "").replace(",", "")
    if tn.isdigit():
        return "numeric"
    return "none"

def parse_decimal(val) -> Decimal:
    if val is None or str(val).strip() == "":
        return Decimal("0")
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))

    s = str(val).strip()
    if not any(ch.isdigit() for ch in s):
        return Decimal("0")
    if "=" in s or re.search(r"\d+\s*[xX]\s*\d+", s):
        return Decimal("0")
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
    is_section: bool = False
    index_kind: str = "none"
    section_letter: str | None = None
    section_roman: str | None = None
    section_type: str | None = None  # NEW

def _find_header_map(rows: Iterable[List]) -> Tuple[Dict[str, int], int]:
    cache = list(rows)
    limit = min(len(cache), 50)
    for i in range(limit):
        row = cache[i]
        seen = {}
        for idx, cell in enumerate(row):
            if cell is None:
                continue
            normed = _norm(cell)
            canon = None
            for key, aliases in HEADER_ALIASES.items():
                if normed in {a.lower().strip() for a in aliases}:
                    canon = key
                    break
            if canon and canon not in seen:
                seen[canon] = idx
        if {"number", "description", "unit"} <= set(seen.keys()):
            return seen, i
    raise ParseError("Required headers not found (need at least No, Uraian Pekerjaan, and Satuan)")

def _rows_after(cache: List[List], start_idx: int) -> Iterable[List]:
    for r in range(start_idx + 1, len(cache)):
        yield cache[r]

def _is_section_row(number: str, desc: str) -> bool:
    if number:
        kind = classify_index_token(number)
        if kind in ("letter", "roman"):
            return True
        if kind == "numeric":
            return False
    if desc and isinstance(desc, str) and desc.strip() and desc.strip().isupper():
        return True
    return False

def _parse_rows(cache: List[List], colmap: Dict[str, int]) -> List[ParsedRow]:
    out: List[ParsedRow] = []
    current_letter: str | None = None
    current_roman: str | None = None

    for idx, row in enumerate(_rows_after(cache, start_idx=colmap["_header_row"])):
        def cell(col):
            i = colmap.get(col)
            return row[i] if i is not None and i < len(row) else None

        number = str(cell("number") or "").strip()
        desc = (cell("description") or "").strip() if isinstance(cell("description"), str) else cell("description")
        if not desc:
            continue

        unit_val = str(cell("unit") or "").strip()
        vol_cell = cell("volume")

        index_kind = classify_index_token(number)
        is_section = _is_section_row(number, str(desc))

        if is_section:
            if index_kind == "letter":
                volume_result = parse_decimal(vol_cell)
            else:
                volume_result = Decimal("0")
        else:
            volume_result = parse_decimal(vol_cell)

        if is_section:
            if index_kind == "letter":
                current_letter = str(desc)
                current_roman = None
            elif index_kind == "roman":
                current_roman = str(desc)

        parsed_row = ParsedRow(
            number=number,
            description=str(desc),
            volume=volume_result,
            unit=unit_val,
            analysis_code=str(cell("analysis_code") or "").strip(),
            price=parse_decimal(cell("price")),
            total_price=parse_decimal(cell("total_price")),
            is_section=is_section,
            index_kind=index_kind,
            section_letter=current_letter,
            section_roman=current_roman,
            section_type="CATEGORY" if index_kind == "letter" else ("SECTION" if index_kind == "roman" else None)
        )
        out.append(parsed_row)
    return out

class ExcelImporter:
    def import_file(self, file: UploadedFile) -> int:
        reader = make_reader(file)
        cache = list(reader.iter_rows(file))
        colmap, header_row = _find_header_map(cache)
        colmap["_header_row"] = header_row
        project, _ = Project.objects.get_or_create(
            program="Default Program",
            kegiatan="Default Activity",
            pekerjaan="Imported from Excel",
            lokasi="Not Specified",
            tahun_anggaran=2025,
            defaults={'source_filename': file.name}
        )
        parsed = _parse_rows(cache, colmap)
        count = 0
        for idx, p in enumerate(parsed, start=1):
            RabEntry.objects.create(
                project=project,
                entry_type=RabEntry.EntryType.SECTION if p.is_section else RabEntry.EntryType.ITEM,
                item_number=p.number,
                description=p.description,
                volume=p.volume,
                unit=p.unit,
                analysis_code=p.analysis_code,
                unit_price=p.price,
                total_price=p.total_price,
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
            "is_section": row.is_section,
            "index_kind": row.index_kind,
            "section_letter": row.section_letter,
            "section_roman": row.section_roman,
            "section_type": row.section_type,
        }
        for row in parsed
    ]
