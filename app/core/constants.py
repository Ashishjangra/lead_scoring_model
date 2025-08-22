"""
Configuration constants for the Lead Scoring API application.
Contains paths, regions, buckets, and environment-specific settings.
"""

# Model Configuration
MODEL_PATH_DEFAULT = "/app/models/lead_scoring_model.joblib"
MODEL_TEMP_PATH = "/tmp/model.joblib"  # nosec B108 # Safe temp path for model files
MODEL_S3_BUCKET = "ml-marketing-lead-scoring"
MODEL_S3_KEY = "model/model.joblib"

# AWS Configuration
AWS_REGION_DEFAULT = "eu-west-1"
AWS_REGION_DEV = "eu-west-1"
AWS_REGION_PROD = "eu-west-1"

# AWS Wrangler Data Lake Configuration
DATA_LAKE_S3_PATH = "s3://ml-marketing-lead-scoring/inference_data/"
DATA_LAKE_DATABASE = "ml_marketing"
DATA_LAKE_TABLE_NAME = "lead_score"
DATA_LAKE_PARTITION_COLUMNS = ["year", "month", "day"]
DATA_LAKE_WRITE_MODE = "append"
DATA_LAKE_SCHEMA_EVOLUTION = True
DATA_LAKE_CONCURRENT_PARTITIONING = False


# Threading Configuration
THREAD_POOL_MAX_WORKERS = 8
DATA_LAKE_THREAD_WORKERS = 4

# Request Limits
MAX_REQUEST_SIZE_MB = 10
MAX_LEADS_PER_REQUEST = 500
MAX_BATCH_SIZE_DEFAULT = 100

# Data Lake Configuration (AWS Wrangler writes directly, no buffering needed)

# Environment Detection
ENV_DEBUG = "debug"
ENV_DEV = "dev"
ENV_PROD = "prod"

# Logging Configuration
LOG_GROUP_NAME = "lead-scoring"
LOG_STREAM_DEV = "dev"
LOG_STREAM_PROD = "prod"
LOG_FILE_PATH = "/tmp/lead-scoring.log"
LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Performance Configuration
PREDICTION_TIMEOUT_DEFAULT = 0.5  # seconds
MOCK_CONFIDENCE_VALUE = 0.8
DEFAULT_DAYS_SINCE_INTERACTION = 999

# Random Forest Configuration (Mock Model)
RANDOM_FOREST_ESTIMATORS = 10
RANDOM_FOREST_RANDOM_STATE = 42
