"""
应用配置模块
使用 pydantic-settings 从 .env 文件读取配置，类型安全
"""

from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    全局配置类，所有配置项均从环境变量 / .env 文件读取。
    不硬编码任何路径或密钥。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 服务地址 ──────────────────────────────────────────────
    host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_port: int = 5173

    # ── 数据库 ────────────────────────────────────────────────
    database_url: str = "postgresql://user:password@localhost:5432/voicechat"

    # ── Redis ─────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── JWT 认证 ──────────────────────────────────────────────
    jwt_secret_key: str = "change-this-to-a-random-string"
    jwt_expire_days: int = 7

    # ── LLM（OpenAI 兼容）────────────────────────────────────
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    # ── STT（faster-whisper）─────────────────────────────────
    whisper_model_size: str = "medium"
    whisper_device: str = "cuda"

    # ── TTS（GPT-SoVITS）─────────────────────────────────────
    gptsovits_dir: str = "./GPT-SoVITS"
    voice_models_dir: str = "./storage/voice_models"
    pretrained_models_dir: str = "./storage/pretrained_models/GPT-SoVITS"
    storage_dir: str = "./storage"

    @property
    def voice_models_path(self) -> Path:
        """返回音色模型目录的 Path 对象。"""
        return Path(self.voice_models_dir)

    @property
    def pretrained_models_path(self) -> Path:
        """返回预训练模型目录的 Path 对象。"""
        return Path(self.pretrained_models_dir)

    @property
    def storage_path(self) -> Path:
        """返回存储根目录的 Path 对象。"""
        return Path(self.storage_dir)

    @property
    def hubert_path(self) -> str:
        """返回 chinese-hubert-base 模型路径。"""
        return str(self.pretrained_models_path / "chinese-hubert-base")

    @property
    def bert_path(self) -> str:
        """返回 chinese-roberta-wwm-ext-large 模型路径。"""
        return str(self.pretrained_models_path / "chinese-roberta-wwm-ext-large")

    @property
    def llm_enabled(self) -> bool:
        """LLM 是否启用（API Key 非空时为 True）。"""
        return bool(self.llm_api_key and self.llm_api_key.strip())


@lru_cache()
def get_settings() -> Settings:
    """
    获取全局配置单例。
    使用 lru_cache 确保只创建一次实例。
    """
    return Settings()
