import asyncio
import pickle
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import boto3  # type: ignore[import-untyped]
import numpy as np
import pandas as pd
import structlog
from sklearn.ensemble import RandomForestClassifier  # type: ignore[import-untyped]

from app.core.config import settings
from app.core.constants import (
    COMPANY_SIZES,
    DEFAULT_DAYS_SINCE_INTERACTION,
    GEOGRAPHIES,
    INDUSTRIES,
    JOB_TITLES,
    MOCK_CONFIDENCE_VALUE,
    MODEL_S3_BUCKET,
    MODEL_S3_KEY,
    MODEL_TEMP_PATH,
    RANDOM_FOREST_ESTIMATORS,
    RANDOM_FOREST_RANDOM_STATE,
    SENIORITY_LEVELS,
    THREAD_POOL_MAX_WORKERS,
)
from app.models.schemas import LeadFeatures, LeadScore

logger = structlog.get_logger()


class LeadScoringPredictor:
    """Production lead scoring model predictor with performance optimizations"""

    def __init__(self) -> None:
        self.model: Any = None
        self.feature_columns: list[str] | None = None
        self.model_version = "1.0.0"
        self.executor = ThreadPoolExecutor(max_workers=THREAD_POOL_MAX_WORKERS)
        self._model_cache: dict[str, Any] = {}
        self._feature_cache: dict[str, Any] = {}
        self._load_model()

    def _load_model(self) -> None:
        """Load the XGBoost model from local file or S3"""
        try:
            if settings.model_bucket and settings.model_key:
                logger.info(
                    "Loading model from S3",
                    bucket=settings.model_bucket,
                    key=settings.model_key,
                )
                self._load_from_s3()
            else:
                logger.info("Loading model from local file", path=settings.model_path)
                self._load_from_file()

            logger.info("Model loaded successfully", version=self.model_version)

        except Exception as e:
            logger.error("Failed to load model", error=str(e))
            self._load_mock_model()

    def _load_from_s3(self) -> None:
        """Load model from S3"""
        s3 = boto3.client("s3", region_name=settings.aws_region)
        local_path = MODEL_TEMP_PATH
        bucket = MODEL_S3_BUCKET
        key = MODEL_S3_KEY
        s3.download_file(bucket, key, local_path)

        with open(local_path, "rb") as f:
            model_data = pickle.load(f)

        self.model = model_data["model"]
        self.feature_columns = model_data["feature_columns"]
        self.model_version = model_data.get("version", "1.0.0")

    def _load_from_file(self) -> None:
        """Load model from local file"""
        if Path(settings.model_path).exists():
            with open(settings.model_path, "rb") as f:
                model_data = pickle.load(f)

            self.model = model_data["model"]
            self.feature_columns = model_data["feature_columns"]
            self.model_version = model_data.get("version", "1.0.0")
        else:
            raise FileNotFoundError(f"Model file not found: {settings.model_path}")

    def _load_mock_model(self) -> None:
        """Load a mock model for development/testing"""
        logger.warning("Loading mock model for development")

        # Create mock feature columns (50 features as specified)
        self.feature_columns = [
            "company_size_encoded",
            "industry_encoded",
            "job_title_encoded",
            "seniority_level_encoded",
            "geography_encoded",
            "email_engagement_score",
            "website_sessions",
            "pages_viewed",
            "time_on_site",
            "form_fills",
            "content_downloads",
            "campaign_touchpoints",
            "account_revenue",
            "account_employees",
            "existing_customer_encoded",
            "days_since_last_interaction",
        ] + [
            f"custom_feature_{i}" for i in range(1, 35)
        ]  # 50 total features

        # Create a simple mock XGBoost model

        self.model = RandomForestClassifier(
            n_estimators=RANDOM_FOREST_ESTIMATORS,
            random_state=RANDOM_FOREST_RANDOM_STATE,
        )

        # Train on dummy data
        if self.feature_columns:
            X_dummy = np.random.rand(100, len(self.feature_columns))
            y_dummy = np.random.randint(1, 6, 100)
            self.model.fit(X_dummy, y_dummy)

        self.model_version = "mock-1.0.0"

    def _prepare_features(self, lead_features: list[LeadFeatures]) -> pd.DataFrame:
        """Convert lead features to model input format with vectorized processing"""

        # Categorical encodings (from constants)
        company_sizes = COMPANY_SIZES
        industries = INDUSTRIES
        job_titles = JOB_TITLES
        seniority_levels = SENIORITY_LEVELS
        geographies = GEOGRAPHIES

        # Extract data in vectorized manner
        data = {
            "company_size_encoded": [
                self._encode_categorical(lead.company_size, company_sizes)
                for lead in lead_features
            ],
            "industry_encoded": [
                self._encode_categorical(lead.industry, industries)
                for lead in lead_features
            ],
            "job_title_encoded": [
                self._encode_categorical(lead.job_title, job_titles)
                for lead in lead_features
            ],
            "seniority_level_encoded": [
                self._encode_categorical(lead.seniority_level, seniority_levels)
                for lead in lead_features
            ],
            "geography_encoded": [
                self._encode_categorical(lead.geography, geographies)
                for lead in lead_features
            ],
            "email_engagement_score": [
                lead.email_engagement_score or 0.0 for lead in lead_features
            ],
            "website_sessions": [lead.website_sessions or 0 for lead in lead_features],
            "pages_viewed": [lead.pages_viewed or 0 for lead in lead_features],
            "time_on_site": [lead.time_on_site or 0.0 for lead in lead_features],
            "form_fills": [lead.form_fills or 0 for lead in lead_features],
            "content_downloads": [
                lead.content_downloads or 0 for lead in lead_features
            ],
            "campaign_touchpoints": [
                lead.campaign_touchpoints or 0 for lead in lead_features
            ],
            "account_revenue": [lead.account_revenue or 0.0 for lead in lead_features],
            "account_employees": [
                lead.account_employees or 0 for lead in lead_features
            ],
            "existing_customer_encoded": [
                1 if lead.existing_customer else 0 for lead in lead_features
            ],
        }

        # Calculate days since last interaction vectorized
        now = pd.Timestamp.now()
        data["days_since_last_interaction"] = [
            (
                max(0, (now - pd.Timestamp(lead.last_campaign_interaction)).days)
                if lead.last_campaign_interaction
                else DEFAULT_DAYS_SINCE_INTERACTION
            )
            for lead in lead_features
        ]

        # Add custom features efficiently
        for i in range(1, 35):
            key = f"custom_feature_{i}"
            data[key] = [
                lead.custom_features.get(key, 0.0) if lead.custom_features else 0.0
                for lead in lead_features
            ]

        # Create DataFrame directly from dict (more efficient)
        df = pd.DataFrame(data)

        # Ensure all required columns are present
        if self.feature_columns:
            for col in self.feature_columns:
                if col not in df.columns:
                    df[col] = 0.0
            return df[self.feature_columns]
        return df

    def _encode_categorical(self, value: str | None, categories: list[str]) -> int:
        """Simple categorical encoding"""
        if not value:
            return 0
        try:
            return categories.index(value) + 1
        except ValueError:
            return len(categories) + 1  # Unknown category

    async def predict_batch(self, lead_features: list[LeadFeatures]) -> list[LeadScore]:
        """Predict scores for a batch of leads"""
        start_time = time.time()

        try:
            # Prepare features
            X = self._prepare_features(lead_features)

            # Run prediction in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            predictions = await loop.run_in_executor(
                self.executor, self._predict_sync, X
            )

            # Calculate confidence scores (mock implementation)
            if self.model and hasattr(self.model, "predict_proba"):
                probabilities = await loop.run_in_executor(
                    self.executor, self.model.predict_proba, X
                )
                confidences = [max(proba) for proba in probabilities]
            else:
                confidences = [MOCK_CONFIDENCE_VALUE] * len(
                    predictions
                )  # Mock confidence

            processing_time = (time.time() - start_time) * 1000

            # Create results
            results = []
            for _, (pred, conf) in enumerate(
                zip(predictions, confidences, strict=False)
            ):
                score = LeadScore(
                    score=int(pred),
                    confidence=float(conf),
                    features_used=(
                        len(self.feature_columns) if self.feature_columns else 0
                    ),
                    prediction_time_ms=processing_time / len(predictions),
                )
                results.append(score)

            logger.info(
                "Batch prediction completed",
                batch_size=len(lead_features),
                processing_time_ms=processing_time,
                model_version=self.model_version,
            )

            return results

        except Exception as e:
            logger.error("Prediction failed", error=str(e))
            raise

    def _predict_sync(self, X: pd.DataFrame) -> np.ndarray[Any, Any]:
        """Synchronous prediction method"""
        if self.model is None:
            raise ValueError("Model is not loaded")
        predictions = self.model.predict(X)

        # Ensure predictions are in range 1-5
        predictions = np.clip(predictions, 1, 5)

        return predictions  # type: ignore[no-any-return]

    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None

    def get_model_info(self) -> dict[str, Any]:
        """Get model information"""
        return {
            "version": self.model_version,
            "features_count": len(self.feature_columns) if self.feature_columns else 0,
            "loaded": self.is_loaded(),
            "model_type": type(self.model).__name__ if self.model else None,
        }


# Global predictor instance
predictor = LeadScoringPredictor()
