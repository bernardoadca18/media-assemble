"""
FASE 4 — Resolução de assets visuais a partir do banco local.

Lê `midia.keywords_busca` de cada cena e busca no banco local
(data/assets_local/, organizado por tags/pastas) antes de acionar fallback.

Convenção do banco local:
- Cada subpasta de `data/assets_local/` representa uma tag
- O nome da pasta é a tag (ex: `data/assets_local/doctor_doom/`)
- Arquivos dentro da pasta são assets daquela tag
- Tags são normalizadas: minúsculas, sem acentos, underscores
- Match é parcial: "Doctor Doom comic art" casa com `doctor_doom`
"""
import logging
import re
import unicodedata
from pathlib import Path
from typing import NamedTuple

from pipeline.config import settings
from pipeline.schemas import Cena, Roteiro
from services.visual.fallback_scraper import buscar_asset_externo

logger = logging.getLogger("services.visual.asset_resolver")

# Diretório base do banco local
BANCO_LOCAL_DIR = Path("data/assets_local")

# Cache do índice em memória
_indice_cache: dict[str, list[Path]] | None = None


class AssetResolvido(NamedTuple):
    """Resultado da resolução de asset para uma cena."""
    path: Path
    origem: str


def _normalizar_tag(texto: str) -> str:
    """
    Normaliza texto para uso como tag:
    - Remove acentos
    - Converte para minúsculas
    - Substitui espaços e caracteres especiais por underscores
    - Remove caracteres não alfanuméricos (exceto underscores)
    """
    # Remove acentos
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    # Converte para minúsculas
    texto = texto.lower()
    # Substitui espaços e hífens por underscores
    texto = re.sub(r"[\s\-]+", "_", texto)
    # Remove caracteres não alfanuméricos (exceto underscores)
    texto = re.sub(r"[^a-z0-9_]", "", texto)
    # Remove underscores duplicados
    texto = re.sub(r"_+", "_", texto)
    # Remove underscores do início e fim
    texto = texto.strip("_")
    return texto


def _construir_indice_local() -> dict[str, list[Path]]:
    """
    Constrói índice do banco local varrendo `data/assets_local/`.

    Retorna dict onde:
    - Chave: tag normalizada
    - Valor: lista de caminhos de arquivos para aquela tag

    A estrutura esperada é:
        data/assets_local/
            doctor_doom/
                img1.jpg
                img2.png
            naruto/
                clip1.mp4
    """
    indice: dict[str, list[Path]] = {}

    if not BANCO_LOCAL_DIR.exists():
        logger.warning(
            "asset_resolver.banco_local_nao_encontrado",
            extra={"caminho": str(BANCO_LOCAL_DIR)},
        )
        return indice

    # Extensões válidas para assets
    extensoes_validas = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm", ".mov"}

    for pasta in BANCO_LOCAL_DIR.iterdir():
        # Ignora arquivos soltos e diretórios especiais
        if not pasta.is_dir():
            continue
        if pasta.name.startswith("_") or pasta.name.startswith("."):
            continue

        tag = _normalizar_tag(pasta.name)
        if not tag:
            continue

        arquivos = []
        for arquivo in pasta.rglob("*"):
            if arquivo.is_file() and arquivo.suffix.lower() in extensoes_validas:
                arquivos.append(arquivo)

        if arquivos:
            indice[tag] = arquivos
            logger.debug(
                "asset_resolver.tag_indexada",
                extra={"tag": tag, "total_arquivos": len(arquivos)},
            )

    logger.info(
        "asset_resolver.indice_construido",
        extra={"total_tags": len(indice), "total_arquivos": sum(len(v) for v in indice.values())},
    )
    return indice


def _obter_indice() -> dict[str, list[Path]]:
    """
    Retorna o índice do banco local, construindo-o na primeira chamada.
    """
    global _indice_cache
    if _indice_cache is None:
        _indice_cache = _construir_indice_local()
    return _indice_cache


def _recarregar_indice() -> None:
    """
    Força a reconstrução do índice (útil após adicionar novos assets).
    """
    global _indice_cache
    _indice_cache = _construir_indice_local()


def _buscar_no_banco_local(keywords: list[str]) -> AssetResolvido | None:
    """
    Busca asset no banco local a partir de keywords.

    Tenta casar cada keyword (normalizada) contra as tags do índice.
    Match é parcial: keyword "doctor_doom" casa com tag "doctor_doom"
    e também keyword "doctor" casa com tag "doctor_doom".

    Args:
        keywords: Lista de keywords da cena

    Returns:
        AssetResolvido se encontrar, None caso contrário
    """
    indice = _obter_indice()

    if not indice:
        return None

    # Normaliza todas as keywords
    keywords_normalizadas = [_normalizar_tag(kw) for kw in keywords]
    keywords_normalizadas = [kw for kw in keywords_normalizadas if kw]

    if not keywords_normalizadas:
        return None

    # Tenta match exato primeiro
    for kw in keywords_normalizadas:
        if kw in indice:
            arquivos = indice[kw]
            if arquivos:
                return AssetResolvido(path=arquivos[0], origem="banco_local")

    # Tenta match parcial (keyword contida na tag ou tag contida na keyword)
    for kw in keywords_normalizadas:
        for tag, arquivos in indice.items():
            # Keyword contém a tag (ex: "doctor_doom_art" contém "doctor_doom")
            if kw in tag or tag in kw:
                if arquivos:
                    return AssetResolvido(path=arquivos[0], origem="banco_local")

    return None


async def resolver_asset_cena(cena: Cena) -> bool:
    """
    Resolve asset para uma única cena.

    Tenta primeiro o banco local, depois fallback externo (Pexels).
    Preenche `cena.asset_resolvido_path` e `cena.asset_origem`.

    Args:
        cena: Cena a ter seu asset resolvido

    Returns:
        True se asset foi resolvido (local ou fallback), False se não encontrou
    """
    keywords = cena.midia.keywords_busca
    fallback_query = cena.midia.fallback_query

    # Tenta banco local primeiro
    resultado_local = _buscar_no_banco_local(keywords)
    if resultado_local:
        cena.asset_resolvido_path = str(resultado_local.path)
        cena.asset_origem = resultado_local.origem
        logger.info(
            "asset_resolver.asset_local_resolvido",
            extra={
                "cena_id": cena.cena_id,
                "keywords": keywords,
                "path": str(resultado_local.path),
            },
        )
        return True

    # Fallback externo (Pexels)
    logger.info(
        "asset_resolver.buscando_fallback",
        extra={"cena_id": cena.cena_id, "fallback_query": fallback_query},
    )

    resultado_externo = await buscar_asset_externo(
        keywords=keywords,
        fallback_query=fallback_query,
        tipo_asset=cena.midia.tipo_asset_preferencial.value,
    )

    if resultado_externo:
        cena.asset_resolvido_path = str(resultado_externo.path)
        cena.asset_origem = resultado_externo.origem
        logger.info(
            "asset_resolver.asset_fallback_resolvido",
            extra={
                "cena_id": cena.cena_id,
                "origem": resultado_externo.origem,
                "path": str(resultado_externo.path),
            },
        )
        return True

    # Nenhum asset encontrado
    cena.revisao_manual_necessaria = True
    logger.warning(
        "asset_resolver.asset_nao_encontrado",
        extra={
            "cena_id": cena.cena_id,
            "keywords": keywords,
            "fallback_query": fallback_query,
        },
    )
    return False


async def resolver_assets_do_roteiro(roteiro: Roteiro) -> Roteiro:
    """
    Resolve assets para todas as cenas de um roteiro.

    Para cada cena:
    1. Tenta encontrar asset no banco local (data/assets_local/)
    2. Se não encontrar, aciona fallback externo (Pexels)
    3. Se ainda não encontrar, marca cena para revisão manual

    Args:
        roteiro: Roteiro com cenas a terem seus assets resolvidos

    Returns:
        O mesmo roteiro com `asset_resolvido_path` e `asset_origem`
        preenchidos em cada cena (ou `revisao_manual_necessaria=True`)
    """
    logger.info(
        "asset_resolver.iniciando",
        extra={
            "video_id": roteiro.metadata.video_id,
            "total_cenas": len(roteiro.cenas),
        },
    )

    cenas_resolvidas = 0
    cenas_fallback = 0
    cenas_sem_asset = 0

    for i, cena in enumerate(roteiro.cenas):
        logger.debug(
            "asset_resolver.processando_cena",
            extra={
                "cena_id": cena.cena_id,
                "ordem": i + 1,
                "total": len(roteiro.cenas),
            },
        )

        resolvido = await resolver_asset_cena(cena)

        if resolvido:
            if cena.asset_origem == "banco_local":
                cenas_resolvidas += 1
            else:
                cenas_fallback += 1
        else:
            cenas_sem_asset += 1

    logger.info(
        "asset_resolver.concluido",
        extra={
            "video_id": roteiro.metadata.video_id,
            "cenas_banco_local": cenas_resolvidas,
            "cenas_fallback": cenas_fallback,
            "cenas_sem_asset": cenas_sem_asset,
        },
    )

    return roteiro
