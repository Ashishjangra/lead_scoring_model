"""
CloudWatch metrics collection for lead scoring API
Tracks prediction quality, operational, business, and infrastructure metrics
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import boto3  # type: ignore[import-untyped]
import numpy as np
import pandas as pd
import structlog

from app.core.config import settings
from app.core.constants import (
    METRICS_NAMESPACE_DEV,
    METRICS_NAMESPACE_PROD,
    METRICS_THREAD_WORKERS,
)
from app.models.schemas import LeadScore

logger = structlog.get_logger()


class CloudWatchMetrics:
    """CloudWatch metrics publisher for lead scoring API"""

    def __init__(self) -> None:
        self.cloudwatch = boto3.client("cloudwatch", region_name=settings.aws_region)
        self.executor = ThreadPoolExecutor(max_workers=METRICS_THREAD_WORKERS)
        self.namespace = METRICS_NAMESPACE_DEV if settings.env == "dev" else METRICS_NAMESPACE_PROD

    async def publish_prediction_metrics(
        self,
        request_id: str,
        scores: list[LeadScore],
        processing_time_ms: float,
        model_version: str,
        engineered_features: pd.DataFrame | None = None,
    ) -> None:
        """Publish prediction quality and business metrics"""
        try:
            timestamp = datetime.now(timezone.utc)
            
            # Extract score and confidence values
            score_values = [score.score for score in scores]
            confidence_values = [score.confidence for score in scores]
            
            # Prepare metrics data
            metrics_data = []
            
            # Essential metrics for lead scoring
            total_predictions = len(scores)
            avg_score = sum(score_values) / len(score_values) if score_values else 0
            avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0
            high_conf_count = sum(1 for c in confidence_values if c > 0.9) if confidence_values else 0
            high_conf_percentage = (high_conf_count / total_predictions * 100) if total_predictions > 0 else 0
            
            # Score distribution per score value
            for score in range(1, 6):
                score_count = score_values.count(score)
                metrics_data.append({
                    "MetricName": "ScoreDistribution",
                    "Value": score_count,
                    "Unit": "Count",
                    "Timestamp": timestamp,
                    "Dimensions": [
                        {"Name": "Score", "Value": str(score)},
                        {"Name": "Environment", "Value": settings.env},
                    ]
                })
            
            # Core metrics
            core_metrics = [
                ("PredictionVolume", total_predictions, "Count"),
                ("AverageScore", avg_score, "None"),
                ("AverageConfidence", avg_confidence, "None"),
                ("HighConfidencePredictions", high_conf_count, "Count"),
                ("HighConfidencePercentage", high_conf_percentage, "Percent"),
                ("ProcessingTimeMs", processing_time_ms, "Milliseconds"),
                ("RequestSuccess", 1.0, "Count"),
            ]
            
            for metric_name, value, unit in core_metrics:
                if pd.notna(value) and np.isfinite(value):
                    metrics_data.append({
                        "MetricName": metric_name,
                        "Value": float(value),
                        "Unit": unit,
                        "Timestamp": timestamp,
                        "Dimensions": [{"Name": "Environment", "Value": settings.env}]
                    })
            
            # Publish metrics asynchronously
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor, self._publish_metrics_sync, metrics_data
            )
            
            logger.debug(
                "Metrics published successfully",
                request_id=request_id,
                metrics_count=len(metrics_data),
            )

        except Exception as e:
            logger.error("Failed to publish metrics", request_id=request_id, error=str(e))

    async def publish_failure_metrics(self, error_type: str) -> None:
        """Publish failure metrics for operational monitoring"""
        try:
            timestamp = datetime.now(timezone.utc)
            metrics_data = []
            
            # Operational failure metrics
            self._add_operational_metrics(metrics_data, 0, 0, timestamp, False, error_type)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor, self._publish_metrics_sync, metrics_data
            )

        except Exception as e:
            logger.error("Failed to publish failure metrics", error=str(e))



    def _add_score_distribution_metrics(
        self, metrics_data: list[dict[str, Any]], scores: list[int], timestamp: datetime
    ) -> None:
        """Add score distribution metrics"""
        score_counts = {}
        for score in range(1, 6):
            score_counts[score] = scores.count(score)
        
        for score, count in score_counts.items():
            metrics_data.append({
                "MetricName": "ScoreDistribution",
                "Value": count,
                "Unit": "Count",
                "Timestamp": timestamp,
                "Dimensions": [
                    {"Name": "Score", "Value": str(score)},
                    {"Name": "Environment", "Value": settings.env},
                ]
            })

    def _add_confidence_metrics(
        self, metrics_data: list[dict[str, Any]], confidences: list[float], timestamp: datetime
    ) -> None:
        """Add confidence statistics metrics"""
        if not confidences:
            return
            
        # Filter out any NaN values from confidences
        valid_confidences = [c for c in confidences if pd.notna(c) and np.isfinite(c)]
        if not valid_confidences:
            return
            
        conf_array = np.array(valid_confidences)
        
        mean_conf = np.mean(conf_array)
        p95_conf = np.percentile(conf_array, 95)
        p99_conf = np.percentile(conf_array, 99)
        
        # Only add metrics if values are valid
        if pd.notna(mean_conf) and np.isfinite(mean_conf):
            metrics_data.append({
                "MetricName": "ConfidenceMean",
                "Value": float(mean_conf),
                "Unit": "None",
                "Timestamp": timestamp,
                "Dimensions": [{"Name": "Environment", "Value": settings.env}]
            })
        
        if pd.notna(p95_conf) and np.isfinite(p95_conf):
            metrics_data.append({
                "MetricName": "ConfidenceP95",
                "Value": float(p95_conf),
                "Unit": "None", 
                "Timestamp": timestamp,
                "Dimensions": [{"Name": "Environment", "Value": settings.env}]
            })
        
        if pd.notna(p99_conf) and np.isfinite(p99_conf):
            metrics_data.append({
                "MetricName": "ConfidenceP99",
                "Value": float(p99_conf),
                "Unit": "None",
                "Timestamp": timestamp,
                "Dimensions": [{"Name": "Environment", "Value": settings.env}]
            })

    def _add_business_metrics(
        self,
        metrics_data: list[dict[str, Any]],
        scores: list[int],
        confidences: list[float],
        timestamp: datetime,
    ) -> None:
        """Add business metrics"""
        total_predictions = len(scores)
        high_confidence_count = sum(1 for c in confidences if c > 0.9)
        high_confidence_percentage = (high_confidence_count / total_predictions * 100) if total_predictions > 0 else 0
        
        metrics_data.extend([
            {
                "MetricName": "PredictionVolume",
                "Value": total_predictions,
                "Unit": "Count",
                "Timestamp": timestamp,
                "Dimensions": [{"Name": "Environment", "Value": settings.env}]
            },
            {
                "MetricName": "HighConfidencePredictions",
                "Value": high_confidence_count,
                "Unit": "Count",
                "Timestamp": timestamp,
                "Dimensions": [{"Name": "Environment", "Value": settings.env}]
            },
            {
                "MetricName": "HighConfidencePercentage",
                "Value": high_confidence_percentage,
                "Unit": "Percent",
                "Timestamp": timestamp,
                "Dimensions": [{"Name": "Environment", "Value": settings.env}]
            }
        ])

    def _add_drift_metrics(
        self,
        metrics_data: list[dict[str, Any]],
        features: pd.DataFrame,
        timestamp: datetime,
        model_version: str,
    ) -> None:
        """Add model drift detection metrics"""
        # Calculate basic feature statistics for drift detection
        feature_means = features.select_dtypes(include=[np.number]).mean()
        feature_stds = features.select_dtypes(include=[np.number]).std()
        
        # Monitor engineered feature columns that actually exist
        numeric_features = features.select_dtypes(include=[np.number])
        
        for feature in numeric_features.columns:
            if feature in feature_means.index:
                mean_val = feature_means[feature]
                std_val = feature_stds[feature]
                
                # Skip NaN/inf values to avoid CloudWatch errors
                if pd.notna(mean_val) and np.isfinite(mean_val):
                    metrics_data.append({
                        "MetricName": "FeatureMean",
                        "Value": float(mean_val),
                        "Unit": "None",
                        "Timestamp": timestamp,
                        "Dimensions": [
                            {"Name": "Feature", "Value": feature},
                            {"Name": "Environment", "Value": settings.env},
                            {"Name": "ModelVersion", "Value": model_version},
                        ]
                    })
                
                if pd.notna(std_val) and np.isfinite(std_val):
                    metrics_data.append({
                        "MetricName": "FeatureStd",
                        "Value": float(std_val),
                        "Unit": "None",
                        "Timestamp": timestamp,
                        "Dimensions": [
                            {"Name": "Feature", "Value": feature},
                            {"Name": "Environment", "Value": settings.env},
                            {"Name": "ModelVersion", "Value": model_version},
                        ]
                    })

    def _add_operational_metrics(
        self,
        metrics_data: list[dict[str, Any]],
        batch_size: int,
        processing_time_ms: float,
        timestamp: datetime,
        success: bool,
        error_type: str | None = None,
    ) -> None:
        """Add operational metrics"""
        metrics_data.extend([
            {
                "MetricName": "RequestSuccess" if success else "RequestFailure",
                "Value": 1.0,
                "Unit": "Count",
                "Timestamp": timestamp,
                "Dimensions": [
                    {"Name": "Environment", "Value": settings.env},
                    {"Name": "ErrorType", "Value": error_type or "None"},
                ]
            },
            {
                "MetricName": "ProcessingTimeMs",
                "Value": processing_time_ms,
                "Unit": "Milliseconds",
                "Timestamp": timestamp,
                "Dimensions": [{"Name": "Environment", "Value": settings.env}]
            },
            {
                "MetricName": "BatchSize",
                "Value": batch_size,
                "Unit": "Count",
                "Timestamp": timestamp,
                "Dimensions": [{"Name": "Environment", "Value": settings.env}]
            }
        ])

    def _publish_metrics_sync(self, metrics_data: list[dict[str, Any]]) -> None:
        """Synchronous metrics publishing to CloudWatch"""
        if not metrics_data:
            return
        
        # Filter out any metrics with NaN or infinite values
        valid_metrics = []
        for i, metric in enumerate(metrics_data):
            value = metric.get("Value")
            if value is not None and pd.notna(value) and np.isfinite(value):
                valid_metrics.append(metric)
            else:
                logger.warning("Skipping invalid metric", 
                             index=i, 
                             metric_name=metric.get("MetricName"), 
                             value=value, 
                             value_type=type(value))
        
        if not valid_metrics:
            logger.warning("No valid metrics to publish")
            return
            
        # CloudWatch allows max 20 metrics per put_metric_data call
        chunk_size = 20
        for i in range(0, len(valid_metrics), chunk_size):
            chunk = valid_metrics[i:i + chunk_size]
            
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=chunk
            )
            
            # Small delay between chunks to avoid throttling
            if i + chunk_size < len(valid_metrics):
                time.sleep(0.1)


# Global metrics publisher instance
metrics_publisher = CloudWatchMetrics()