"""
Async data lake integration for writing prediction results to S3 in Parquet format
Optimized for high-throughput batch operations using AWS Wrangler
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import awswrangler as wr
import boto3  # type: ignore[import-untyped]
import pandas as pd
import structlog

from app.core.config import settings
from app.core.constants import (
    DATA_LAKE_CONCURRENT_PARTITIONING,
    DATA_LAKE_DATABASE,
    DATA_LAKE_PARTITION_COLUMNS,
    DATA_LAKE_S3_PATH_DEV,
    DATA_LAKE_S3_PATH_PROD,
    DATA_LAKE_SCHEMA_EVOLUTION,
    DATA_LAKE_TABLE_NAME_DEV,
    DATA_LAKE_TABLE_NAME_PROD,
    DATA_LAKE_THREAD_WORKERS,
    DATA_LAKE_WRITE_MODE,
)
from app.models.schemas import LeadScore, ScoreRequest

logger = structlog.get_logger()


class DataLakeWriter:
    """Async data lake writer using AWS Wrangler for Parquet format"""

    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=DATA_LAKE_THREAD_WORKERS)

    async def write_predictions_async(
        self,
        request_id: str,
        request: ScoreRequest,
        scores: list[LeadScore],
        processing_time_ms: float,
        model_version: str,
        engineered_features: pd.DataFrame | None = None,
    ) -> bool:
        """Write prediction results to data lake asynchronously using AWS Wrangler"""
        try:
            # Prepare timestamp for partitioning
            timestamp_dt = datetime.now(timezone.utc)

            # Create comprehensive records with both raw and engineered features
            records = []
            for i, (lead, score) in enumerate(zip(request.leads, scores, strict=False)):
                # Base record with metadata and results
                record = {
                    # Metadata
                    "request_id": request_id,
                    "lead_id": getattr(lead, "id", f"{request_id}_{i}"),
                    "model_version": model_version,
                    "processing_time_ms": processing_time_ms / len(scores),
                    "timestamp": timestamp_dt,
                    # Partition columns
                    "year": timestamp_dt.year,
                    "month": timestamp_dt.month,
                    "day": timestamp_dt.day,
                    # Prediction results
                    "score": score.score,
                    "confidence": score.confidence,
                    "features_used": score.features_used,
                    # Raw input features (original data)
                    "raw_company_size": lead.company_size,
                    "raw_industry": lead.industry,
                    "raw_job_title": lead.job_title,
                    "raw_seniority_level": lead.seniority_level,
                    "raw_geography": lead.geography,
                    "raw_email_engagement_score": lead.email_engagement_score,
                    "raw_website_sessions": lead.website_sessions,
                    "raw_pages_viewed": lead.pages_viewed,
                    "raw_time_on_site": lead.time_on_site,
                    "raw_form_fills": lead.form_fills,
                    "raw_content_downloads": lead.content_downloads,
                    "raw_campaign_touchpoints": lead.campaign_touchpoints,
                    "raw_account_revenue": lead.account_revenue,
                    "raw_account_employees": lead.account_employees,
                    "raw_existing_customer": lead.existing_customer,
                    "raw_last_campaign_interaction": lead.last_campaign_interaction,
                }

                # Add raw custom features
                if lead.custom_features:
                    for key, value in lead.custom_features.items():
                        record[f"raw_{key}"] = value

                # Add ALL 50 engineered features that were actually used by the model
                if engineered_features is not None and i < len(engineered_features):
                    for col in engineered_features.columns:
                        record[f"engineered_{col}"] = engineered_features.iloc[i][col]

                records.append(record)

            # Write to Parquet using AWS Wrangler
            write_result = await self._write_parquet_to_catalog(records)

            logger.info(
                "Prediction results written to data lake",
                request_id=request_id,
                records_count=len(records),
                rows_written=write_result,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to write to data lake", request_id=request_id, error=str(e)
            )
            return False

    async def _write_parquet_to_catalog(self, records: list[dict[str, Any]]) -> int:
        """Write records to AWS Data Catalog in Parquet format using AWS Wrangler"""
        try:
            # Create DataFrame from records
            df = pd.DataFrame(records)

            # Fix data types for AWS Wrangler/Athena compatibility
            if "raw_last_campaign_interaction" in df.columns:
                df["raw_last_campaign_interaction"] = df["raw_last_campaign_interaction"].astype("string")

            # Write to S3 in Parquet format with Glue Catalog registration
            loop = asyncio.get_event_loop()
            rows_written = await loop.run_in_executor(
                self.executor, self._write_parquet_sync, df
            )

            table_name = DATA_LAKE_TABLE_NAME_DEV if settings.env == "dev" else DATA_LAKE_TABLE_NAME_PROD
            s3_path = DATA_LAKE_S3_PATH_DEV if settings.env == "dev" else DATA_LAKE_S3_PATH_PROD
            logger.debug(
                "Records written to Parquet",
                path=s3_path,
                database=DATA_LAKE_DATABASE,
                table=table_name,
                records=rows_written,
            )

            return rows_written

        except Exception as e:
            logger.error("Parquet write failed", error=str(e))
            raise

    def _write_parquet_sync(self, df: pd.DataFrame) -> int:
        """Synchronous Parquet write operation using AWS Wrangler"""
        # Create boto3 session with region
        boto3_session = boto3.Session(region_name=settings.aws_region)

        # Determine table name and S3 path based on environment
        table_name = DATA_LAKE_TABLE_NAME_DEV if settings.env == "dev" else DATA_LAKE_TABLE_NAME_PROD
        s3_path = DATA_LAKE_S3_PATH_DEV if settings.env == "dev" else DATA_LAKE_S3_PATH_PROD

        # Write to S3 in Parquet format
        wr.s3.to_parquet(
            df=df,
            path=s3_path,
            dataset=True,
            database=DATA_LAKE_DATABASE,
            table=table_name,
            mode=DATA_LAKE_WRITE_MODE,  # type: ignore
            index=False,
            partition_cols=DATA_LAKE_PARTITION_COLUMNS,
            boto3_session=boto3_session,
            schema_evolution=DATA_LAKE_SCHEMA_EVOLUTION,
            concurrent_partitioning=DATA_LAKE_CONCURRENT_PARTITIONING,
        )

        return len(df)


# Global data lake writer instance
data_lake_writer = DataLakeWriter()
