"""
FASE 5 — Ponte Python -> Remotion CLI.

Este módulo serializa o roteiro para JSON e invoca o Remotion CLI
via subprocess para renderizar o vídeo final.
"""
import asyncio
import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from pipeline.config import settings
from pipeline.schemas import Roteiro

logger = logging.getLogger("remotion_bridge")


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

    # Serializar roteiro para JSON temporário
    roteiro_json = roteiro.model_dump_json()
    roteiro_dict = json.loads(roteiro_json)

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