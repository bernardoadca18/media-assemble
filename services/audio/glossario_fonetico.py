"""
Glossário fonético para correção de pronúncia no Kokoro TTS.

Mapeia termos problemáticos (nomes próprios, termos técnicos em inglês, siglas)
para suas versões com pronúncia correta em português.

Este glossário é aplicado ANTES de enviar o texto ao Kokoro, garantindo que
a pronúncia esteja correta sem alterar o texto original usado para legendas
e validação WER.
"""
from typing import Dict


# Glossário principal: termo_original -> versão_fonetica
GLOSSARIO_FONETICO: Dict[str, str] = {
    # Nomes próprios de animes/personagens
    "Naruto": "Naruto",
    "Sasuke": "Sasukê",
    "Uchiha": "Utchiha",
    "Kakashi": "Kakashí",
    "Itachi": "Itachi",
    "Obito": "Obito",
    "Madara": "Madara",
    "Sakura": "Sakúra",
    "Hinata": "Hinata",
    "Minato": "Minato",
    "Jiraiya": "Jiraía",
    "Tsunade": "Tsunáde",
    "Orochimaru": "Orotchimaru",
    "Boruto": "Boruto",
    "Sarada": "Saráda",

    # Termos técnicos em inglês comuns
    "software": "softuér",
    "hardware": "harduér",
    "gameplay": "guémiplei",
    "gamer": "guéimer",
    "gaming": "guéiming",
    "streamer": "strímer",
    "streaming": "stríming",
    "click": "clique",
    "clicks": "cliques",
    "download": "daunloud",
    "upload": "aploude",
    "online": "onláin",
    "offline": "offláin",
    "website": "uêbsáite",
    "link": "linque",
    "links": "linques",
    "file": "fáile",
    "files": "fáiles",
    "server": "sérver",
    "servers": "sérvers",
    "bug": "bágue",
    "bugs": "bágues",
    "feature": "fíture",
    "features": "fítures",
    "update": "apdéite",
    "updates": "apdéites",

    # Termos de tecnologia/games
    "FPS": "éfe pé esse",
    "RPG": "érre pé guê",
    "MMORPG": "êmue môrre pé guê",
    "NPC": "ênê pé cê",
    "PvP": "pê vês pê",
    "PvE": "pê vês ê",
    "DPS": "dê pé esse",
    "XP": "xis pé",
    "HP": "agá pé",
    "MP": "ême pé",
    "CD": "sê dê",
    "DVD": "dê vê dê",
    "PC": "pê cê",
    "GPU": "guê pê u",
    "CPU": "cê pê u",
    "RAM": "rã",
    "SSD": "esse esse dê",
    "HDD": "agá dê dê",
    "USB": "u esse bê",
    "WiFi": "uái fái",

    # Plataformas e marcas
    "YouTube": "Iutube",
    "TikTok": "TikTok",
    "Instagram": "Instagram",
    "Twitter": "Tuíter",
    "Facebook": "Feisbuk",
    "Netflix": "Nétflix",
    "Spotify": "Spótifaí",
    "Discord": "Discórd",
    "Steam": "Stím",
    "PlayStation": "Pléistétion",
    "Xbox": "Eksbox",
    "Nintendo": "Nintêndo",
    "Android": "Andróide",
    "iPhone": "áifon",
    "iPad": "aípéd",

    # Termos de anime/manga
    "manga": "mangá",
    "anime": "anime",
    "otaku": "otaku",
    "cosplay": "cósplei",
    "waifu": "uaífue",
    "husbando": "ázbande",
    "senpai": "senpái",
    "kouhai": "kohái",
    "sensei": "sensêi",
    "shounen": "shóunen",
    "seinen": "sêinen",
    "shoujo": "shôjo",
    "isekai": "isekai",
    "chakra": "tchákra",
    "jutsu": "jutsu",
    "sharingan": "sharingan",
    "byakugan": "biakugan",
    "rasengan": "rasengan",
}


def aplicar_glossario(texto: str) -> str:
    """
    Aplica correções fonéticas ao texto antes de enviar ao Kokoro.

    Mantém case-insensitive matching para maior cobertura.

    Args:
        texto: Texto original

    Returns:
        Texto com termos substituídos por suas versões fonéticas
    """
    resultado = texto

    # Aplica substituições case-insensitive
    for termo_original, versao_fonetica in GLOSSARIO_FONETICO.items():
        # Substitui todas as ocorrências (case-insensitive)
        import re
        pattern = re.compile(re.escape(termo_original), re.IGNORECASE)
        resultado = pattern.sub(versao_fonetica, resultado)

    return resultado


def adicionar_termo(termo_original: str, versao_fonetica: str) -> None:
    """
    Adiciona ou atualiza um termo no glossário.

    Args:
        termo_original: Termo a ser corrigido
        versao_fonetica: Versão com pronúncia correta
    """
    GLOSSARIO_FONETICO[termo_original] = versao_fonetica


def remover_termo(termo_original: str) -> bool:
    """
    Remove um termo do glossário.

    Args:
        termo_original: Termo a ser removido

    Returns:
        True se removido, False se não existia
    """
    if termo_original in GLOSSARIO_FONETICO:
        del GLOSSARIO_FONETICO[termo_original]
        return True
    return False


def listar_termos() -> Dict[str, str]:
    """
    Retorna todos os termos do glossário.

    Returns:
        Dicionário com todos os mapeamentos
    """
    return GLOSSARIO_FONETICO.copy()
