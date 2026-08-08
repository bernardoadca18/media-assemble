"""
Rastreamento de custos de LLM e APIs.

Registra uso de tokens e custos estimados por operação do pipeline.
Os dados são salvos em data/custos/ para análise posterior.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("utils.cost_tracker")

# Diretório para salvar logs de custo
COST_DIR = Path("data/custos")
COST_DIR.mkdir(parents=True, exist_ok=True)

# Custos por 1M tokens (aproximados, ajustar conforme provedor)
CUSTOS_POR_1M_TOKENS = {
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},

    # Anthropic
    "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},

    # Google Gemini
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},

    # Ollama (local - custo zero)
    "ollama/*": {"input": 0.00, "output": 0.00},
}

# Alias para modelos
ALIAS_MODELO = {
    "openai/gemini-3.6-flash": "gemini-1.5-flash",
    "openai/gemini-3.1-pro": "gemini-1.5-pro",
    "gemini/gemini-1.5-flash": "gemini-1.5-flash",
    "gemini/gemini-1.5-pro": "gemini-1.5-pro",
}


def _normalizar_modelo(modelo: str) -> str:
    """Normaliza nome do modelo para buscar na tabela de custos."""
    # Verifica alias primeiro
    if modelo in ALIAS_MODELO:
        return ALIAS_MODELO[modelo]

    # Remove prefixos comuns
    for prefixo in ["openai/", "anthropic/", "google/"]:
        if modelo.startswith(prefixo):
            return modelo[len(prefixo):]

    # Ollama é gratuito
    if modelo.startswith("ollama/"):
        return "ollama/*"

    return modelo


def calcular_custo(modelo: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calcula o custo estimado de uma chamada LLM.

    Args:
        modelo: Nome do modelo (ex: "gpt-4o", "gemini-1.5-flash")
        input_tokens: Número de tokens de entrada
        output_tokens: Número de tokens de saída

    Returns:
        Custo estimado em USD
    """
    modelo_normalizado = _normalizar_modelo(modelo)

    if modelo_normalizado not in CUSTOS_POR_1M_TOKENS:
        logger.warning(
            "cost_tracker.modelo_desconhecido",
            extra={"modelo": modelo, "modelo_normalizado": modelo_normalizado}
        )
        return 0.0

    custos = CUSTOS_POR_1M_TOKENS[modelo_normalizado]
    custo_input = (input_tokens / 1_000_000) * custos["input"]
    custo_output = (output_tokens / 1_000_000) * custos["output"]

    return custo_input + custo_output


def registrar_chamada(
    operacao: str,
    modelo: str,
    input_tokens: int,
    output_tokens: int,
    nicho: str | None = None,
    video_id: str | None = None,
    metadados: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Registra uma chamada de LLM para análise de custos.

    Args:
        operacao: Nome da operação (ex: "ideacao", "roteirizacao")
        modelo: Nome do modelo usado
        input_tokens: Tokens de entrada
        output_tokens: Tokens de saída
        nicho: Nicho do vídeo (opcional)
        video_id: ID do vídeo (opcional)
        metadados: Metadados adicionais (opcional)

    Returns:
        Dict com informações da chamada e custo
    """
    custo = calcular_custo(modelo, input_tokens, output_tokens)

    registro = {
        "timestamp": datetime.now().isoformat(),
        "operacao": operacao,
        "modelo": modelo,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "custo_usd": round(custo, 6),
        "nicho": nicho,
        "video_id": video_id,
        "metadados": metadados or {},
    }

    # Salva em arquivo JSONL (append)
    arquivo = COST_DIR / f"custos_{datetime.now().strftime('%Y-%m')}.jsonl"
    with open(arquivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    logger.info(
        "cost_tracker.chamada_registrada",
        extra={
            "operacao": operacao,
            "modelo": modelo,
            "total_tokens": input_tokens + output_tokens,
            "custo_usd": custo,
        }
    )

    return registro


def relatorio_custos(periodo_mes: str | None = None) -> dict[str, Any]:
    """
    Gera relatório de custos por período.

    Args:
        periodo_mes: Mês no formato YYYY-MM (default: mês atual)

    Returns:
        Dict com resumo de custos por operação, modelo, etc.
    """
    if not periodo_mes:
        periodo_mes = datetime.now().strftime("%Y-%m")

    arquivo = COST_DIR / f"custos_{periodo_mes}.jsonl"

    if not arquivo.exists():
        return {
            "periodo": periodo_mes,
            "total_chamadas": 0,
            "total_tokens": 0,
            "total_custo_usd": 0.0,
            "por_operacao": {},
            "por_modelo": {},
        }

    chamadas = []
    with open(arquivo, "r", encoding="utf-8") as f:
        for linha in f:
            chamadas.append(json.loads(linha))

    # Agregações
    total_tokens = sum(c["total_tokens"] for c in chamadas)
    total_custo = sum(c["custo_usd"] for c in chamadas)

    por_operacao: dict[str, dict[str, float]] = {}
    por_modelo: dict[str, dict[str, float]] = {}

    for c in chamadas:
        op = c["operacao"]
        mod = c["modelo"]

        if op not in por_operacao:
            por_operacao[op] = {"chamadas": 0, "tokens": 0, "custo": 0.0}
        por_operacao[op]["chamadas"] += 1
        por_operacao[op]["tokens"] += c["total_tokens"]
        por_operacao[op]["custo"] += c["custo_usd"]

        if mod not in por_modelo:
            por_modelo[mod] = {"chamadas": 0, "tokens": 0, "custo": 0.0}
        por_modelo[mod]["chamadas"] += 1
        por_modelo[mod]["tokens"] += c["total_tokens"]
        por_modelo[mod]["custo"] += c["custo_usd"]

    return {
        "periodo": periodo_mes,
        "total_chamadas": len(chamadas),
        "total_tokens": total_tokens,
        "total_custo_usd": round(total_custo, 4),
        "por_operacao": por_operacao,
        "por_modelo": por_modelo,
    }
