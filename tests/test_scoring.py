from fastapi.testclient import TestClient

from app.main import app

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
                "existing_customer": False,
            }
        ],
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
    for _ in range(5):
        leads.append(
            {
                "company_size": "Large",
                "industry": "Healthcare",
                "email_engagement_score": 0.7,
                "website_sessions": 5,
                "pages_viewed": 20,
                "existing_customer": False,
            }
        )

    payload = {"request_id": "batch-test-456", "leads": leads}

    response = client.post("/api/v1/scoring/score", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["total_leads"] == 5
    assert len(data["scores"]) == 5


def test_invalid_batch_size():
    """Test batch size validation"""
    leads = [{"company_size": "Small"} for _ in range(501)]

    payload = {"request_id": "invalid-batch", "leads": leads}

    response = client.post("/api/v1/scoring/score", json=payload)
    # Pydantic validation returns 422 for validation errors
    assert response.status_code == 422


def test_model_info():
    """Test model info endpoint"""
    response = client.get("/api/v1/scoring/model/info")
    assert response.status_code == 200

    data = response.json()
    assert "version" in data
    assert "loaded" in data


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "service" in data
    assert "version" in data
    assert "status" in data


def test_score_with_custom_features():
    """Test scoring with custom features"""
    payload = {
        "request_id": "custom-features-test",
        "leads": [
            {
                "company_size": "Medium",
                "industry": "Technology",
                "email_engagement_score": 0.9,
                "custom_features": {
                    "custom_feature_1": 0.75,
                    "custom_feature_2": 100.0,
                    "custom_feature_5": 42.5,
                },
            }
        ],
    }

    response = client.post("/api/v1/scoring/score", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["total_leads"] == 1
    assert 1 <= data["scores"][0]["score"] <= 5
    assert data["scores"][0]["features_used"] == 50


def test_score_minimal_lead():
    """Test scoring with minimal lead data"""
    payload = {"request_id": "minimal-test", "leads": [{"email_engagement_score": 0.1}]}

    response = client.post("/api/v1/scoring/score", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["total_leads"] == 1
    assert 1 <= data["scores"][0]["score"] <= 5


def test_score_empty_leads():
    """Test scoring with empty leads array"""
    payload = {"request_id": "empty-test", "leads": []}

    response = client.post("/api/v1/scoring/score", json=payload)
    assert response.status_code == 422  # Validation error for empty array


def test_xgboost_model_info():
    """Test that model info shows XGBoost model details"""
    response = client.get("/api/v1/scoring/model/info")
    assert response.status_code == 200

    data = response.json()
    assert data["version"] == "1.0.0"
    assert data["loaded"] is True
    assert data["features_count"] == 50
    assert "XGB" in data["model_type"]  # Should be XGBClassifier
