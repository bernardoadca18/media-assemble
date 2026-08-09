#!/usr/bin/env python3
"""
Script para iniciar a API do Faceless Pipeline.

IMPORTANTE: Esta API deve sempre escutar em 127.0.0.1 (localhost).
Não expor em 0.0.0.0 sem implementar autenticação antes.

Uso:
    python scripts/start_api.py
    python scripts/start_api.py --port 8001
    python scripts/start_api.py --reload  # Desenvolvimento
"""
import argparse
import os
import sys
import subprocess
import uvicorn


def run_migrations():
    """Executa as migrações do Alembic antes de iniciar a API."""
    try:
        print("🔄 Executando migrações do banco de dados...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print("✅ Migrações executadas com sucesso")
            if result.stdout.strip():
                print(result.stdout.strip())
        else:
            print(f"⚠️  Aviso: migrações podem já estar aplicadas ou houve erro:")
            print(result.stderr.strip())
    except subprocess.TimeoutExpired:
        print("⚠️  Timeout ao executar migrações")
    except Exception as e:
        print(f"⚠️  Erro ao executar migrações: {e}")


def main():
    parser = argparse.ArgumentParser(description="Iniciar API do Faceless Pipeline")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host para bind (padrão: 127.0.0.1 - NÃO usar 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Porta para escutar (padrão: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Ativar hot reload para desenvolvimento"
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Pular execução de migrações (apenas para desenvolvimento)"
    )
    args = parser.parse_args()

    # Aviso de segurança
    if args.host != "127.0.0.1":
        # Detecta se está rodando em container (sem stdin interativo ou variável de ambiente)
        em_container = (
            not sys.stdin.isatty() or
            os.getenv("RUNNING_IN_DOCKER") == "true" or
            os.path.exists("/.dockerenv")
        )

        print("⚠️  AVISO: Bind em host diferente de 127.0.0.1!")
        print("⚠️  Autenticação não está implementada!")
        print("⚠️  Isso pode expor a API para outros dispositivos na rede.")

        if em_container:
            print("🐳 Detectado ambiente Docker - continuando automaticamente")
        else:
            response = input("Continuar? (s/N): ")
            if response.lower() != "s":
                print("Abortado.")
                return

    # Executa migrações antes de iniciar (exceto se --skip-migrations)
    if not args.skip_migrations:
        run_migrations()

    print(f"🚀 Iniciando API em http://{args.host}:{args.port}")
    print(f"📚 Documentação: http://{args.host}:{args.port}/docs")
    print("⚠️  Autenticação: DESABILITADA (uso local apenas)")
    print("")

    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
