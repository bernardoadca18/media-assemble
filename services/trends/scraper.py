"""
FASE 1 — Coleta de tendências.

Responsável por buscar tópicos em alta em fontes externas (X/Twitter, Google
Trends, Reddit, YouTube trending) para o nicho informado. Substitui a fonte
`{{ $node["Webhook"].json.body.raw_trends }}` que antes era enviada
manualmente/externamente para o fluxo n8n — aqui o próprio pipeline Python
passa a ser responsável por buscar esses dados.

Escopo da Fase 1:
- Implementar ao menos 1 fonte real (ex: Google Trends via `pytrends` ou
  scraping direto) de forma funcional.
- As demais fontes podem ficar como stubs anotados com TODO, retornando
  lista vazia, sem quebrar o pipeline.
- Sempre devolver uma lista de strings "cruas" (texto livre), que serão
  limpas/estruturadas pelo normalizer.py em seguida.
"""
import logging

logger = logging.getLogger("services.trends.scraper")


async def coletar_tendencias(nicho: str) -> list[str]:
    """
    Retorna uma lista de tópicos/tendências brutos (texto livre) relevantes
    para o nicho informado.

    TODO (Fase 1): implementar fontes reais. Sugestão de fontes por nicho:
      - cultura_pop: Google Trends (categoria Entertainment), Reddit
        (r/anime, r/movies, r/gaming), YouTube trending.
      - tecnologia: Hacker News, Google Trends (categoria Technology).
      - futebol: Google Trends (categoria Sports), APIs de notícias esportivas.
    """
    logger.warning("coletar_tendencias: usando stub — nenhuma fonte real implementada ainda")
    return []
