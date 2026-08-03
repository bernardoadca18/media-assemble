"""
Entry point do projeto.

Uso manual (uma execução):
    python main.py --run-once

Uso agendado (produção):
    python main.py
"""
import argparse
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from pipeline.config import settings
from pipeline.orchestrator import rodar_pipeline_completo
from utils.logger import configurar_logging


async def _rodar_uma_vez():
    for nicho in settings.nichos_lista:
        await rodar_pipeline_completo(nicho)


def main():
    configurar_logging()

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-once", action="store_true", help="Executa uma vez e sai (não agenda).")
    args = parser.parse_args()

    if args.run_once:
        asyncio.run(_rodar_uma_vez())
        return

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
