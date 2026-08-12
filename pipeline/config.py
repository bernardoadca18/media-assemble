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
    # LiteLLM Proxy centralizado (todas as requisições passam por ele)
    litellm_master_key: str | None = None
    litellm_base_url: str | None = None
    # Modelos locais (via LiteLLM proxy, não mais conexão direta)
    local_model_name: str = "qwen-local"
    local_model_base_url: str = "http://host.docker.internal:4000"
    # Modelos em nuvem (via LiteLLM proxy)
    cloud_model_ideacao: str = "gemini-3.6-flash"
    cloud_model_roteiro: str = "gemini-3.1-pro"

    # --- Áudio / GPU ---
    whisper_model_size: str = "medium"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    # F5-TTS (LEGADO - mantido para fallback se necessário)
    f5_tts_ref_audio: str = "data/voz_referencia/minha_voz.wav"
    f5_tts_ref_text: str = ""
    # Novo pipeline de voz (Kokoro + Seed-VC)
    voice_pipeline_url: str = "http://localhost:9000"
    voice_pipeline_run_name_default: str = "minha_voz_v1"
    voice_pipeline_timeout: int = 300  # 5 minutos por cena
    voice_pipeline_max_retries: int = 3  # Para erro 409 (GPU ocupada)
    voice_pipeline_retry_delay: float = 2.0  # Segundos entre retries

    # --- Pipeline ---
    nichos_ativos: str = "cultura_pop"
    wer_limite_aprovacao: float = 0.15  # Ajustado de 0.05 para 0.15 (mais realista para TTS)
    max_tentativas_tts: int = 3

    # --- Assets externos ---
    pexels_api_key: str | None = None

    # --- Gameplay ingestion (Fase 9.1) ---
    gameplay_raw_dir: str = "data/gameplay_raw"
    gameplay_processed_dir: str = "data/gameplay_processed"
    gameplay_segment_duration_sec: int = 30
    gameplay_min_motion_score: float = 5.0

    # --- Gameplay resolver (Fase 9.2) ---
    gameplay_janela_reuso_dias: int = 30
    gameplay_crossfade_duration_sec: float = 0.5

    # --- Timbre variation (Fase 9.3) ---
    timbre_pitch_shift_min: float = -2.0
    timbre_pitch_shift_max: float = 2.0
    timbre_velocidade_min: float = 0.95
    timbre_velocidade_max: float = 1.05

    # --- Gameplay crop config (Fase 9.4) ---
    # Default crop offset Y for gameplay videos in Shorts (0 = centered)
    gameplay_crop_offset_y_default: int = 0

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
