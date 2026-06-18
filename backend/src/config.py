from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 智谱 AI（优先）
    zhipu_api_key: str = ""
    zhipu_chat_model: str = "glm-5"
    zhipu_embedding_model: str = "embedding-3"

    # OLLAMA / 本地模型（备用）
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model_name: str = ""

    # 通用 LLM 参数
    llm_temperature: float = 0.3

    # 数据模式
    data_mode: str = "real"  # mock | real

    # 数据库配置
    database_path: str = "data/gasturbine.db"
    data_retention_days: int = 365

    # JWT 认证配置
    jwt_secret_key: str = "gas-turbine-llm-demo-secret-key-change-in-production"
    jwt_expire_hours: int = 24
    admin_default_password: str = "admin123"

    # 混合检索配置
    embedding_enabled: bool = True
    embedding_batch_size: int = 32
    rrf_k: int = 60
    chunk_max_size: int = 800

    # 向量知识库（外部 Milvus 系统）默认配置
    vector_retrieve_url: str = ""       # 如 http://192.168.1.93:43425/retrieve
    vector_ocr_url: str = ""            # 如 http://192.168.7.6:32281/file_parse
    vector_minio_url: str = ""          # 如 http://192.168.111.4:39000
    vector_minio_bucket: str = "mineru"
    vector_minio_ak: str = ""
    vector_minio_sk: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def active_llm_base_url(self) -> str:
        """智谱优先，否则回退 OLLAMA 配置。"""
        if self.zhipu_api_key:
            return "https://open.bigmodel.cn/api/paas/v4/"
        return self.llm_base_url or "http://localhost:11434/v1"

    @property
    def active_llm_api_key(self) -> str:
        if self.zhipu_api_key:
            return self.zhipu_api_key
        return self.llm_api_key or "empty"

    @property
    def active_llm_model_name(self) -> str:
        if self.zhipu_api_key:
            return self.zhipu_chat_model
        return self.llm_model_name or "qwen2.5:72b"

    @property
    def is_zhipu(self) -> bool:
        return bool(self.zhipu_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
