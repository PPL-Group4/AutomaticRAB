# pdf_parser/services/normalizer.py
from decimal import Decimal, InvalidOperation
from typing import Dict
import re

# common unit tokens in RAB documents (lowercased, punctuation-free)
_UNIT_TOKENS = {
    "ls", "m", "m1", "m2", "m3", "mm", "cm", "cm2", "cm3", "kg", "ton",
    "l", "lt", "ltr", "bh", "buah", "unit", "set", "paket", "hari",
    "jam", "mtr", "btg", "batang", "lembar", "lbr", "orang", "pak",
    "roll", "pcs", "meter", "pasang", "kegiatan", "psg", "titik", "ttk"
}

_ROMAN_RE = re.compile(r'^\s*([IVXLCDM]+)\.?\s*(.*)$', re.I)
# handles "1Penyiapan", "2. Sosialisasi", "3-Something", "4) Another"
_LEADING_DIGIT_RE = re.compile(r'^\s*(\d+)(?:[\.)-]?\s*)?(.*)$')
_LEADING_ALPHA_RE = re.compile(r'^\s*([a-zA-Z])[\.)]\s*(.*)$')


def _split_number_from_desc(desc: str) -> tuple[str, str]:
    m = _ROMAN_RE.match(desc)
    if m:
        numeral, rest = m.group(1), m.group(2)
        following = desc[m.end(1):]
        if following:
            first = following[0]
            if first.isalnum():
                return ("", desc)
        return (numeral, rest)
    m = _LEADING_DIGIT_RE.match(desc)
    if m:
        return (m.group(1), m.group(2))
    m = _LEADING_ALPHA_RE.match(desc)
    if m:
        return (m.group(1), m.group(2))
    return ("", desc)


def _decimal(val) -> Decimal:
    if not val:
        return Decimal("0")
    try:
        s = str(val).strip()
        # normalize 1.000,50 -> 1000.50, 1,000.50 -> 1000.50
        s = s.replace(" ", "")
        if "," in s and "." not in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        s = re.sub(r"[^\d\.-]", "", s)
        return Decimal(s) if s not in {"", "-", "."} else Decimal("0")
    except (InvalidOperation, AttributeError):
        return Decimal("0")


def _clean_unit_and_desc(unit_text: str) -> tuple[str, str]:
    t = (unit_text or "").strip()
    if not t:
        return ("", "")

    toks = t.split()
    unit = ""
    extras = []
    for tok in toks:
        key = re.sub(r"[^a-z0-9]", "", tok.lower())
        if not unit and key in _UNIT_TOKENS:
            unit = tok
        else:
            extras.append(tok)

    # 🔹 If the "unit" candidate is clearly not a real unit, reject
    if not unit:
        return (t, "")
    if len(toks) > 2:  # suspiciously long
        return (t, "")
    return (" ".join(extras).strip(), unit)


def _fix_desc_with_unit(desc: str) -> tuple[str, str]:
    """
    If description ends with a known unit token, strip it and return separately.
    Example: "Bouwplank m1" -> ("Bouwplank", "m1")
    """
    toks = desc.split()
    if len(toks) < 2:
        return desc, ""
    last = re.sub(r"[^a-z0-9]", "", toks[-1].lower())
    if last in _UNIT_TOKENS:
        return " ".join(toks[:-1]).strip(), toks[-1]
    return desc, ""


class PdfRowNormalizer:
    """Converts raw row values into normalized DTOs with heuristics."""

    @staticmethod
    def normalize(row: Dict[str, str]) -> Dict[str, object]:
        # raw fields
        num = (row.get("no") or "").strip()
        desc = (row.get("uraian") or "").strip()
        unit_raw = (row.get("satuan") or "").strip()
        orig_desc_empty = not desc  # track if description was originally empty

        # 1. Force header-like rows into description only (skip number extraction)
        # But first check if we should extract a number prefix even from headers
        if desc and not num:
            guess_num, rest = _split_number_from_desc(desc)
            if guess_num and rest.strip():
                num = guess_num.strip()
                desc = rest.strip()

        # Now check if it's a header
        if desc.isupper() or "pekerjaan" in desc.lower():
            return {
                "number": num,
                "description": desc,
                "volume": Decimal("0"),
                "unit": "",
                "analysis_code": "",
                "price": Decimal("0"),
                "total_price": Decimal("0"),
            }

        # 2. Split number glued into description (already done in step 1 for most cases)
        # This handles any remaining cases where step 1 didn't extract
        if desc and not num:
            guess_num, rest = _split_number_from_desc(desc)
            if guess_num and rest.strip():
                num = guess_num.strip()
                desc = rest.strip()

        # 3. If unit contains words, push extras back into description
        extra_desc_from_unit, real_unit = _clean_unit_and_desc(unit_raw)
        if extra_desc_from_unit:
            desc = (desc + " " + extra_desc_from_unit).strip()

        # 4. If description ends with a unit token, extract it
        fixed_desc, desc_unit = _fix_desc_with_unit(desc)
        if desc_unit:
            desc = fixed_desc
            real_unit = real_unit or desc_unit

        # 4b. If original description was empty but unit_raw contains header-like text,
        # blank the unit (the text was already moved to description via extra_desc_from_unit)
        final_unit = real_unit or unit_raw
        if orig_desc_empty and not real_unit and unit_raw:
            # Check if unit_raw looks like a header (multi-word, contains 'pekerjaan', or ALLCAPS)
            token_lc = re.sub(r"[^a-z0-9]", "", unit_raw.lower())
            looks_like_header = (
                    "pekerjaan" in unit_raw.lower()
                    or "sistem" in unit_raw.lower()
                    or "manajemen" in unit_raw.lower()
                    or unit_raw.isupper()
                    or len(unit_raw.split()) > 2
            )
            if looks_like_header and token_lc not in _UNIT_TOKENS:
                final_unit = ""

        # 4c. If a short numeric prefix looks like a continuation fragment, keep it in description
        vol_candidate = _decimal(row.get("volume"))
        if (
            num
            and num.isdigit()
            and desc
            and len(desc.split()) <= 3
            and len(desc) <= 25
            and not (final_unit or "").strip()
            and vol_candidate == Decimal("0")
        ):
            desc = f"{num} {desc}".strip()
            num = ""

        # 5. Normalize numerics
        vol = vol_candidate
        price = _decimal(row.get("price"))
        total = _decimal(row.get("total_price"))

        return {
            "number": num,
            "description": desc,
            "volume": vol,
            "unit": final_unit,
            "analysis_code": (row.get("analysis_code") or "").strip(),
            "price": price,
            "total_price": total,
        }
