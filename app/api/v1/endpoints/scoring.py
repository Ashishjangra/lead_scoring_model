import time

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.data_lake import data_lake_writer
from app.core.metrics import metrics_publisher
from app.models.predictor import predictor
from app.models.schemas import ScoreRequest, ScoreResponse

logger = structlog.get_logger()
router = APIRouter()


async def validate_request_size(request: Request) -> None:
    """Validate request size to prevent DoS"""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=413, detail="Request too large")


@router.post("/score", response_model=ScoreResponse)
async def score_leads(
    score_request: ScoreRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(validate_request_size),
) -> ScoreResponse:
    """Score leads using the ML model"""
    start_time = time.time()
    request_id = getattr(request.state, "request_id", score_request.request_id)

    logger.info(
        "Starting lead scoring",
        request_id=request_id,
        num_leads=len(score_request.leads),
    )

    try:
        # Check if model is loaded
        if not predictor.is_loaded():
            raise HTTPException(
                status_code=503, detail="Model not available. Please try again later."
            )

        # Validate batch size (increased for better throughput)
        if len(score_request.leads) > 500:
            raise HTTPException(status_code=400, detail="Maximum 500 leads per request")

        # Get model info
        model_info = predictor.get_model_info()
        model_version = model_info.get("version", "unknown")

        # Predict scores and get engineered features
        scores, engineered_features = await predictor.predict_batch(score_request.leads)

        # Calculate total processing time
        processing_time_ms = (time.time() - start_time) * 1000

        # Create response
        response = ScoreResponse(
            request_id=score_request.request_id,
            total_leads=len(score_request.leads),
            processing_time_ms=processing_time_ms,
            scores=scores,
            model_version=model_version,
        )

        # Write results to data lake asynchronously with complete feature data
        background_tasks.add_task(
            data_lake_writer.write_predictions_async,
            request_id,
            score_request,
            scores,
            processing_time_ms,
            model_version,
            engineered_features,
        )

        # Publish metrics to CloudWatch asynchronously
        background_tasks.add_task(
            metrics_publisher.publish_prediction_metrics,
            request_id,
            scores,
            processing_time_ms,
            model_version,
            engineered_features,
        )

        logger.info(
            "Lead scoring completed",
            request_id=request_id,
            processing_time_ms=processing_time_ms,
            num_predictions=len(scores),
        )

        return response

    except HTTPException:
        # Publish failure metrics (temporarily disabled)
        # background_tasks.add_task(
        #     metrics_publisher.publish_failure_metrics,
        #     f"HTTP_{he.status_code}",
        # )
        raise
    except Exception as e:
        logger.error("Lead scoring failed", request_id=request_id, error=str(e))
        # Publish failure metrics (temporarily disabled)
        # background_tasks.add_task(
        #     metrics_publisher.publish_failure_metrics,
        #     "InternalError",
        # )
        raise HTTPException(
            status_code=500, detail="Internal server error during prediction"
        ) from None


@router.get("/model/info")
async def get_model_info() -> JSONResponse:
    """Get information about the loaded model"""
    try:
        info = predictor.get_model_info()
        return JSONResponse(content=info)
    except Exception as e:
        logger.error("Failed to get model info", error=str(e))
        raise HTTPException(
            status_code=500, detail="Failed to retrieve model information"
        ) from None
