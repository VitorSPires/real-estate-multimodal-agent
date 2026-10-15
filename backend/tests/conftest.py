"""Test environment: a throwaway data dir + database, and offline (canned) model answers.

Set before any `app` import, because settings and the engine are created at import time.
"""

import os
import tempfile

_data_dir = tempfile.mkdtemp(prefix="rema-tests-")
os.environ["DATA_DIR"] = _data_dir
os.environ["DATABASE_URL"] = f"sqlite:///{_data_dir}/test.db"
os.environ["LLM_PROVIDER"] = "fake"
