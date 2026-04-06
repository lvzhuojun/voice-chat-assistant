"""
应用配置模块
使用 pydantic-settings 从 .env 文件读取配置，类型安全
Application configuration module.
Reads configuration from .env file using pydantic-settings with type safety.
"""

from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    全局配置类，所有配置项均从环境变量 / .env 文件读取。
    不硬编码任何路径或密钥。
    Global settings class; all configuration values are read from environment
    variables or the .env file. No paths or secrets are hard-coded.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 服务地址 / Service addresses ──────────────────────────
    host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_port: int = 5173

    # ── 数据库 / Database ─────────────────────────────────────
    database_url: str = "postgresql://user:password@localhost:5432/voicechat"

    # ── Redis ─────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── JWT 认证 / JWT authentication ─────────────────────────
    jwt_secret_key: str = "change-this-to-a-random-string"
    jwt_expire_days: int = 7

    # ── LLM（OpenAI 兼容）/ LLM (OpenAI-compatible) ──────────
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

    # ── TTS（CosyVoice 2）────────────────────────────────────
    # CosyVoice 仓库目录；预训练模型须位于 {cosyvoice_dir}/pretrained_models/CosyVoice2-0.5B
    # CosyVoice repository directory; pretrained model must be located at
    # {cosyvoice_dir}/pretrained_models/CosyVoice2-0.5B
    cosyvoice_dir: str = "./CosyVoice"

    # ── 安全与限制 / Security and limits ─────────────────────
    # 额外允许的 CORS 来源（逗号分隔，生产部署时配置真实域名）
    # Additional allowed CORS origins (comma-separated; set real domains in production)
    # 示例 / Example：CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
    cors_origins: str = ""
    # 音色 ZIP 包最大上传大小（MB）/ Maximum upload size for voice ZIP packages (MB)
    max_upload_size_mb: int = 500

    @property
    def voice_models_path(self) -> Path:
        """
        返回音色模型目录的 Path 对象。
        Return the voice model directory as a Path object.
        """
        return Path(self.voice_models_dir)

    @property
    def pretrained_models_path(self) -> Path:
        """
        返回预训练模型目录的 Path 对象。
        Return the pretrained model directory as a Path object.
        """
        return Path(self.pretrained_models_dir)

    @property
    def storage_path(self) -> Path:
        """
        返回存储根目录的 Path 对象。
        Return the storage root directory as a Path object.
        """
        return Path(self.storage_dir)

    @property
    def hubert_path(self) -> str:
        """
        返回 chinese-hubert-base 模型路径。
        Return the path to the chinese-hubert-base model.
        """
        return str(self.pretrained_models_path / "chinese-hubert-base")

    @property
    def bert_path(self) -> str:
        """
        返回 chinese-roberta-wwm-ext-large 模型路径。
        Return the path to the chinese-roberta-wwm-ext-large model.
        """
        return str(self.pretrained_models_path / "chinese-roberta-wwm-ext-large")

    @property
    def llm_enabled(self) -> bool:
        """
        LLM 是否启用（API Key 非空时为 True）。
        Whether LLM is enabled (True when the API key is non-empty).
        """
        return bool(self.llm_api_key and self.llm_api_key.strip())


@lru_cache()
def get_settings() -> Settings:
    """
    获取全局配置单例。
    使用 lru_cache 确保只创建一次实例。
    Return the global settings singleton.
    Uses lru_cache to ensure only one instance is created.
    """
    return Settings()
