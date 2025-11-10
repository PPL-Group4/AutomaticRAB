import csv
import hashlib
import logging
import os
import re
from pathlib import Path
from typing import List

from automatic_job_matching.security import SecurityValidationError
from automatic_job_matching.service.exact_matcher import AhsRow

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security.audit")

class AhspCiptaKaryaRepository:
    def __init__(self):
        base_dir = Path(__file__).resolve().parent.parent
        self.csv_path = base_dir / "data" / "AHSP_CIPTA_KARYA.csv"
        self._cache = None
        self._expected_hash = os.getenv("AHSP_CIPTA_KARYA_SHA256")
        self._integrity_checked = False

    def _validate_integrity(self) -> None:
        if self._integrity_checked:
            return

        if not self._expected_hash:
            security_logger.warning(
                "Environment variable AHSP_CIPTA_KARYA_SHA256 not set; skipping CSV integrity validation."
            )
            self._integrity_checked = True
            return

        try:
            with open(self.csv_path, mode="rb") as csv_file:
                digest = hashlib.sha256(csv_file.read()).hexdigest()
        except FileNotFoundError as exc:
            raise SecurityValidationError("Reference CSV file is missing.") from exc

        if digest != self._expected_hash:
            raise SecurityValidationError("CSV integrity validation failed.")
        security_logger.info("Verified integrity of %s", self.csv_path.name)
        self._integrity_checked = True

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

        s = re.sub(r"[^a-z0-9\s\.\-']", " ", s.replace("/", " "))
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    def _load_csv(self) -> List[AhsRow]:
        if self._cache is not None:
            return self._cache

        rows = []
        try:
            self._validate_integrity()
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
        except SecurityValidationError as exc:
            logger.error("CSV integrity validation failed: %s", exc)
            security_logger.error("CSV integrity validation failed: %s", exc)
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
