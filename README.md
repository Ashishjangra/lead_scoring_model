# Lead Scoring API

A production-ready FastAPI service for scoring B2B leads using XGBoost, designed for Salesforce Marketing AI/ML team requirements.

## Features

- **High Performance**: Handles ~300 requests/second with sub-1-second response times
- **Scalable Architecture**: Built with FastAPI and async processing
- **Production Ready**: Comprehensive logging and security
- **ML-Optimized**: XGBoost model with 50+ features from multiple data sources
- **Container Ready**: Docker containerization with health checks
- **ECS Fargate Ready**: Optimized for AWS ECS Fargate deployment with load balancer

## Quick Start

### Local Development

```bash
# Install dependencies
uv sync

# Run the application
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Health check
curl http://localhost:8000/api/v1/health
```

### Docker Deployment

```bash
# Build image
docker build -t lead-scoring-api .

# Run container
docker run -p 8000:8000 lead-scoring-api

# Health check
curl http://localhost:8000/api/v1/health
```

### ECS Fargate Deployment

The application is optimized for AWS ECS Fargate deployment:

- **Container Port**: 8000
- **Health Check**: `/api/v1/health`
- **Resource Requirements**: 512 CPU, 1024 Memory (minimum)
- **Load Balancer**: Application Load Balancer with health checks
- **Logging**: CloudWatch log driver for structured logs
- **Environment Variables**: Configure via ECS task definition

## API Usage

### Score Leads Endpoint

```bash
POST /api/v1/scoring/score
```

**Request Example:**

```json
{
  "request_id": "uuid-string",
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
      "existing_customer": false
    }
  ]
}
```

## Monitoring & Observability

### Health Checks
- **Liveness**: `GET /api/v1/health/live`
- **Readiness**: `GET /api/v1/health/ready`
- **Health**: `GET /api/v1/health`

### Logging
- **Structured Logging**: JSON-formatted logs with request IDs and metadata
- **CloudWatch Integration**: Ready for AWS CloudWatch log aggregation

## CI/CD Pipeline

The project includes a comprehensive GitHub Actions workflow for:
1. **Testing**: Unit tests, integration tests, coverage
2. **Security**: Bandit, Trivy vulnerability scanning  
3. **Quality**: Linting, formatting, type checking
4. **Build**: Multi-platform Docker images
5. **Deploy**: Automated staging/production deployment
