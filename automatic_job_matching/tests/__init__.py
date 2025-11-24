import sys
from unittest.mock import MagicMock

sys.modules["sentence_transformers"] = MagicMock()
