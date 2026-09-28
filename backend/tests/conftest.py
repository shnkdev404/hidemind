import os
import tempfile
from pathlib import Path

# Isolate tests from the real DB and from real credentials - must run before `app` is imported.
_tmp = Path(tempfile.mkdtemp(prefix="munshi-test-"))
os.environ["DB_PATH"] = str(_tmp / "test.db")
os.environ["HINDSIGHT_URL"] = ""
os.environ["GROQ_API_KEY"] = ""
