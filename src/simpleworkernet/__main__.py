# simpleworkernet/__main__.py
"""
Точка входа для запуска модуля напрямую: python -m simpleworkernet
"""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())