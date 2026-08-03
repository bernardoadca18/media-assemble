"""
FASE 4 — Fallback de assets via fontes externas (Pexels, DuckDuckGo, yt-dlp) —
NÃO implementado nesta base. Acionado apenas quando o banco local não possui
asset compatível com as keywords da cena. Ver seção 4 do guia de arquitetura
quanto a critérios de licenciamento antes de usar qualquer fonte externa.
"""


async def buscar_asset_externo(keywords: list[str]) -> str | None:
    raise NotImplementedError("Fase 4: implementar fallback externo com fontes licenciadas.")
