"""Point d'entrée des exécutables PyInstaller."""

import sys

from fukuroku.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
