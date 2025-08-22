from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid


class LeadFeatures(BaseModel):
    """Input features for lead scoring model"""
    # Contact/Lead attributes
    company_size: Optional[str] = Field(None, description="Company size category")
    industry: Optional[str] = Field(None, description="Industry vertical")
    job_title: Optional[str] = Field(None, description="Contact job title")
    seniority_level: Optional[str] = Field(None, description="Job seniority level")
    geography: Optional[str] = Field(None, description="Geographic region")
    
    # Behavioral features
    email_engagement_score: Optional[float] = Field(None, ge=0, le=1, description="Email engagement score")
    website_sessions: Optional[int] = Field(None, ge=0, description="Number of website sessions")
    pages_viewed: Optional[int] = Field(None, ge=0, description="Total pages viewed")
    time_on_site: Optional[float] = Field(None, ge=0, description="Total time on site (minutes)")
    form_fills: Optional[int] = Field(None, ge=0, description="Number of form fills")
    content_downloads: Optional[int] = Field(None, ge=0, description="Content downloads count")
    
    # Campaign interaction
    campaign_touchpoints: Optional[int] = Field(None, ge=0, description="Number of campaign touchpoints")
    last_campaign_interaction: Optional[datetime] = Field(None, description="Last campaign interaction date")
    
    # Account-level features
    account_revenue: Optional[float] = Field(None, ge=0, description="Account annual revenue")
    account_employees: Optional[int] = Field(None, ge=0, description="Number of employees")
    existing_customer: Optional[bool] = Field(None, description="Is existing customer")
    
    # Additional features (to reach 50 features)
    custom_features: Optional[Dict[str, Any]] = Field(None, description="Additional custom features")
    
    @validator('custom_features')
    def validate_custom_features(cls, v):
        if v and len(v) > 40:  # Limit custom features
            raise ValueError("Too many custom features provided")
        return v


class ScoreRequest(BaseModel):
    """Request model for lead scoring"""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique request ID")
    leads: List[LeadFeatures] = Field(..., min_items=1, max_items=100, description="List of leads to score")
    
    @validator('leads')
    def validate_leads(cls, v):
        if len(v) > 100:
            raise ValueError("Maximum 100 leads per request")
        return v


class LeadScore(BaseModel):
    """Individual lead score result"""
    score: int = Field(..., ge=1, le=5, description="Lead score (1-5)")
    confidence: float = Field(..., ge=0, le=1, description="Prediction confidence")
    features_used: int = Field(..., description="Number of features used in prediction")
    prediction_time_ms: float = Field(..., description="Prediction time in milliseconds")


class ScoreResponse(BaseModel):
    """Response model for lead scoring"""
    request_id: str = Field(..., description="Request ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    total_leads: int = Field(..., description="Total number of leads processed")
    processing_time_ms: float = Field(..., description="Total processing time in milliseconds")
    scores: List[LeadScore] = Field(..., description="Lead scores")
    model_version: str = Field(..., description="Model version used")
    status: str = Field(default="success", description="Processing status")


class HealthCheck(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(..., description="API version")
    model_loaded: bool = Field(..., description="Whether model is loaded")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")

