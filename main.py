"""
Entry point do projeto.

Uso manual (uma execução):
    python main.py --run-once

Uso agendado (produção):
    python main.py

Retomar execuções falhas:
    python main.py --listar-falhas
    python main.py --retomar VIDEO_ID

Revisão manual:
    python main.py --listar-pendentes
    python main.py --revisar VIDEO_ID --aprovar
    python main.py --revisar VIDEO_ID --rejeitar
"""
import argparse
import asyncio
import json
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from pipeline.config import settings
from pipeline.orchestrator import retomar_execucao_falha, rodar_pipeline_completo
from utils.logger import configurar_logging


async def _rodar_uma_vez():
    for nicho in settings.nichos_lista:
        await rodar_pipeline_completo(nicho)


async def _listar_falhas():
    """Lista execuções falhas que podem ser retomadas."""
    from db.models import listar_execucoes_falhas

    execucoes = await listar_execucoes_falhas()

    if not execucoes:
        print("Nenhuma execução falha encontrada.")
        return

    print(f"\n{len(execucoes)} execução(ões) falha(s) encontrada(s):\n")
    print(f"{'VIDEO_ID':<40} {'NICHO':<20} {'ETAPA':<20} {'CRIADO_EM'}")
    print("-" * 100)

    for exec_ in execucoes:
        print(f"{exec_['video_id']:<40} {exec_['nicho']:<20} {exec_['etapa_atual']:<20} {exec_['criado_em'] or 'N/A'}")


async def _retomar(video_id: str):
    """Retoma uma execução falha específica."""
    print(f"\nRetomando execução {video_id}...")

    resultado = await retomar_execucao_falha(video_id)

    if resultado["sucesso"]:
        print(f"\n✅ Execução retomada com sucesso!")
        print(f"   Video ID: {resultado['video_id']}")
    else:
        print(f"\n❌ Falha ao retomar execução.")
        print(f"   Etapa: {resultado.get('etapa', 'desconhecida')}")
        print(f"   Erro: {resultado.get('erro', 'erro desconhecido')}")


async def _listar_pendentes():
    """Lista roteiros pendentes de revisão."""
    from db.models import listar_roteiros_pendentes_revisao

    roteiros = await listar_roteiros_pendentes_revisao()

    if not roteiros:
        print("Nenhum roteiro pendente de revisão.")
        return

    print(f"\n{len(roteiros)} roteiro(s) pendente(s) de revisão:\n")
    print(f"{'VIDEO_ID':<15} {'NICHO':<20} {'TÍTULO':<60} {'CRIADO_EM'}")
    print("-" * 120)

    for r in roteiros:
        titulo = r['titulo_sugerido'][:57] + "..." if len(r['titulo_sugerido']) > 60 else r['titulo_sugerido']
        print(f"{r['video_id']:<15} {r['nicho']:<20} {titulo:<60} {r['criado_em'] or 'N/A'}")


async def _revisar(video_id: str, aprovar: bool):
    """Aprova ou rejeita um roteiro."""
    from db.models import atualizar_status_revisao

    status = "aprovado" if aprovar else "rejeitado"
    print(f"\n{'Aprovando' if aprovar else 'Rejeitando'} roteiro {video_id}...")

    sucesso = await atualizar_status_revisao(video_id, status)

    if sucesso:
        print(f"\n✅ Roteiro {status} com sucesso!")
    else:
        print(f"\n❌ Roteiro não encontrado.")


async def _relatorio_custos(periodo: str | None):
    """Exibe relatório de custos de LLM."""
    from utils.cost_tracker import relatorio_custos

    relatorio = relatorio_custos(periodo)

    print(f"\n{'='*60}")
    print(f"RELATÓRIO DE CUSTOS - {relatorio['periodo']}")
    print(f"{'='*60}")
    print(f"\nTotal de chamadas: {relatorio['total_chamadas']}")
    print(f"Total de tokens: {relatorio['total_tokens']:,}")
    print(f"Custo total: ${relatorio['total_custo_usd']:.4f} USD")

    if relatorio['por_operacao']:
        print(f"\n{'─'*60}")
        print("POR OPERAÇÃO:")
        print(f"{'Operação':<25} {'Chamadas':>10} {'Tokens':>12} {'Custo':>12}")
        print(f"{'─'*60}")
        for op, dados in sorted(relatorio['por_operacao'].items(), key=lambda x: x[1]['custo'], reverse=True):
            print(f"{op:<25} {dados['chamadas']:>10} {dados['tokens']:>12,} ${dados['custo']:>10.4f}")

    if relatorio['por_modelo']:
        print(f"\n{'─'*60}")
        print("POR MODELO:")
        print(f"{'Modelo':<25} {'Chamadas':>10} {'Tokens':>12} {'Custo':>12}")
        print(f"{'─'*60}")
        for mod, dados in sorted(relatorio['por_modelo'].items(), key=lambda x: x[1]['custo'], reverse=True):
            modelo_display = mod[:22] + "..." if len(mod) > 25 else mod
            print(f"{modelo_display:<25} {dados['chamadas']:>10} {dados['tokens']:>12,} ${dados['custo']:>10.4f}")

    print(f"\n{'='*60}\n")


async def _gerar_metadata(video_id: str):
    """Gera metadata de publicação para um vídeo."""
    from db.models import carregar_roteiro, salvar_roteiro
    from services.metadata_generator import gerar_metadata_publicacao, formatar_metadata_cli

    print(f"\nBuscando roteiro {video_id}...")
    roteiro = await carregar_roteiro(video_id)

    if not roteiro:
        print(f"\n❌ Roteiro não encontrado.")
        return

    if not roteiro.metadata.video_final_path:
        print(f"\n⚠️  Vídeo ainda não foi renderizado. Execute o pipeline completo primeiro.")
        return

    print(f"Gerando metadata de publicação...")
    try:
        metadata = await gerar_metadata_publicacao(roteiro)

        # Atualizar roteiro com metadata
        from pipeline.schemas import MetadataPublicacao
        roteiro.metadata.metadata_publicacao = MetadataPublicacao(**metadata)
        await salvar_roteiro(roteiro)

        # Exibir resultado
        print(formatar_metadata_cli(metadata))
        print(f"\n✅ Metadata salva no banco de dados.")

    except Exception as e:
        print(f"\n❌ Erro ao gerar metadata: {e}")


async def _sugerir_ideia(nicho: str, titulo: str, descricao: str | None, prioridade: str):
    """Salva uma ideia manual sugerida pelo usuário."""
    from db.models import salvar_ideia_manual

    print(f"\nSalvando ideia para nicho '{nicho}'...")
    try:
        ideia_id = await salvar_ideia_manual(
            nicho=nicho,
            titulo_sugerido=titulo,
            descricao_breve=descricao,
            prioridade=prioridade,
        )
        print(f"\n✅ Ideia salva com sucesso!")
        print(f"   ID: {ideia_id}")
        print(f"   Nicho: {nicho}")
        print(f"   Título: {titulo}")
        print(f"   Prioridade: {prioridade}")
        if prioridade == "alta":
            print(f"\n💡 Ideia com alta prioridade será processada no próximo lote do nicho.")
    except Exception as e:
        print(f"\n❌ Erro ao salvar ideia: {e}")


async def _listar_ideias_manuais(nicho: str | None):
    """Lista ideias manuais cadastradas."""
    from db.models import listar_ideias_manuais

    ideias = await listar_ideias_manuais(nicho=nicho)

    if not ideias:
        print("Nenhuma ideia manual encontrada.")
        return

    print(f"\n{len(ideias)} ideia(s) manual(is):\n")
    print(f"{'ID':<6} {'NICHO':<15} {'TÍTULO':<50} {'PRIORIDADE':<10} {'STATUS':<12}")
    print("-" * 100)

    for ideia in ideias:
        titulo = ideia['titulo_sugerido'][:47] + "..." if len(ideia['titulo_sugerido']) > 50 else ideia['titulo_sugerido']
        print(f"{ideia['id']:<6} {ideia['nicho']:<15} {titulo:<50} {ideia['prioridade']:<10} {ideia['status']:<12}")


async def _descartar_ideia(ideia_id: int):
    """Descarta uma ideia manual."""
    from db.models import marcar_ideia_manual_descartada

    print(f"\nDescartando ideia {ideia_id}...")
    sucesso = await marcar_ideia_manual_descartada(ideia_id)

    if sucesso:
        print(f"\n✅ Ideia descartada com sucesso!")
    else:
        print(f"\n❌ Ideia não encontrada.")


def main():
    configurar_logging()

    parser = argparse.ArgumentParser(description="Pipeline de vídeos faceless")
    parser.add_argument("--run-once", action="store_true", help="Executa uma vez e sai (não agenda).")
    parser.add_argument("--listar-falhas", action="store_true", help="Lista execuções falhas que podem ser retomadas.")
    parser.add_argument("--retomar", type=str, metavar="VIDEO_ID", help="Retoma uma execução falha específica.")
    parser.add_argument("--listar-pendentes", action="store_true", help="Lista roteiros pendentes de revisão.")
    parser.add_argument("--revisar", type=str, metavar="VIDEO_ID", help="Revisa um roteiro (use com --aprovar ou --rejeitar).")
    parser.add_argument("--aprovar", action="store_true", help="Aprova o roteiro (usado com --revisar).")
    parser.add_argument("--rejeitar", action="store_true", help="Rejeita o roteiro (usado com --revisar).")
    parser.add_argument("--custos", action="store_true", help="Exibe relatório de custos do mês atual.")
    parser.add_argument("--metadata", type=str, metavar="VIDEO_ID", help="Gera metadata de publicação para o vídeo.")
    # Subfase 8.8 — Painel de controle editorial
    parser.add_argument("--sugerir-ideia", action="store_true", help="Sugere uma ideia manual (use com --nicho, --titulo, --prioridade).")
    parser.add_argument("--nicho", type=str, help="Nicho para a ideia manual (usado com --sugerir-ideia).")
    parser.add_argument("--titulo", type=str, help="Título da ideia manual (usado com --sugerir-ideia).")
    parser.add_argument("--descricao", type=str, help="Descrição da ideia manual (opcional, usado com --sugerir-ideia).")
    parser.add_argument("--prioridade", type=str, choices=["alta", "normal"], default="normal", help="Prioridade da ideia (usado com --sugerir-ideia).")
    parser.add_argument("--listar-ideias-manuais", action="store_true", help="Lista ideias manuais cadastradas.")
    parser.add_argument("--descartar-ideia", type=int, metavar="ID", help="Descarta uma ideia manual pelo ID.")
    args = parser.parse_args()

    if args.run_once:
        asyncio.run(_rodar_uma_vez())
        return

    if args.listar_falhas:
        asyncio.run(_listar_falhas())
        return

    if args.retomar:
        asyncio.run(_retomar(args.retomar))
        return

    if args.listar_pendentes:
        asyncio.run(_listar_pendentes())
        return

    if args.revisar:
        if not args.aprovar and not args.rejeitar:
            print("Erro: Especifique --aprovar ou --rejeitar ao usar --revisar.")
            return
        if args.aprovar and args.rejeitar:
            print("Erro: Especifique apenas --aprovar ou --rejeitar, não ambos.")
            return
        asyncio.run(_revisar(args.revisar, args.aprovar))
        return

    if args.custos:
        asyncio.run(_relatorio_custos(None))
        return

    if args.metadata:
        asyncio.run(_gerar_metadata(args.metadata))
        return

    if args.sugerir_ideia:
        if not args.nicho or not args.titulo:
            print("Erro: --sugerir-ideia requer --nicho e --titulo.")
            return
        asyncio.run(_sugerir_ideia(args.nicho, args.titulo, args.descricao, args.prioridade))
        return

    if args.listar_ideias_manuais:
        asyncio.run(_listar_ideias_manuais(args.nicho))
        return

    if args.descartar_ideia:
        asyncio.run(_descartar_ideia(args.descartar_ideia))
        return

    # Modo scheduler (padrão)
    scheduler = AsyncIOScheduler()
    for nicho in settings.nichos_lista:
        scheduler.add_job(rodar_pipeline_completo, "cron", hour=6, args=[nicho])

    scheduler.start()
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
