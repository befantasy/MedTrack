import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "MedTrack 肿瘤与慢病智能管理平台"
    API_V1_STR: str = "/api"
    
    # 数据库配置: 优先使用环境变量中的 PostgreSQL，未配置时回退到本地 SQLite 便于开发与测试
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./medtrack.db")
    
    # JWT 鉴权密钥
    JWT_SECRET: str = os.getenv("JWT_SECRET", "medtrack-super-secret-key-change-in-production-2026")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天免登录
    
    # 多模态 AI 大模型配置 (兼容 OpenAI 协议接口，可对接 Gemini, Qwen-VL, GPT-4o, DeepSeek 等)
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_BASE_URL: str = os.getenv("AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    AI_MODEL: str = os.getenv("AI_MODEL", "gemini-2.0-flash")
    
    # 文件存储目录
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "uploads"))

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
