"""
FASE 5 — Ponte Python -> Remotion CLI.

Este módulo serializa o roteiro para JSON e invoca o Remotion CLI
via subprocess para renderizar o vídeo final.
"""
import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from pipeline.config import settings
from pipeline.schemas import Roteiro

logger = logging.getLogger("remotion_bridge")


def _copiar_assets_para_public(roteiro: Roteiro) -> dict[str, str]:
    """
    Copia assets do roteiro para remotion/public/ para uso via staticFile().

    O Remotion só consegue carregar arquivos locais via staticFile() se
    estiverem em public/. Esta função copia áudio, imagens e vídeos do
    roteiro para esse diretório e retorna um mapeamento dos paths originais
    para os nomes dos arquivos em public/.

    Args:
        roteiro: Roteiro com assets_resolvido_path e audio_final_path

    Returns:
        Dict mapeando path_original -> nome_arquivo_public
    """
    public_dir = settings.remotion_dir / "public"
    public_dir.mkdir(parents=True, exist_ok=True)

    mapeamento: dict[str, str] = {}

    # Copiar áudio final se existir
    if roteiro.metadata.audio_final_path:
        audio_path = Path(roteiro.metadata.audio_final_path)
        if audio_path.exists():
            nome_public = f"audio_{roteiro.metadata.video_id}.wav"
            destino = public_dir / nome_public
            shutil.copy2(audio_path, destino)
            mapeamento[str(audio_path)] = nome_public
            logger.debug(
                "remotion.asset_copiado",
                extra={"original": str(audio_path), "public": nome_public}
            )

    # Copiar assets de cada cena
    for cena in roteiro.cenas:
        if cena.asset_resolvido_path:
            asset_path = Path(cena.asset_resolvido_path)
            if asset_path.exists():
                # Usar video_id + cena_id para garantir unicidade
                ext = asset_path.suffix
                nome_public = f"asset_{roteiro.metadata.video_id}_cena_{cena.cena_id}{ext}"
                destino = public_dir / nome_public
                shutil.copy2(asset_path, destino)
                mapeamento[str(asset_path)] = nome_public
                logger.debug(
                    "remotion.asset_copiado",
                    extra={"original": str(asset_path), "public": nome_public}
                )

    logger.info(
        "remotion.assets_preparados",
        extra={"video_id": roteiro.metadata.video_id, "total_assets": len(mapeamento)}
    )

    return mapeamento


async def renderizar_video(roteiro: Roteiro, output_path: Path | None = None) -> Path:
    """
    Renderiza o vídeo final usando Remotion CLI.

    Args:
        roteiro: Objeto Roteiro validado com todos os dados preenchidos
        output_path: Caminho opcional para o vídeo de saída.
                    Se não fornecido, usa data/output_final/{video_id}.mp4

    Returns:
        Path para o arquivo de vídeo gerado

    Raises:
        RuntimeError: Se a renderização falhar
    """
    # Determinar caminho de saída
    if output_path is None:
        output_dir = settings.data_dir / "output_final"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{roteiro.metadata.video_id}.mp4"

    # Copiar assets para remotion/public/ e obter mapeamento
    mapeamento_assets = _copiar_assets_para_public(roteiro)

    # Criar cópia do roteiro com paths atualizados para staticFile()
    roteiro_dict = roteiro.model_dump()

    # Atualizar paths no roteiro para usar nomes em public/
    if roteiro_dict["metadata"]["audio_final_path"]:
        path_original = roteiro_dict["metadata"]["audio_final_path"]
        if path_original in mapeamento_assets:
            roteiro_dict["metadata"]["audio_final_path"] = mapeamento_assets[path_original]

    for cena in roteiro_dict["cenas"]:
        if cena["asset_resolvido_path"]:
            path_original = cena["asset_resolvido_path"]
            if path_original in mapeamento_assets:
                cena["asset_resolvido_path"] = mapeamento_assets[path_original]

    # Serializar roteiro atualizado para JSON
    roteiro_json = json.dumps(roteiro_dict)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        prefix=f"roteiro_{roteiro.metadata.video_id}_"
    ) as temp_file:
        temp_file.write(roteiro_json)
        roteiro_temp_path = Path(temp_file.name)

    logger.info(
        "remotion.serializando_roteiro",
        extra={
            "video_id": roteiro.metadata.video_id,
            "temp_path": str(roteiro_temp_path),
        }
    )

    try:
        # Construir comando do Remotion CLI
        remotion_dir = settings.remotion_dir

        # Comando: npx remotion render VideoPrincipal <output> --props=<roteiro_json>
        comando = [
            "npx",
            "remotion",
            "render",
            "VideoPrincipal",
            str(output_path.absolute()),
            f"--props={roteiro_temp_path.absolute()}",
            "--concurrency=1",
        ]

        logger.info(
            "remotion.iniciando_render",
            extra={
                "video_id": roteiro.metadata.video_id,
                "output": str(output_path),
                "comando": " ".join(comando),
            }
        )

        # Executar em thread separada (subprocess síncrono)
        resultado = await asyncio.to_thread(
            _executar_comando_remotion,
            comando,
            remotion_dir,
        )

        if resultado["returncode"] != 0:
            logger.error(
                "remotion.erro_render",
                extra={
                    "video_id": roteiro.metadata.video_id,
                    "stderr": resultado["stderr"],
                    "stdout": resultado["stdout"],
                }
            )
            raise RuntimeError(
                f"Falha ao renderizar vídeo: {resultado['stderr'] or resultado['stdout']}"
            )

        logger.info(
            "remotion.render_concluido",
            extra={
                "video_id": roteiro.metadata.video_id,
                "output": str(output_path),
            }
        )

        return output_path

    finally:
        # Limpar arquivo temporário
        if roteiro_temp_path.exists():
            roteiro_temp_path.unlink()
            logger.debug("remotion.temp_removido", extra={"path": str(roteiro_temp_path)})


def _executar_comando_remotion(comando: list[str], cwd: Path) -> dict[str, Any]:
    """
    Executa o comando do Remotion CLI de forma síncrona.

    Args:
        comando: Lista de argumentos do comando
        cwd: Diretório de trabalho (onde está o package.json do Remotion)

    Returns:
        Dict com returncode, stdout e stderr
    """
    import subprocess

    try:
        resultado = subprocess.run(
            comando,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutos de timeout
        )

        return {
            "returncode": resultado.returncode,
            "stdout": resultado.stdout,
            "stderr": resultado.stderr,
        }

    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "Timeout: renderização excedeu 10 minutos",
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
        }

async def renderizar_video_short(
    roteiro: Roteiro,
    output_path: Path | None = None,
) -> Path:
    """
    Renderiza vídeo no formato Short (9:16 vertical).
    Subfase 8.5 — Suporte a Shorts.

    Args:
        roteiro: Roteiro de short com áudio e assets resolvidos
        output_path: Caminho opcional para o vídeo de saída

    Returns:
        Caminho do arquivo de vídeo gerado

    Raises:
        RuntimeError: Se a renderização falhar
    """
    logger.info(
        "renderizar_video_short.iniciando",
        extra={
            "video_id": roteiro.metadata.video_id,
            "formato": roteiro.metadata.formato,
            "video_origem": roteiro.metadata.video_origem_id,
        },
    )

    if roteiro.metadata.formato != "short":
        logger.warning(
            "renderizar_video_short.formato_incorreto",
            extra={"formato": roteiro.metadata.formato},
        )

    # Determinar caminho de saída
    if output_path is None:
        output_dir = settings.data_dir / "output_final"
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{roteiro.metadata.video_id}_short.mp4"
        output_path = output_dir / filename

    # Serializar roteiro para JSON
    roteiro_json = roteiro.model_dump_json(indent=2)

    # Criar arquivo temporário para o props
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        dir=settings.remotion_dir,
    ) as roteiro_temp_file:
        roteiro_temp_file.write(roteiro_json)
        roteiro_temp_path = Path(roteiro_temp_file.name)

    try:
        # Construir comando Remotion para composição VideoShort
        comando = [
            "npx",
            "remotion",
            "render",
            "VideoShort",
            str(output_path),
            f"--props={roteiro_temp_path.name}",
            f"--concurrency={settings.remotion_concurrency}",
            "--codec=h264",
            "--quality=100",
        ]

        # Executar comando de forma assíncrona
        loop = asyncio.get_event_loop()
        resultado = await loop.run_in_executor(
            None,
            _executar_comando_remotion,
            comando,
            Path(settings.remotion_dir),
        )

        if resultado["returncode"] != 0:
            raise RuntimeError(
                f"Renderização do short falhou: {resultado['stderr']}"
            )

        logger.info(
            "renderizar_video_short.sucesso",
            extra={
                "video_id": roteiro.metadata.video_id,
                "output": str(output_path),
            },
        )

        return output_path

    finally:
        # Limpar arquivo temporário
        if roteiro_temp_path.exists():
            roteiro_temp_path.unlink()
            logger.debug("remotion.temp_removido", extra={"path": str(roteiro_temp_path)})
