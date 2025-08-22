# GitHub Actions Setup Guide

This guide explains how to set up the CI/CD pipeline for the Lead Scoring API.

## Required GitHub Secrets

Add the following secrets to your GitHub repository:

### AWS Configuration
```bash
# AWS Account ID (12-digit number)
AWS_ACCOUNT_ID=123456789012

# IAM Role ARN for GitHub Actions OIDC
AWS_ROLE_ARN=arn:aws:iam::123456789012:role/GitHubActionsRole
```

### Optional Integrations
```bash
# Codecov token for coverage reporting
CODECOV_TOKEN=your-codecov-token

# Slack webhook for notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## AWS IAM Role Setup

Create an IAM role with the following trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:your-org/lead-scoring-model:*"
        }
      }
    }
  ]
}
```

Attach the following policies to the role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage",
        "ecr:CreateRepository",
        "ecr:DescribeRepositories",
        "ecr:StartImageScan",
        "ecr:DescribeImageScanFindings"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:DescribeTaskDefinition"
      ],
      "Resource": "*"
    }
  ]
}
```

## Quality Gates Configuration

The pipeline enforces these quality thresholds:

- **Code Coverage**: Minimum 80% (configurable via `MIN_COVERAGE`)
- **Security Issues**: 0 high/critical issues (configurable via `MAX_SECURITY_ISSUES`)
- **Vulnerability Scan**: Max 0 critical, 3 high vulnerabilities in Docker image
- **Linting**: Must pass black and ruff checks
- **Type Checking**: Must pass mypy checks

## Version Management

- **Main branch**: Auto-increments patch version (v1.0.0 → v1.0.1)
- **Feature branches**: Uses branch name + commit SHA (feature-branch-abc123)
- Git tags are automatically created on successful releases

## Pipeline Workflow

1. **Quality Gates** - Run on all branches
   - Linting (black, ruff)
   - Type checking (mypy)  
   - Security scan (bandit)
   - Unit tests with coverage
   - Version generation

2. **Vulnerability Scan** - Parallel file system scan
   - Trivy security scanning
   - Results uploaded to GitHub Security tab

3. **Build & Push** - Only on main branch after quality gates pass
   - Docker build for linux/amd64 platform
   - Push to AWS ECR with version tagging
   - Image vulnerability scanning
   - SBOM generation
   - Git tag creation

4. **Deploy** - Automatic ECS deployment
   - Update production ECS service
   - Wait for deployment completion

5. **Notify** - Slack notifications
   - Deployment status with coverage metrics
   - Version and commit information

## Customization

Edit `.github/workflows/ci-cd.yml` to customize:

- Quality thresholds (lines 13-14)
- AWS region (line 10) - currently set to eu-west-1
- ECR repository name (line 12)
- ECS cluster/service names (lines 290-292)

## Testing the Pipeline

1. Create a feature branch
2. Make changes and push
3. Create a pull request to main
4. Quality gates will run automatically
5. Merge to main to trigger full deployment pipeline