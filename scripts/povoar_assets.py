#!/usr/bin/env python3
"""
Script para povoar o banco de assets locais com imagens e vídeos do Pexels.

Uso:
    python scripts/povoar_assets.py --tag "doctor_doom" --tipo imagem --quantidade 20
    python scripts/povoar_assets.py --tag "marvel" --tipo video --quantidade 10
    python scripts/povoar_assets.py --arquivo lista_tags.txt
"""
import argparse
import asyncio
import hashlib
import logging
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Carrega .env
load_dotenv()

# Configurações
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
ASSETS_DIR = Path("data/assets_local")
CACHE_DIR = ASSETS_DIR / "_download_cache"

# Rate limit: 200 requisições/hora, 30 requisições/minuto
DELAY_ENTRE_REQUESTS = 2.5  # segundos


async def buscar_pexels_imagens(client: httpx.AsyncClient, query: str, per_page: int = 80, page: int = 1) -> dict:
    """Busca imagens no Pexels."""
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "per_page": per_page,
        "page": page,
        "orientation": "landscape",  # Melhor para vídeos
    }

    response = await client.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


async def buscar_pexels_videos(client: httpx.AsyncClient, query: str, per_page: int = 80, page: int = 1) -> dict:
    """Busca vídeos no Pexels."""
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "per_page": per_page,
        "page": page,
        "orientation": "landscape",
    }

    response = await client.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


async def baixar_arquivo(client: httpx.AsyncClient, url: str, destino: Path) -> bool:
    """Baixa arquivo e salva no destino."""
    try:
        response = await client.get(url, timeout=60.0, follow_redirects=True)
        response.raise_for_status()

        # Determina extensão
        content_type = response.headers.get("content-type", "")
        if "video" in content_type:
            ext = ".mp4"
        elif "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        else:
            ext = ".jpg"

        # Nome único com hash
        hash_conteudo = hashlib.md5(response.content).hexdigest()[:12]
        nome_final = destino.with_suffix(ext)

        # Salva
        nome_final.write_bytes(response.content)
        logger.info(f"✅ Baixado: {nome_final.name} ({len(response.content):,} bytes)")
        return True

    except Exception as e:
        logger.error(f"❌ Erro ao baixar {url}: {e}")
        return False


async def povoar_tag(tag: str, tipo: str, quantidade: int, modo: str = "diversificado"):
    """
    Povoa uma tag com assets do Pexels.

    Args:
        tag: Nome da tag (ex: "doctor_doom", "marvel")
        tipo: "imagem" ou "video"
        quantidade: Quantos assets baixar
        modo: "diversificado" (usa variações de query) ou "simples"
    """
    if not PEXELS_API_KEY:
        logger.error("❌ PEXELS_API_KEY não encontrada no .env")
        return 0

    # Cria diretório da tag
    tag_dir = ASSETS_DIR / tag
    tag_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"\n{'='*60}")
    logger.info(f"🏷️  Tag: {tag}")
    logger.info(f"📦 Tipo: {tipo}")
    logger.info(f"🎯 Quantidade: {quantidade}")
    logger.info(f"📁 Destino: {tag_dir}")
    logger.info(f"{'='*60}\n")

    # Queries variadas para diversificar
    queries = [tag.replace("_", " ")]

    if modo == "diversificado":
        queries.extend([
            f"{tag.replace('_', ' ')} art",
            f"{tag.replace('_', ' ')} wallpaper",
            f"{tag.replace('_', ' ')} 4k",
            f"{tag.replace('_', ' ')} aesthetic",
        ])

    baixados = 0
    tentativas = 0
    max_tentativas = quantidade * 3  # Triplica para compensar falhas

    async with httpx.AsyncClient(timeout=30.0) as client:
        page = 1

        while baixados < quantidade and tentativas < max_tentativas:
            for query in queries:
                if baixados >= quantidade:
                    break

                logger.info(f"🔍 Buscando: '{query}' (página {page})...")

                try:
                    if tipo == "imagem":
                        data = await buscar_pexels_imagens(client, query, per_page=80, page=page)
                        items = data.get("photos", [])
                    else:
                        data = await buscar_pexels_videos(client, query, per_page=80, page=page)
                        items = data.get("videos", [])

                    if not items:
                        logger.warning(f"⚠️  Nenhum resultado para '{query}'")
                        page += 1
                        continue

                    logger.info(f"📸 {len(items)} resultados encontrados")

                    # Baixar cada item
                    for i, item in enumerate(items):
                        if baixados >= quantidade:
                            break

                        tentativas += 1

                        # Extrair URL
                        if tipo == "imagem":
                            src = item.get("src", {})
                            url = src.get("large") or src.get("original") or src.get("medium")
                            photo_id = item.get("id")
                        else:
                            video_files = item.get("video_files", [])
                            # Prefere MP4 HD
                            video_file = None
                            for vf in video_files:
                                if vf.get("file_type") == "video/mp4" and vf.get("quality") in ["hd", "sd"]:
                                    video_file = vf
                                    break
                            if not video_file and video_files:
                                video_file = video_files[0]

                            url = video_file.get("link") if video_file else None
                            photo_id = item.get("id")

                        if not url:
                            continue

                        # Nome do arquivo
                        nome_base = f"pexels_{photo_id}"
                        destino = tag_dir / nome_base

                        # Verifica se já existe (por hash no nome)
                        arquivos_existentes = list(tag_dir.glob(f"pexels_{photo_id}.*"))
                        if arquivos_existentes:
                            logger.info(f"⏭️  Já existe: {arquivos_existentes[0].name}")
                            continue

                        # Baixa
                        sucesso = await baixar_arquivo(client, url, destino)
                        if sucesso:
                            baixados += 1

                        # Rate limit
                        await asyncio.sleep(DELAY_ENTRE_REQUESTS)

                    page += 1

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        logger.error("❌ Rate limit atingido! Aguarde 1 hora.")
                        logger.info(f"💡 Dica: Você pode usar outra API key ou esperar.")
                        return baixados
                    else:
                        logger.error(f"❌ Erro HTTP {e.response.status_code}: {e}")

                except Exception as e:
                    logger.error(f"❌ Erro inesperado: {e}")

                # Aguarda entre queries
                await asyncio.sleep(DELAY_ENTRE_REQUESTS)

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ Concluído: {baixados}/{quantidade} assets baixados")
    logger.info(f"📁 Local: {tag_dir}")
    logger.info(f"{'='*60}\n")

    return baixados


async def povoar_de_arquivo(arquivo: str, tipo: str, quantidade_por_tag: int):
    """
    Povoa múltiplas tags a partir de um arquivo de texto.

    Formato do arquivo (uma tag por linha):
    doctor_doom
    marvel
    dc_comics
    naruto
    anime
    """
    arquivo_path = Path(arquivo)
    if not arquivo_path.exists():
        logger.error(f"❌ Arquivo não encontrado: {arquivo}")
        return

    tags = arquivo_path.read_text().strip().split("\n")
    tags = [t.strip() for t in tags if t.strip() and not t.startswith("#")]

    logger.info(f"\n📋 Processando {len(tags)} tags do arquivo: {arquivo}")
    logger.info(f"📦 Tipo: {tipo}")
    logger.info(f"🎯 Quantidade por tag: {quantidade_por_tag}")
    logger.info(f"{'='*60}\n")

    total_baixados = 0

    for tag in tags:
        baixados = await povoar_tag(tag, tipo, quantidade_por_tag)
        total_baixados += baixados

        # Aguarda entre tags para não atingir rate limit
        await asyncio.sleep(5)

    logger.info(f"\n{'='*60}")
    logger.info(f"🎉 TOTAL: {total_baixados} assets baixados para {len(tags)} tags")
    logger.info(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Povoa banco de assets com imagens/vídeos do Pexels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Baixar 20 imagens sobre Doctor Doom
  python scripts/povoar_assets.py --tag "doctor_doom" --tipo imagem --quantidade 20

  # Baixar 10 vídeos sobre Marvel
  python scripts/povoar_assets.py --tag "marvel" --tipo video --quantidade 10

  # Baixar múltiplas tags de um arquivo
  python scripts/povoar_assets.py --arquivo tags.txt --tipo imagem --quantidade 15

  # Modo simples (sem variações de query)
  python scripts/povoar_assets.py --tag "naruto" --tipo imagem --quantidade 10 --modo simples
        """
    )

    parser.add_argument(
        "--tag",
        type=str,
        help="Nome da tag (ex: doctor_doom, marvel, naruto)"
    )
    parser.add_argument(
        "--tipo",
        type=str,
        choices=["imagem", "video"],
        required=True,
        help="Tipo de asset: imagem ou video"
    )
    parser.add_argument(
        "--quantidade",
        type=int,
        default=20,
        help="Quantidade de assets por tag (padrão: 20)"
    )
    parser.add_argument(
        "--arquivo",
        type=str,
        help="Arquivo com lista de tags (uma por linha)"
    )
    parser.add_argument(
        "--modo",
        type=str,
        choices=["diversificado", "simples"],
        default="diversificado",
        help="Modo de busca: diversificado (variações de query) ou simples"
    )

    args = parser.parse_args()

    if not args.tag and not args.arquivo:
        parser.error("Especifique --tag OU --arquivo")

    if args.tag and args.arquivo:
        parser.error("Use apenas --tag OU --arquivo, não ambos")

    # Executa
    if args.arquivo:
        asyncio.run(povoar_de_arquivo(args.arquivo, args.tipo, args.quantidade))
    else:
        asyncio.run(povoar_tag(args.tag, args.tipo, args.quantidade, args.modo))


if __name__ == "__main__":
    main()
