import pytest
import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.models.schemas import LeadFeatures

client = TestClient(app)


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "uptime_seconds" in data


def test_readiness_check():
    """Test readiness check endpoint"""
    response = client.get("/api/v1/health/ready")
    assert response.status_code in [200, 503]


def test_liveness_check():
    """Test liveness check endpoint"""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_score_leads_endpoint():
    """Test lead scoring endpoint"""
    payload = {
        "request_id": "test-request-123",
        "leads": [
            {
                "company_size": "Enterprise",
                "industry": "Technology",
                "job_title": "VP Marketing",
                "seniority_level": "Executive",
                "geography": "North America",
                "email_engagement_score": 0.85,
                "website_sessions": 12,
                "pages_viewed": 45,
                "time_on_site": 23.5,
                "form_fills": 3,
                "content_downloads": 5,
                "campaign_touchpoints": 8,
                "account_revenue": 50000000,
                "account_employees": 5000,
                "existing_customer": False
            }
        ]
    }
    
    response = client.post("/api/v1/scoring/score", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["request_id"] == "test-request-123"
    assert data["total_leads"] == 1
    assert len(data["scores"]) == 1
    assert 1 <= data["scores"][0]["score"] <= 5
    assert 0 <= data["scores"][0]["confidence"] <= 1


def test_score_leads_batch():
    """Test batch scoring"""
    leads = []
    for i in range(5):
        leads.append({
            "company_size": "Large",
            "industry": "Healthcare",
            "email_engagement_score": 0.7,
            "website_sessions": 5,
            "pages_viewed": 20,
            "existing_customer": False
        })
    
    payload = {
        "request_id": "batch-test-456",
        "leads": leads
    }
    
    response = client.post("/api/v1/scoring/score", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["total_leads"] == 5
    assert len(data["scores"]) == 5


def test_invalid_batch_size():
    """Test batch size validation"""
    leads = [{"company_size": "Small"} for _ in range(101)]
    
    payload = {
        "request_id": "invalid-batch",
        "leads": leads
    }
    
    response = client.post("/api/v1/scoring/score", json=payload)
    assert response.status_code == 400


def test_model_info():
    """Test model info endpoint"""
    response = client.get("/api/v1/scoring/model/info")
    assert response.status_code == 200
    
    data = response.json()
    assert "version" in data
    assert "loaded" in data


def test_prometheus_metrics():
    """Test Prometheus metrics endpoint"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text


def test_system_metrics():
    """Test system metrics endpoint"""
    response = client.get("/api/v1/metrics/system")
    assert response.status_code == 200
    
    data = response.json()
    assert "cpu_percent" in data
    assert "memory_percent" in data
    assert "uptime_seconds" in data