"""Test configuration and fixtures"""

import os
from unittest.mock import Mock, patch

import numpy as np
import pytest

# Set environment variables before any app imports
os.environ["ENV"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"


def pytest_configure(config):
    """Configure pytest with necessary patches before test collection"""
    # Patch boto3 globally to prevent credential issues
    boto3_patcher = patch("boto3.client")
    mock_boto3 = boto3_patcher.start()

    def mock_client_factory(service_name, **kwargs):
        mock_client = Mock()
        if service_name == "s3":
            mock_client.download_file.side_effect = Exception(
                "NoCredentialsError: test mode"
            )
        elif service_name == "cloudwatch":
            mock_client.put_metric_data.return_value = {}
        return mock_client

    mock_boto3.side_effect = mock_client_factory

    # Store patcher for cleanup
    config._boto3_patcher = boto3_patcher


def pytest_unconfigure(config):
    """Clean up patches after tests"""
    if hasattr(config, "_boto3_patcher"):
        config._boto3_patcher.stop()


@pytest.fixture(autouse=True)
def setup_test_predictor():
    """Set up predictor with mock model for all tests"""
    with patch("app.models.predictor.LeadScoringPredictor._load_from_s3"):
        # Import after patching
        from app.models.predictor import predictor

        # Create mock model that adapts to input size
        mock_model = Mock()
        mock_model.__class__.__name__ = "XGBClassifier"

        def mock_predict(X):
            # Return predictions matching input size
            batch_size = len(X) if hasattr(X, "__len__") else 1
            return np.random.randint(1, 6, size=batch_size)

        def mock_predict_proba(X):
            # Return probabilities matching input size
            batch_size = len(X) if hasattr(X, "__len__") else 1
            # Generate random probabilities that sum to 1
            probs = np.random.dirichlet(np.ones(5), size=batch_size)
            return probs

        mock_model.predict.side_effect = mock_predict
        mock_model.predict_proba.side_effect = mock_predict_proba

        # Set up predictor
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

        yield
