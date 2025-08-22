from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Lead Scoring API"
    app_version: str = "1.0.0"
    env: str = "prod"

    @property
    def debug(self) -> bool:
        return self.env.lower() == "debug"

    # Server settings
    host: str = "0.0.0.0"  # nosec B104 # Intentional for containerized deployment
    port: int = 8000
    workers: int = 4

    # Model settings
    model_path: str = "/app/models/lead_scoring_model.joblib"
    model_bucket: str | None = None
    model_key: str | None = None

    # Performance settings
    max_batch_size: int = 100
    prediction_timeout: float = 0.5

    # AWS settings
    aws_region: str = "eu-west-1"

    # Security
    api_key_header: str = "X-API-Key"
    allowed_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
