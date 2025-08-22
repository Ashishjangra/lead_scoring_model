#!/bin/bash
set -e

# Docker build script for Lead Scoring API

IMAGE_NAME="lead-scoring-api"
REGISTRY="ghcr.io"
ORG="your-org"
VERSION=${1:-"latest"}

echo "🐳 Building Docker image for Lead Scoring API"

# Build the image
echo "📦 Building image: ${REGISTRY}/${ORG}/${IMAGE_NAME}:${VERSION}"
docker build \
  -t ${IMAGE_NAME}:${VERSION} \
  -t ${REGISTRY}/${ORG}/${IMAGE_NAME}:${VERSION} \
  .

# Run security scan
echo "🔒 Running security scan..."
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd):/app" \
  aquasec/trivy:latest image --severity HIGH,CRITICAL ${IMAGE_NAME}:${VERSION} || echo "Security scan completed with findings"

# Test the image
echo "🧪 Testing the image..."
docker run --rm -d --name test-api -p 8001:8000 ${IMAGE_NAME}:${VERSION}

# Wait for container to start
sleep 10

# Health check
echo "🏥 Running health check..."
curl -f http://localhost:8001/api/v1/health/live || (echo "Health check failed" && exit 1)

# Clean up test container
docker stop test-api || true

echo "✅ Build completed successfully!"
echo "🚀 Image ready: ${REGISTRY}/${ORG}/${IMAGE_NAME}:${VERSION}"