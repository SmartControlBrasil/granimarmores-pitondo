import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
INNER = ROOT / "hando"
if str(INNER) not in sys.path:
    sys.path.append(str(INNER))
