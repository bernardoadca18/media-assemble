"""
Fase 9.4 — Configuração de crop vertical por jogo.

Define offsets de crop Y para cada jogo de gameplay, permitindo ajustar
o enquadramento vertical para Shorts/TikTok. Gameplay videos são 16:9
(horizontal), e precisam ser cropados para 9:16 (vertical).

O offset Y ajusta a posição vertical do crop:
- 0 = centrado (padrão)
- negativo = move crop para cima
- positivo = move crop para baixo
"""
from typing import NamedTuple


class CropConfigJogo(NamedTuple):
    """Configuração de crop para um jogo específico."""
    jogo: str
    crop_offset_y: int  # Offset Y em pixels
    descricao: str = ""


# Configurações de crop por jogo
# Valores baseados em análise visual dos jogos mais comuns
CROP_CONFIG_POR_JOGO: dict[str, CropConfigJogo] = {
    "minecraft": CropConfigJogo(
        jogo="minecraft",
        crop_offset_y=0,
        descricao="Centrado - HUD na parte inferior visível",
    ),
    "fortnite": CropConfigJogo(
        jogo="fortnite",
        crop_offset_y=-50,
        descricao="Levemente acima - evitar HUD muito baixa",
    ),
    "valorant": CropConfigJogo(
        jogo="valorant",
        crop_offset_y=100,
        descricao="Abaixo - foco no centro da tela, minimap no topo",
    ),
    "league_of_legends": CropConfigJogo(
        jogo="league_of_legends",
        crop_offset_y=150,
        descricao="Mais abaixo - evitar minimap no canto inferior",
    ),
    "gta_v": CropConfigJogo(
        jogo="gta_v",
        crop_offset_y=-80,
        descricao="Acima - minimap no canto inferior esquerdo",
    ),
    "call_of_duty": CropConfigJogo(
        jogo="call_of_duty",
        crop_offset_y=0,
        descricao="Centrado - HUD distribuída",
    ),
    "apex_legends": CropConfigJogo(
        jogo="apex_legends",
        crop_offset_y=50,
        descricao="Abaixo - evitar HUD superior",
    ),
    "dota_2": CropConfigJogo(
        jogo="dota_2",
        crop_offset_y=150,
        descricao="Mais abaixo - minimap no canto inferior",
    ),
    "csgo": CropConfigJogo(
        jogo="csgo",
        crop_offset_y=0,
        descricao="Centrado - HUD distribuída",
    ),
    "free_fire": CropConfigJogo(
        jogo="free_fire",
        crop_offset_y=-30,
        descricao="Levemente acima - controles mobile na parte inferior",
    ),
}


def obter_crop_offset_y(jogo: str, default: int = 0) -> int:
    """
    Obtém o offset Y de crop para um jogo.

    Args:
        jogo: Nome do jogo (case insensitive, normalizado)
        default: Valor padrão se jogo não estiver configurado

    Returns:
        Offset Y em pixels
    """
    # Normalizar nome do jogo
    jogo_normalizado = jogo.lower().replace(" ", "_").replace("-", "_")

    if jogo_normalizado in CROP_CONFIG_POR_JOGO:
        return CROP_CONFIG_POR_JOGO[jogo_normalizado].crop_offset_y

    # Tentar match parcial
    for jogo_key, config in CROP_CONFIG_POR_JOGO.items():
        if jogo_normalizado in jogo_key or jogo_key in jogo_normalizado:
            return config.crop_offset_y

    return default


def listar_jogos_configurados() -> list[str]:
    """Retorna lista de jogos com configuração de crop."""
    return list(CROP_CONFIG_POR_JOGO.keys())
