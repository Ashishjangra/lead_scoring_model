from pydantic import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "Lead Scoring API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # Model settings
    model_path: str = "/app/models/lead_scoring_model.pkl"
    model_bucket: Optional[str] = None
    model_key: Optional[str] = None
    
    # Performance settings
    max_batch_size: int = 100
    prediction_timeout: float = 0.5
    
    # AWS settings
    aws_region: str = "us-west-2"
    
    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 8080
    
    # Security
    api_key_header: str = "X-API-Key"
    allowed_origins: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()