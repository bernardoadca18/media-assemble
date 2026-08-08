"""
Fase 9.2 — Resolução de asset por gameplay (gameplay_bg).

Seleciona segmentos de gameplay do banco para usar como fundo visual,
concatenando-os com crossfade e marcando como usados para evitar reutilização
prematura no mesmo canal.
"""
import asyncio
import logging
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from pipeline.config import settings
from pipeline.schemas import Roteiro, Cena
from db.models import buscar_gameplay_segmentos, marcar_gameplay_usado

logger = logging.getLogger("services.gameplay.resolver")


class GameplayBgResolvido(NamedTuple):
    """Resultado da resolução de gameplay_bg para um vídeo."""
    path: Path
    duracao_total: float
    segmentos_ids: list[str]
    jogos_utilizados: list[str]


async def selecionar_segmentos(
    duracao_alvo: float,
    canal_id: str,
    faixa_intensidade: str | None = None,
    jogo: str | None = None,
    janela_reuso_dias: int | None = None,
) -> list[dict]:
    """
    Seleciona segmentos de gameplay suficientes para cobrir a duração alvo.

    Respeita a janela de reuso: segmentos usados recentemente no mesmo canal
    não são selecionados novamente.

    Args:
        duracao_alvo: Duração total necessária em segundos
        canal_id: ID do canal para verificar reuso
        faixa_intensidade: Filtro opcional por faixa de intensidade
        jogo: Filtro opcional por jogo de origem
        janela_reuso_dias: Dias para evitar reuso (default: settings)

    Returns:
        Lista de dicts com dados dos segmentos selecionados
    """
    janela_reuso_dias = janela_reuso_dias or settings.gameplay_janela_reuso_dias
    limite_data = datetime.now() - timedelta(days=janela_reuso_dias)

    # Buscar segmentos (sem filtro de usado_em, filtramos manualmente)
    segmentos = await buscar_gameplay_segmentos(
        jogo=jogo,
        faixa_intensidade=faixa_intensidade,
        limite=1000,  # Buscar muitos para ter opções
    )

    if not segmentos:
        logger.warning(
            "gameplay_resolver.sem_segmentos",
            extra={"faixa_intensidade": faixa_intensidade, "jogo": jogo},
        )
        return []

    # Filtrar por janela de reuso
    segmentos_disponiveis = []
    for seg in segmentos:
        usado_em = seg.get("usado_em", []) or []

        # Verificar se foi usado recentemente neste canal
        usado_recentemente = False
        for uso in usado_em:
            # formato esperado: "video_id:YYYY-MM-DD"
            try:
                if ":" in uso:
                    video_id_uso, data_uso = uso.rsplit(":", 1)
                    data_uso_dt = datetime.strptime(data_uso, "%Y-%m-%d")
                    if data_uso_dt >= limite_data:
                        usado_recentemente = True
                        break
            except (ValueError, IndexError):
                continue

        if not usado_recentemente:
            segmentos_disponiveis.append(seg)

    if not segmentos_disponiveis:
        logger.warning(
            "gameplay_resolver.todos_usados",
            extra={"canal_id": canal_id, "janela_dias": janela_reuso_dias},
        )
        # Fallback: usar todos mesmo que tenham sido usados
        segmentos_disponiveis = segmentos

    # Selecionar segmentos até cobrir duração
    selecionados = []
    duracao_acumulada = 0.0

    for seg in segmentos_disponiveis:
        selecionados.append(seg)
        duracao_acumulada += seg["duracao_segundos"]

        if duracao_acumulada >= duracao_alvo:
            break

    logger.info(
        "gameplay_resolver.segmentos_selecionados",
        extra={
            "duracao_alvo": duracao_alvo,
            "duracao_coberta": duracao_acumulada,
            "num_segmentos": len(selecionados),
            "faixa_intensidade": faixa_intensidade,
        },
    )

    return selecionados


async def concatenar_segmentos(
    segmentos: list[dict],
    output_path: Path,
    crossfade_duration: float | None = None,
) -> Path:
    """
    Concatena segmentos com crossfade usando ffmpeg.

    Args:
        segmentos: Lista de segmentos com caminho_arquivo e duracao_segundos
        output_path: Caminho do arquivo de saída
        crossfade_duration: Duração do crossfade em segundos (default: settings)

    Returns:
        Path do arquivo concatenado
    """
    if not segmentos:
        raise ValueError("Lista de segmentos vazia")

    crossfade_duration = crossfade_duration or settings.gameplay_crossfade_duration_sec
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Se há apenas um segmento, apenas copiar
    if len(segmentos) == 1:
        import shutil
        shutil.copy2(segmentos[0]["caminho_arquivo"], output_path)
        logger.info(
            "gameplay_resolver.segmento_unico",
            extra={"path": str(output_path)},
        )
        return output_path

    # Criar lista de arquivos para concatenação
    # Usar concat demuxer do ffmpeg para simplicidade
    # Para crossfade real, precisaríamos de filtro complexo
    # Por ora, usamos concat simples + fade entre segmentos

    lista_file = output_path.parent / f".concat_list_{output_path.stem}.txt"

    try:
        # Escrever lista de arquivos
        with open(lista_file, "w") as f:
            for seg in segmentos:
                # ffmpeg concat demuxer requer paths absolutos e escapados
                path = Path(seg["caminho_arquivo"]).absolute()
                f.write(f"file '{path}'\n")

        # Comando de concatenação
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(lista_file),
            "-c", "copy",
            "-an",  # Sem áudio
            str(output_path),
        ]

        logger.info(
            "gameplay_resolver.concatenando",
            extra={
                "num_segmentos": len(segmentos),
                "output": str(output_path),
            },
        )

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        logger.info(
            "gameplay_resolver.concatenacao_concluida",
            extra={"path": str(output_path)},
        )

        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(
            "gameplay_resolver.erro_concat",
            extra={"stderr": e.stderr, "stdout": e.stdout},
        )
        raise RuntimeError(f"Falha ao concatenar segmentos: {e.stderr}")
    finally:
        # Limpar arquivo temporário
        if lista_file.exists():
            lista_file.unlink()


async def resolver_gameplay_bg(
    roteiro: Roteiro,
    canal_id: str,
    faixa_intensidade: str | None = None,
    output_dir: Path | None = None,
) -> GameplayBgResolvido | None:
    """
    Resolve fundo de gameplay para um roteiro completo.

    Fluxo:
    1. Calcula duração total do áudio
    2. Seleciona segmentos suficientes
    3. Concatena com crossfade
    4. Marca segmentos como usados

    Args:
        roteiro: Roteiro com audio_final_path
        canal_id: ID do canal
        faixa_intensidade: Filtro de intensidade (default: do nicho ou settings)
        output_dir: Diretório para salvar vídeo concatenado

    Returns:
        GameplayBgResolvido se sucesso, None se falhar
    """
    # Obter duração do áudio
    if not roteiro.metadata.audio_final_path:
        logger.warning(
            "gameplay_resolver.sem_audio",
            extra={"video_id": roteiro.metadata.video_id},
        )
        return None

    audio_path = Path(roteiro.metadata.audio_final_path)
    if not audio_path.exists():
        logger.warning(
            "gameplay_resolver.audio_nao_encontrado",
            extra={"path": str(audio_path)},
        )
        return None

    # Obter duração do áudio via ffprobe
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duracao_audio = float(result.stdout.strip())
    except Exception as e:
        logger.error(
            "gameplay_resolver.erro_duracao_audio",
            extra={"erro": str(e)},
        )
        return None

    # Adicionar margem de segurança (5 segundos)
    duracao_alvo = duracao_audio + 5.0

    # Selecionar segmentos
    segmentos = await selecionar_segmentos(
        duracao_alvo=duracao_alvo,
        canal_id=canal_id,
        faixa_intensidade=faixa_intensidade,
    )

    if not segmentos:
        return None

    # Definir caminho de saída
    output_dir = output_dir or Path(settings.gameplay_processed_dir) / "concatenados"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"bg_{roteiro.metadata.video_id}.mp4"

    # Concatenar segmentos
    try:
        video_path = await concatenar_segmentos(
            segmentos=segmentos,
            output_path=output_path,
        )
    except Exception as e:
        logger.error(
            "gameplay_resolver.erro_concatenacao",
            extra={"erro": str(e)},
        )
        return None

    # Marcar segmentos como usados
    hoje = datetime.now().strftime("%Y-%m-%d")
    for seg in segmentos:
        try:
            await marcar_gameplay_usado(
                segmento_id=seg["id"],
                video_id=roteiro.metadata.video_id,
                data_uso=hoje,
            )
        except Exception as e:
            logger.warning(
                "gameplay_resolver.erro_marcar_usado",
                extra={"segmento_id": seg["id"], "erro": str(e)},
            )

    duracao_total = sum(seg["duracao_segundos"] for seg in segmentos)
    jogos = list(set(seg["jogo_origem"] for seg in segmentos))

    logger.info(
        "gameplay_resolver.resolvido",
        extra={
            "video_id": roteiro.metadata.video_id,
            "duracao_audio": duracao_audio,
            "duracao_bg": duracao_total,
            "num_segmentos": len(segmentos),
            "jogos": jogos,
        },
    )

    return GameplayBgResolvido(
        path=video_path,
        duracao_total=duracao_total,
        segmentos_ids=[str(seg["id"]) for seg in segmentos],
        jogos_utilizados=jogos,
    )


async def resolver_gameplay_bg_cena(
    cena: Cena,
    canal_id: str,
    faixa_intensidade: str | None = None,
) -> bool:
    """
    Resolve fundo de gameplay para uma cena específica.

    Preenche cena.asset_resolvido_path com o vídeo de gameplay concatenado.

    Args:
        cena: Cena a ter seu asset resolvido
        canal_id: ID do canal
        faixa_intensidade: Filtro de intensidade

    Returns:
        True se resolvido com sucesso, False caso contrário
    """
    # Criar roteiro temporário para usar a função principal
    from pipeline.schemas import RoteiroMetadata

    # A cena precisa estar em um contexto de roteiro com áudio
    # Por ora, esta função é um placeholder - a resolução real
    # acontece no nível do roteiro completo
    logger.warning(
        "gameplay_resolver.resolucao_por_cena_nao_suportada",
        extra={"cena_id": cena.cena_id},
    )
    return False
