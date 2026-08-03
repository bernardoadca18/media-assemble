"""
Configuração de logging estruturado (JSON) para todo o projeto.
Chamar `configurar_logging()` uma única vez, no entrypoint (main.py).
"""
import logging
import sys


def configurar_logging(nivel: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    formato = logging.Formatter(
        fmt='{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
        '"logger": "%(name)s", "message": "%(message)s"}'
    )
    handler.setFormatter(formato)

    root = logging.getLogger()
    root.setLevel(nivel)
    root.addHandler(handler)
