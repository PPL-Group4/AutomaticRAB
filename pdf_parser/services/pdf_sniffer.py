import os
from django.core.exceptions import ValidationError


class PdfSniffer:
    """Checks PDF file integrity using header + EOF marker"""

    def is_valid(self, file_path):
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext != ".pdf":
            raise ValidationError("Unsupported file extension. Only .pdf allowed.")

        try:
            with open(file_path, "rb") as f:
                # check header 
                header = f.read(4)
                if header != b"%PDF":
                    raise ValidationError("Invalid or corrupted PDF file (bad header).")

                # check EOF marker 
                try:
                    f.seek(-20, os.SEEK_END)
                except OSError:
                    raise ValidationError("Corrupted PDF file (too small).")

                tail = f.read().strip()
                if b"%%EOF" not in tail:
                    raise ValidationError("Corrupted PDF file (missing EOF marker).")

        except ValidationError:
            raise
        except Exception:
            raise ValidationError("Could not read PDF file.")

        return None  
