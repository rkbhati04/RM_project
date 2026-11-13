"""Entry point for DoH/3 (DNS-over-HTTP/3) RQ1, RQ2, and RQ3 Privacy Analysis.

Delegates execution to doh3_rq123_analysis.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src directory is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from doh3_rq123_analysis import main

if __name__ == "__main__":
    sys.exit(main())

