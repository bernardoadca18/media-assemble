"""
Configurações globais do projeto, carregadas via .env.
Fonte única da verdade para paths, credenciais e parâmetros do pipeline.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Banco de dados ---
    database_url: str = "postgresql+asyncpg://usuario:senha@localhost:5432/faceless_pipeline"

    # --- LiteLLM / Modelos ---
    litellm_master_key: str | None = None
    litellm_base_url: str | None = None
    local_model_name: str = "ollama/qwen2.5:7b"
    local_model_base_url: str = "http://localhost:11434"
    cloud_model_ideacao: str = "openai/gemini-3.6-flash"
    cloud_model_roteiro: str = "openai/gemini-3.1-pro"

    # --- Áudio / GPU ---
    whisper_model_size: str = "medium"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    f5_tts_ref_audio: str = "data/voz_referencia/minha_voz.wav"
    f5_tts_ref_text: str = ""

    # --- Pipeline ---
    nichos_ativos: str = "cultura_pop"
    wer_limite_aprovacao: float = 0.05
    max_tentativas_tts: int = 3

    # --- Assets externos ---
    pexels_api_key: str | None = None

    @property
    def nichos_lista(self) -> list[str]:
        return [n.strip() for n in self.nichos_ativos.split(",") if n.strip()]

    # --- Paths derivados (raiz do projeto) ---
    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def remotion_dir(self) -> Path:
        return self.base_dir / "remotion"


settings = Settings()
