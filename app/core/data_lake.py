"""
Async data lake integration for writing prediction results to S3 in Parquet format
Optimized for high-throughput batch operations using AWS Wrangler
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import structlog
import boto3
import pandas as pd
import awswrangler as wr
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.models.schemas import LeadScore, ScoreRequest
from app.core.constants import (
    DATA_LAKE_THREAD_WORKERS, DATA_LAKE_S3_PATH, DATA_LAKE_DATABASE, 
    DATA_LAKE_TABLE_NAME, DATA_LAKE_PARTITION_COLUMNS, DATA_LAKE_WRITE_MODE, 
    DATA_LAKE_SCHEMA_EVOLUTION, DATA_LAKE_CONCURRENT_PARTITIONING
)

logger = structlog.get_logger()


class DataLakeWriter:
    """Async data lake writer using AWS Wrangler for Parquet format"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=DATA_LAKE_THREAD_WORKERS)
    
    async def write_predictions_async(
        self, 
        request_id: str,
        request: ScoreRequest,
        scores: List[LeadScore],
        processing_time_ms: float,
        model_version: str
    ) -> bool:
        """Write prediction results to data lake asynchronously using AWS Wrangler"""
        try:
            # Prepare timestamp for partitioning
            timestamp_dt = datetime.now(timezone.utc)
            
            # Create flat records for DataFrame
            records = []
            for i, (lead, score) in enumerate(zip(request.leads, scores)):
                # Flatten the structure for Parquet
                record = {
                    # Metadata
                    "request_id": request_id,
                    "lead_id": getattr(lead, 'id', f"{request_id}_{i}"),
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
                    
                    # Input features (flattened)
                    "company_size": lead.company_size,
                    "industry": lead.industry,
                    "job_title": lead.job_title,
                    "seniority_level": lead.seniority_level,
                    "geography": lead.geography,
                    "email_engagement_score": lead.email_engagement_score,
                    "website_sessions": lead.website_sessions,
                    "pages_viewed": lead.pages_viewed,
                    "time_on_site": lead.time_on_site,
                    "form_fills": lead.form_fills,
                    "content_downloads": lead.content_downloads,
                    "campaign_touchpoints": lead.campaign_touchpoints,
                    "account_revenue": lead.account_revenue,
                    "account_employees": lead.account_employees,
                    "existing_customer": lead.existing_customer,
                    "last_campaign_interaction": lead.last_campaign_interaction,
                }
                
                # Add custom features as separate columns
                if lead.custom_features:
                    for key, value in lead.custom_features.items():
                        record[f"custom_{key}"] = value
                
                records.append(record)
            
            # Write to Parquet using AWS Wrangler
            write_result = await self._write_parquet_to_catalog(records)
            
            logger.info(
                "Prediction results written to data lake",
                request_id=request_id,
                records_count=len(records),
                rows_written=write_result
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to write to data lake",
                request_id=request_id,
                error=str(e)
            )
            return False
    
    async def _write_parquet_to_catalog(self, records: List[Dict[str, Any]]) -> int:
        """Write records to AWS Data Catalog in Parquet format using AWS Wrangler"""
        try:
            # Create DataFrame from records
            df = pd.DataFrame(records)
            
            # Write to S3 in Parquet format with Glue Catalog registration
            loop = asyncio.get_event_loop()
            rows_written = await loop.run_in_executor(
                self.executor,
                self._write_parquet_sync,
                df
            )
            
            logger.debug(
                "Records written to Parquet",
                path=DATA_LAKE_S3_PATH,
                database=DATA_LAKE_DATABASE,
                table=DATA_LAKE_TABLE_NAME,
                records=rows_written
            )
            
            return rows_written
            
        except Exception as e:
            logger.error("Parquet write failed", error=str(e))
            raise
    
    def _write_parquet_sync(self, df: pd.DataFrame) -> int:
        """Synchronous Parquet write operation using AWS Wrangler"""
        # Create boto3 session with region
        boto3_session = boto3.Session(region_name=settings.aws_region)
        
        # Write to S3 in Parquet format
        wr.s3.to_parquet(
            df=df,
            path=DATA_LAKE_S3_PATH,
            dataset=True,
            database=DATA_LAKE_DATABASE,
            table=DATA_LAKE_TABLE_NAME,
            mode=DATA_LAKE_WRITE_MODE,
            index=False,
            partition_cols=DATA_LAKE_PARTITION_COLUMNS,
            boto3_session=boto3_session,
            schema_evolution=DATA_LAKE_SCHEMA_EVOLUTION,
            concurrent_partitioning=DATA_LAKE_CONCURRENT_PARTITIONING,
        )
        
        return len(df)
    


# Global data lake writer instance
data_lake_writer = DataLakeWriter()