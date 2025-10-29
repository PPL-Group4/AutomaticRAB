import re, unicodedata
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger("excel_parser")  

def _normalize(s: str) -> str:
    if s is None: return ""
    s = str(s)
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode('ascii')
    s = s.strip().lower()
    s = re.sub(r'[\.\:\(\)\-/]', ' ', s)  
    s = re.sub(r'\s+', ' ', s).strip()
    return s

HEADER_SYNONYMS = {
    'no':            ['no', 'nomor', 'no urut'],
    'uraian':        ['uraian', 'uraian pekerjaan', 'deskripsi', 'keterangan'],
    'satuan':        ['satuan', 'unit'],
    'volume':        ['volume', 'vol', 'qty', 'kuantitas', 'quantity'],
    'harga_satuan':  ['harga satuan', 'harga', 'harga rupiah', 'hrg satuan'],
    'jumlah':        ['jumlah', 'jumlah harga', 'total', 'total harga', 'biaya'],
    'kode_analisa':  ['kode analisa', 'kode', 'analisa'],
}
REQUIRED = ['no','uraian','satuan','volume']

def map_headers(header_row: List[str]) -> Tuple[Dict[str,int], List[str], Dict[str,str]]:
    normed = [_normalize(h) for h in header_row]
    mapping, originals = {}, {}
    for canon, variants in HEADER_SYNONYMS.items():
        vset = {_normalize(v) for v in variants}
        for idx, h in enumerate(normed):
            if h in vset:
                mapping[canon] = idx
                originals[canon] = header_row[idx]
                break

    missing = [k for k in REQUIRED if k not in mapping]

    if missing:
        logger.warning(
            "Header mapping: missing_required=%s detected=%s raw_header=%s",
            missing, list(mapping.keys()), header_row
        )
    else:
        logger.debug("Header mapping ok: %s (raw=%s)", mapping, header_row)

    return mapping, missing, originals

def find_header_row(rows: List[List[str]], scan_first: int = 200) -> int:
    best_idx, best_hits = -1, -1
    to_scan = rows[:scan_first]
    for i, row in enumerate(to_scan):
        mapping, _, _ = map_headers([str(c or '') for c in row])
        hits = len(mapping)
        if hits > best_hits:
            best_idx, best_hits = i, hits
    logger.debug("find_header_row: scanned=%d best_idx=%d best_hits=%d",
                 len(to_scan), best_idx, best_hits)
    return best_idx