"""Punto de entrada del escáner de bibliotecas (proceso independiente).

La GUI ejecuta este script como subproceso: si algo falla de forma nativa
durante el escaneo (archivos a medio descargar, etc.), el proceso muere pero
la aplicación sigue viva y lo reintenta.

Salida estándar:
  SCAN_OK <n>            → índice guardado con n fondos
  SCAN_FAIL <mensaje>    → error (código de salida 1)
"""

import os
import sys

# ruta raíz del proyecto (tres niveles arriba: app/library/scanner_main.py)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    from app.library import indexer

    try:
        previous = indexer.load_index()
        items = indexer.build_index(previous)
        indexer.save_index(items)
    except Exception as e:  # noqa: BLE001
        print(f"SCAN_FAIL {e}", flush=True)
        return 1

    print(f"SCAN_OK {len(items)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
