"""Test configuration and fixtures"""

from unittest.mock import Mock, patch

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def mock_model_loading():
    """Mock model loading to avoid AWS credentials requirement in tests"""
    with patch("app.models.predictor.LeadScoringPredictor._load_from_s3") as mock_s3:
        # Create a mock model
        mock_model = Mock()
        mock_model.predict.return_value = np.array(
            [3, 4, 2, 5, 1]
        )  # Sample predictions
        mock_model.predict_proba.return_value = np.array(
            [
                [0.1, 0.1, 0.6, 0.1, 0.1],  # High confidence for score 3
                [0.05, 0.05, 0.05, 0.8, 0.05],  # High confidence for score 4
                [0.2, 0.6, 0.1, 0.05, 0.05],  # High confidence for score 2
                [0.05, 0.05, 0.05, 0.05, 0.8],  # High confidence for score 5
                [0.8, 0.1, 0.05, 0.025, 0.025],  # High confidence for score 1
            ]
        )

        def mock_load_side_effect():
            # Set up the predictor with mock data
            from app.models.predictor import predictor

            predictor.model = mock_model
            predictor.feature_columns = [f"feature_{i}" for i in range(50)]
            predictor.model_version = "1.0.0"
            predictor.parameters = {"test": True}
            predictor.preprocessing_info = {
                "categorical_mappings": {
                    "company_size": ["Small", "Medium", "Large", "Enterprise"],
                    "industry": ["Technology", "Healthcare", "Finance", "Retail"],
                    "job_title": ["Manager", "Director", "VP", "C-Level"],
                    "seniority_level": ["Junior", "Mid", "Senior", "Executive"],
                    "geography": ["North America", "Europe", "Asia Pacific"],
                }
            }

        mock_s3.side_effect = mock_load_side_effect
        yield mock_s3


@pytest.fixture(autouse=True)
def mock_cloudwatch():
    """Mock CloudWatch metrics to avoid AWS calls in tests"""
    with patch("app.core.metrics.CloudWatchMetrics.__init__") as mock_init:
        mock_init.return_value = None
        with patch(
            "app.core.metrics.metrics_publisher.publish_prediction_metrics"
        ) as mock_publish:
            mock_publish.return_value = None
            yield mock_publish


@pytest.fixture(autouse=True)
def mock_data_lake():
    """Mock data lake writer to avoid AWS calls in tests"""
    with patch(
        "app.core.data_lake.DataLakeWriter.write_predictions_async"
    ) as mock_write:
        mock_write.return_value = True
        yield mock_write
