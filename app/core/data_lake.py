"""
Async data lake integration for writing prediction results
Optimized for high-throughput batch operations
"""

import asyncio
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import structlog
import boto3
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.models.schemas import LeadScore, ScoreRequest

logger = structlog.get_logger()


class DataLakeWriter:
    """Async data lake writer with connection pooling and batching"""
    
    def __init__(self):
        self.s3_client = None
        self.kinesis_client = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._batch_buffer = []
        self._buffer_lock = asyncio.Lock()
        self._last_flush = time.time()
        self.batch_size = 100
        self.flush_interval = 5.0  # seconds
        
    def _ensure_clients(self):
        """Lazy initialization of AWS clients"""
        if not self.s3_client:
            self.s3_client = boto3.client('s3', region_name=settings.aws_region)
        if not self.kinesis_client:
            self.kinesis_client = boto3.client('kinesis', region_name=settings.aws_region)
    
    async def write_predictions_async(
        self, 
        request_id: str,
        request: ScoreRequest,
        scores: List[LeadScore],
        processing_time_ms: float,
        model_version: str
    ) -> bool:
        """Write prediction results to data lake asynchronously"""
        try:
            # Prepare batch record
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Create enriched records with metadata
            records = []
            for i, (lead, score) in enumerate(zip(request.leads, scores)):
                record = {
                    "timestamp": timestamp,
                    "request_id": request_id,
                    "lead_id": getattr(lead, 'id', f"{request_id}_{i}"),
                    "model_version": model_version,
                    "processing_time_ms": processing_time_ms / len(scores),
                    "prediction": {
                        "score": score.score,
                        "confidence": score.confidence,
                        "features_used": score.features_used
                    },
                    "input_features": {
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
                        "last_campaign_interaction": lead.last_campaign_interaction.isoformat() if lead.last_campaign_interaction else None,
                        "custom_features": lead.custom_features
                    }
                }
                records.append(record)
            
            # Write to multiple destinations concurrently
            write_tasks = []
            
            # 1. Write to S3 data lake (batch)
            if hasattr(settings, 'data_lake_bucket') and settings.data_lake_bucket:
                write_tasks.append(
                    self._write_to_s3_async(request_id, timestamp, records)
                )
            
            # 2. Stream to Kinesis for real-time processing
            if hasattr(settings, 'kinesis_stream') and settings.kinesis_stream:
                write_tasks.append(
                    self._write_to_kinesis_async(records)
                )
            
            # 3. Buffer for batch writing (fallback)
            write_tasks.append(
                self._buffer_records(records)
            )
            
            # Execute all writes concurrently
            if write_tasks:
                results = await asyncio.gather(*write_tasks, return_exceptions=True)
                
                # Check for any failures
                failures = [r for r in results if isinstance(r, Exception)]
                if failures:
                    logger.warning(
                        "Some data lake writes failed",
                        request_id=request_id,
                        failures=len(failures),
                        errors=[str(f) for f in failures]
                    )
                    return False
            
            logger.info(
                "Prediction results written to data lake",
                request_id=request_id,
                records_count=len(records),
                destinations=len(write_tasks)
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to write to data lake",
                request_id=request_id,
                error=str(e)
            )
            return False
    
    async def _write_to_s3_async(self, request_id: str, timestamp: str, records: List[Dict[str, Any]]):
        """Write records to S3 data lake"""
        try:
            # Organize by date for partitioning
            date_partition = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y/%m/%d')
            
            # Create S3 key with partitioning
            s3_key = f"predictions/{date_partition}/batch_{request_id}_{int(time.time())}.json"
            
            # Prepare data
            batch_data = {
                "metadata": {
                    "request_id": request_id,
                    "timestamp": timestamp,
                    "record_count": len(records),
                    "version": "1.0"
                },
                "predictions": records
            }
            
            # Write to S3 asynchronously
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                self._s3_put_object,
                settings.data_lake_bucket,
                s3_key,
                json.dumps(batch_data, separators=(',', ':'))
            )
            
            logger.debug(
                "Records written to S3",
                bucket=settings.data_lake_bucket,
                key=s3_key,
                records=len(records)
            )
            
        except Exception as e:
            logger.error(
                "S3 write failed",
                request_id=request_id,
                error=str(e)
            )
            raise
    
    def _s3_put_object(self, bucket: str, key: str, body: str):
        """Sync S3 put operation"""
        self._ensure_clients()
        self.s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType='application/json',
            Metadata={
                'source': 'lead-scoring-api',
                'version': '1.0'
            }
        )
    
    async def _write_to_kinesis_async(self, records: List[Dict[str, Any]]):
        """Stream records to Kinesis"""
        try:
            # Prepare Kinesis records
            kinesis_records = []
            for record in records:
                kinesis_records.append({
                    'Data': json.dumps(record, separators=(',', ':')),
                    'PartitionKey': record['request_id']
                })
                
                # Kinesis batch limit is 500 records
                if len(kinesis_records) >= 500:
                    await self._send_kinesis_batch(kinesis_records[:500])
                    kinesis_records = kinesis_records[500:]
            
            # Send remaining records
            if kinesis_records:
                await self._send_kinesis_batch(kinesis_records)
                
        except Exception as e:
            logger.error("Kinesis write failed", error=str(e))
            raise
    
    async def _send_kinesis_batch(self, records: List[Dict[str, Any]]):
        """Send batch to Kinesis"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            self._kinesis_put_records,
            records
        )
    
    def _kinesis_put_records(self, records: List[Dict[str, Any]]):
        """Sync Kinesis put operation"""
        self._ensure_clients()
        response = self.kinesis_client.put_records(
            Records=records,
            StreamName=settings.kinesis_stream
        )
        
        # Check for failed records
        if response.get('FailedRecordCount', 0) > 0:
            logger.warning(
                "Some Kinesis records failed",
                failed_count=response['FailedRecordCount'],
                total_records=len(records)
            )
    
    async def _buffer_records(self, records: List[Dict[str, Any]]):
        """Buffer records for batch processing"""
        async with self._buffer_lock:
            self._batch_buffer.extend(records)
            
            # Check if we need to flush
            should_flush = (
                len(self._batch_buffer) >= self.batch_size or
                (time.time() - self._last_flush) >= self.flush_interval
            )
            
            if should_flush:
                await self._flush_buffer()
    
    async def _flush_buffer(self):
        """Flush buffered records"""
        if not self._batch_buffer:
            return
        
        try:
            # Create batch file
            timestamp = datetime.now(timezone.utc).isoformat()
            batch_id = f"buffer_{int(time.time())}"
            
            # Write buffer to S3 if configured
            if hasattr(settings, 'data_lake_bucket') and settings.data_lake_bucket:
                await self._write_to_s3_async(batch_id, timestamp, self._batch_buffer)
            
            logger.info(
                "Buffer flushed",
                records_count=len(self._batch_buffer),
                batch_id=batch_id
            )
            
            # Clear buffer
            self._batch_buffer.clear()
            self._last_flush = time.time()
            
        except Exception as e:
            logger.error("Buffer flush failed", error=str(e))
    
    async def health_check(self) -> Dict[str, Any]:
        """Check data lake connectivity"""
        health = {
            "s3_available": False,
            "kinesis_available": False,
            "buffer_size": len(self._batch_buffer),
            "last_flush": self._last_flush
        }
        
        try:
            # Check S3 connectivity
            if hasattr(settings, 'data_lake_bucket') and settings.data_lake_bucket:
                self._ensure_clients()
                await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self.s3_client.head_bucket,
                    Bucket=settings.data_lake_bucket
                )
                health["s3_available"] = True
                
        except Exception as e:
            logger.debug("S3 health check failed", error=str(e))
        
        try:
            # Check Kinesis connectivity
            if hasattr(settings, 'kinesis_stream') and settings.kinesis_stream:
                self._ensure_clients()
                await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self.kinesis_client.describe_stream,
                    StreamName=settings.kinesis_stream
                )
                health["kinesis_available"] = True
                
        except Exception as e:
            logger.debug("Kinesis health check failed", error=str(e))
        
        return health


# Global data lake writer instance
data_lake_writer = DataLakeWriter()