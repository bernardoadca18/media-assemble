"""
Configuração de logging estruturado (JSON) para todo o projeto.
Chamar `configurar_logging()` uma única vez, no entrypoint (main.py).
"""
import logging
import sys
from contextvars import ContextVar

# ContextVar para propagar video_id em logs de uma mesma execução
_video_id_context: ContextVar[str | None] = ContextVar("video_id", default=None)


def set_video_id(video_id: str | None) -> None:
    """Define o video_id no contexto atual para correlacionar logs."""
    _video_id_context.set(video_id)


def get_video_id() -> str | None:
    """Recupera o video_id do contexto atual."""
    return _video_id_context.get()


class VideoIdFilter(logging.Filter):
    """Filtro de log que injeta video_id do contexto em cada registro."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.video_id = get_video_id() or ""
        return True


def configurar_logging(nivel: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    formato = logging.Formatter(
        fmt='{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
        '"logger": "%(name)s", "video_id": "%(video_id)s", "message": "%(message)s"}'
    )
    handler.setFormatter(formato)
    handler.addFilter(VideoIdFilter())

    root = logging.getLogger()
    root.setLevel(nivel)
    root.addHandler(handler)
