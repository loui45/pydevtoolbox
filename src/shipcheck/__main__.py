"""
__main__.py - Entry point when executed as `python -m shipcheck`.
"""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
