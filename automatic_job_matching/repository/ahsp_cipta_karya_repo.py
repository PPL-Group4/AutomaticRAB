import csv
import logging
import re
from pathlib import Path
from typing import List
from automatic_job_matching.service.exact_matcher import AhsRow

logger = logging.getLogger(__name__)

class AhspCiptaKaryaRepository:
    def __init__(self):
        base_dir = Path(__file__).resolve().parent.parent
        self.csv_path = base_dir / "data" / "AHSP_CIPTA_KARYA.csv"
        self._cache = None

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        s = text.strip().lower()
        s = (
            s.replace("×", "x")
             .replace("²", "2")
             .replace("³", "3")
             .replace("‘", "'")
             .replace("’", "'")
             .replace("”", '"')
             .replace("“", '"')
        )

        s = re.sub(r"[^a-z0-9\s\.\-']", " ", s)
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    def _load_csv(self) -> List[AhsRow]:
        if self._cache is not None:
            return self._cache

        rows = []
        try:
            with open(self.csv_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, delimiter=";")

                for row in reader:
                    row = {k.strip().upper(): (v or "").strip() for k, v in row.items()}

                    code = row.get("NO") or row.get(";NO") or ""
                    name = row.get("URAIAN PEKERJAAN") or ""
                    if not code or not name:
                        continue

                    normalized_code = code.replace("-", ".").replace(" ", "")
                    normalized_name = self._normalize_text(name)

                    rows.append(
                        AhsRow(
                            id=len(rows) + 1,
                            code=normalized_code,
                            name=normalized_name,
                        )
                    )

            self._cache = rows
            logger.info(f"Loaded {len(rows)} normalized rows from {self.csv_path}")
        except FileNotFoundError:
            logger.error(f"CSV not found at {self.csv_path}")
            self._cache = []

        return self._cache


    def by_code_like(self, code: str) -> List[AhsRow]:
        code = (code or "").strip().upper()
        if not code:
            return []

        dot_variant = code.replace("-", ".")
        dash_variant = code.replace(".", "-")
        variants = {code, dot_variant, dash_variant}

        results = []
        for v in variants:
            results.extend([r for r in self._load_csv() if v in r.code.upper()])

        logger.debug(f"by_code_like found {len(results)} matches for code={code}")
        return results

    def by_name_candidates(self, head_token: str) -> List[AhsRow]:
        logger.debug("Cipta: by_name_candidates called with head_token=%s", head_token)
        token = self._normalize_text(head_token)
        if not token:
            return []

        results = [
            r for r in self._load_csv()
            if r.name.startswith(token)
        ][:200]

        logger.debug(f"by_name_candidates found {len(results)} matches for token={token}")
        return results

    def get_all_ahs(self) -> List[AhsRow]:
        return self._load_csv()
