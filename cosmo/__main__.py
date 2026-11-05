"""Point d'entrée de `python -m cosmo`."""

import io
import sys

from cosmo.cli import main

if __name__ == "__main__":
    # Hors d'un terminal, Windows n'encode pas en UTF-8 par défaut : `transmets "→";` échouerait.
    for flux in (sys.stdin, sys.stdout, sys.stderr):
        if isinstance(flux, io.TextIOWrapper):
            flux.reconfigure(encoding="utf-8")
    sys.exit(main())
