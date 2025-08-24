"""
Load testing script for Lead Scoring API
Generates realistic dummy data and tests API performance under load
"""

import asyncio
import os
import random
import time
from datetime import datetime, timedelta
from typing import Any

import aiohttp
import pytest


class LoadTestData:
    """Generator for realistic lead scoring test data"""

    COMPANY_SIZES = ["Startup", "Small", "Medium", "Large", "Enterprise"]
    INDUSTRIES = [
        "Technology",
        "Healthcare",
        "Finance",
        "Manufacturing",
        "Retail",
        "Education",
        "Energy",
        "Real Estate",
        "Media",
        "Transportation",
    ]
    JOB_TITLES = [
        "CEO",
        "CTO",
        "VP Marketing",
        "VP Sales",
        "Director Marketing",
        "Marketing Manager",
        "Sales Manager",
        "Product Manager",
        "Engineer",
        "Analyst",
        "Coordinator",
        "Specialist",
        "Executive",
        "Consultant",
    ]
    SENIORITY_LEVELS = ["Entry", "Mid", "Senior", "Executive", "C-Level"]
    GEOGRAPHIES = [
        "North America",
        "Europe",
        "Asia Pacific",
        "Latin America",
        "Middle East",
        "Africa",
        "Australia",
    ]

    @classmethod
    def generate_lead(cls) -> dict[str, Any]:
        """Generate a single realistic lead"""
        # Generate engagement scores that correlate with business value
        base_engagement = random.uniform(0.1, 0.9)

        # Higher seniority tends to have higher engagement
        seniority = random.choice(cls.SENIORITY_LEVELS)
        engagement_boost = {
            "Entry": 0.0,
            "Mid": 0.1,
            "Senior": 0.2,
            "Executive": 0.3,
            "C-Level": 0.4,
        }.get(seniority, 0.0)

        email_engagement = min(
            0.95, base_engagement + engagement_boost + random.uniform(-0.1, 0.1)
        )

        # Generate correlated website activity
        website_sessions = max(1, int(email_engagement * 20 + random.uniform(-5, 10)))
        pages_viewed = max(1, int(website_sessions * random.uniform(2, 8)))
        time_on_site = max(1.0, website_sessions * random.uniform(1.5, 5.0))

        # Generate form activity
        form_fills = max(0, int(email_engagement * 5 + random.uniform(-2, 3)))
        content_downloads = max(0, int(email_engagement * 8 + random.uniform(-3, 5)))
        campaign_touchpoints = max(
            1, int(email_engagement * 12 + random.uniform(-4, 8))
        )

        # Generate account data based on company size
        company_size = random.choice(cls.COMPANY_SIZES)
        revenue_ranges = {
            "Startup": (100000, 1000000),
            "Small": (1000000, 10000000),
            "Medium": (10000000, 100000000),
            "Large": (100000000, 1000000000),
            "Enterprise": (1000000000, 10000000000),
        }
        revenue_range = revenue_ranges.get(company_size, (1000000, 10000000))
        account_revenue = random.uniform(*revenue_range)

        employee_ranges = {
            "Startup": (1, 50),
            "Small": (51, 200),
            "Medium": (201, 1000),
            "Large": (1001, 5000),
            "Enterprise": (5001, 50000),
        }
        employee_range = employee_ranges.get(company_size, (51, 200))
        account_employees = random.randint(*employee_range)

        # Generate custom features
        custom_features = {}
        for i in range(1, 35):
            if random.random() < 0.3:  # 30% chance to have custom feature
                custom_features[f"custom_feature_{i}"] = random.uniform(0.0, 100.0)

        # Generate realistic interaction date
        days_ago = random.randint(0, 365)
        last_interaction = datetime.now() - timedelta(days=days_ago)

        return {
            "company_size": company_size,
            "industry": random.choice(cls.INDUSTRIES),
            "job_title": random.choice(cls.JOB_TITLES),
            "seniority_level": seniority,
            "geography": random.choice(cls.GEOGRAPHIES),
            "email_engagement_score": round(email_engagement, 3),
            "website_sessions": website_sessions,
            "pages_viewed": pages_viewed,
            "time_on_site": round(time_on_site, 2),
            "form_fills": form_fills,
            "content_downloads": content_downloads,
            "campaign_touchpoints": campaign_touchpoints,
            "account_revenue": int(account_revenue),
            "account_employees": account_employees,
            "existing_customer": random.choice([True, False]),
            "last_campaign_interaction": last_interaction.isoformat(),
            "custom_features": custom_features if custom_features else None,
        }

    @classmethod
    def generate_batch(cls, batch_size: int) -> list[dict[str, Any]]:
        """Generate a batch of leads"""
        return [cls.generate_lead() for _ in range(batch_size)]


class LoadTester:
    """Async load tester for the scoring API"""

    def __init__(self, base_url: str = None):
        # Environment-based URL configuration
        if base_url is None:
            # Check for external ENV override first (for CI/CD)
            external_env = os.environ.get("LOAD_TEST_ENV") or os.environ.get("ENV")
            if external_env and external_env != "test":
                env = external_env.lower()
            else:
                env = "debug"  # fallback for local/debug environments

            if env == "prod":
                base_url = (
                    "https://alb-lead-scoring-1394767465.eu-west-1.elb.amazonaws.com"
                )
            elif env == "dev":
                base_url = (
                    "https://alb-lead-scoring-dev-263460192.eu-west-1.elb.amazonaws.com"
                )
            else:
                base_url = "http://localhost:8000"  # fallback for local testing

        self.base_url = base_url
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def score_leads(
        self, leads: list[dict[str, Any]], request_id: str
    ) -> dict[str, Any]:
        """Score a batch of leads"""
        if not self.session:
            raise RuntimeError("LoadTester not initialized with async context manager")

        payload = {"request_id": request_id, "leads": leads}

        start_time = time.time()
        async with self.session.post(
            f"{self.base_url}/api/v1/scoring/score",
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as response:
            response_data = await response.json()
            end_time = time.time()

            return {
                "status_code": response.status,
                "response_time_ms": (end_time - start_time) * 1000,
                "response_data": response_data,
                "batch_size": len(leads),
            }

    async def concurrent_load_test(
        self, total_requests: int, concurrent_requests: int, batch_size: int = 10
    ) -> dict[str, Any]:
        """Run concurrent load test"""
        print(
            f"Starting load test: {total_requests} requests, {concurrent_requests} concurrent, batch size {batch_size}"
        )

        start_time = time.time()
        semaphore = asyncio.Semaphore(concurrent_requests)

        async def single_request(request_num: int) -> dict[str, Any]:
            async with semaphore:
                leads = LoadTestData.generate_batch(batch_size)
                request_id = f"load-test-{request_num}-{int(time.time())}"
                return await self.score_leads(leads, request_id)

        # Execute all requests
        tasks = [single_request(i) for i in range(total_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time

        # Analyze results
        successful_requests = [
            r for r in results if isinstance(r, dict) and r.get("status_code") == 200
        ]
        failed_requests = [
            r for r in results if not isinstance(r, dict) or r.get("status_code") != 200
        ]

        response_times = [r["response_time_ms"] for r in successful_requests]

        stats = {
            "total_requests": total_requests,
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "success_rate": len(successful_requests) / total_requests * 100,
            "total_time_seconds": total_time,
            "requests_per_second": total_requests / total_time,
            "total_leads_processed": sum(r["batch_size"] for r in successful_requests),
            "leads_per_second": sum(r["batch_size"] for r in successful_requests)
            / total_time,
        }

        if response_times:
            response_times.sort()
            stats.update(
                {
                    "avg_response_time_ms": sum(response_times) / len(response_times),
                    "min_response_time_ms": min(response_times),
                    "max_response_time_ms": max(response_times),
                    "p50_response_time_ms": response_times[len(response_times) // 2],
                    "p95_response_time_ms": response_times[
                        int(len(response_times) * 0.95)
                    ],
                    "p99_response_time_ms": response_times[
                        int(len(response_times) * 0.99)
                    ],
                }
            )

        return stats


# Test functions for pytest


@pytest.mark.asyncio
async def test_single_request_load():
    """Test single request performance"""
    async with LoadTester() as tester:
        leads = LoadTestData.generate_batch(1)
        result = await tester.score_leads(leads, "single-load-test")

        assert result["status_code"] == 200
        assert result["response_time_ms"] < 1000  # Should be under 1 second
        assert result["response_data"]["total_leads"] == 1
        assert 1 <= result["response_data"]["scores"][0]["score"] <= 5


@pytest.mark.asyncio
async def test_batch_request_load():
    """Test batch request performance"""
    async with LoadTester() as tester:
        batch_sizes = [5, 10, 25, 50]

        for batch_size in batch_sizes:
            leads = LoadTestData.generate_batch(batch_size)
            result = await tester.score_leads(leads, f"batch-load-test-{batch_size}")

            assert result["status_code"] == 200
            assert result["response_time_ms"] < 5000  # Should be under 5 seconds
            assert result["response_data"]["total_leads"] == batch_size
            assert len(result["response_data"]["scores"]) == batch_size


@pytest.mark.asyncio
async def test_concurrent_load():
    """Test concurrent request handling"""
    async with LoadTester() as tester:
        stats = await tester.concurrent_load_test(
            total_requests=20, concurrent_requests=5, batch_size=10
        )

        print("\nLoad Test Results:")
        print(f"   Total Requests: {stats['total_requests']}")
        print(f"   Success Rate: {stats['success_rate']:.1f}%")
        print(f"   Requests/sec: {stats['requests_per_second']:.1f}")
        print(f"   Leads/sec: {stats['leads_per_second']:.1f}")
        print(f"   Avg Response Time: {stats.get('avg_response_time_ms', 0):.1f}ms")
        print(f"   P95 Response Time: {stats.get('p95_response_time_ms', 0):.1f}ms")

        # Assertions for performance benchmarks
        assert stats["success_rate"] >= 95.0  # 95% success rate
        assert stats["requests_per_second"] >= 2.0  # At least 2 RPS
        assert stats.get("avg_response_time_ms", 0) < 2000  # Avg under 2 seconds
        assert stats.get("p95_response_time_ms", 0) < 5000  # P95 under 5 seconds


@pytest.mark.asyncio
async def test_stress_load():
    """Stress test with high concurrency"""
    async with LoadTester() as tester:
        stats = await tester.concurrent_load_test(
            total_requests=50, concurrent_requests=10, batch_size=20
        )

        print("\nStress Test Results:")
        print(f"   Total Requests: {stats['total_requests']}")
        print(f"   Success Rate: {stats['success_rate']:.1f}%")
        print(f"   Total Leads Processed: {stats['total_leads_processed']}")
        print(f"   Requests/sec: {stats['requests_per_second']:.1f}")
        print(f"   Leads/sec: {stats['leads_per_second']:.1f}")
        print(f"   Avg Response Time: {stats.get('avg_response_time_ms', 0):.1f}ms")
        print(f"   P99 Response Time: {stats.get('p99_response_time_ms', 0):.1f}ms")

        # Stress test assertions (more lenient)
        assert stats["success_rate"] >= 90.0  # 90% success rate under stress
        assert stats["total_leads_processed"] >= 800  # Should process most leads
        assert stats.get("avg_response_time_ms", 0) < 10000  # Avg under 10 seconds


@pytest.mark.asyncio
async def test_max_batch_size():
    """Test maximum allowed batch size"""
    async with LoadTester() as tester:
        # Test just under the limit
        leads = LoadTestData.generate_batch(500)
        result = await tester.score_leads(leads, "max-batch-test")

        assert result["status_code"] == 200
        assert result["response_data"]["total_leads"] == 500

        # Test over the limit (should fail)
        large_leads = LoadTestData.generate_batch(501)
        result = await tester.score_leads(large_leads, "over-limit-test")

        assert result["status_code"] == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_data_variety():
    """Test with diverse data patterns"""
    async with LoadTester() as tester:
        test_cases = [
            # Minimal data
            [{"email_engagement_score": 0.1, "existing_customer": False}],
            # Rich data
            [
                {
                    "company_size": "Enterprise",
                    "industry": "Technology",
                    "job_title": "CEO",
                    "seniority_level": "C-Level",
                    "geography": "North America",
                    "email_engagement_score": 0.95,
                    "website_sessions": 25,
                    "pages_viewed": 100,
                    "time_on_site": 45.5,
                    "form_fills": 8,
                    "content_downloads": 12,
                    "campaign_touchpoints": 15,
                    "account_revenue": 5000000000,
                    "account_employees": 10000,
                    "existing_customer": True,
                    "last_campaign_interaction": (
                        datetime.now() - timedelta(days=1)
                    ).isoformat(),
                    "custom_features": {
                        f"custom_feature_{i}": random.uniform(0, 100)
                        for i in range(1, 35)
                    },
                }
            ],
            # Mixed batch
            LoadTestData.generate_batch(15),
        ]

        for i, leads in enumerate(test_cases):
            result = await tester.score_leads(leads, f"variety-test-{i}")

            assert result["status_code"] == 200
            assert result["response_data"]["total_leads"] == len(leads)

            # Verify all scores are in valid range
            scores = result["response_data"]["scores"]
            for score in scores:
                assert 1 <= score["score"] <= 5
                assert 0 <= score["confidence"] <= 1
                assert score["features_used"] == 50


if __name__ == "__main__":
    """Run load test directly"""

    async def run_load_test():
        env = os.getenv("ENV", "debug")
        print("Starting Lead Scoring API Load Test")
        print("=" * 50)
        print(f"Environment: {env.upper()}")

        async with LoadTester() as tester:
            print(f"Testing URL: {tester.base_url}")
            # Quick performance test
            print("\nQuick Performance Test (5 requests, 2 concurrent)")
            quick_stats = await tester.concurrent_load_test(
                total_requests=5, concurrent_requests=2, batch_size=5
            )

            print(f"   Success Rate: {quick_stats['success_rate']:.1f}%")
            print(
                f"   Avg Response Time: {quick_stats.get('avg_response_time_ms', 0):.1f}ms"
            )
            print(f"   Leads/sec: {quick_stats['leads_per_second']:.1f}")

            # Extended load test
            print("\nExtended Load Test (30 requests, 5 concurrent)")
            load_stats = await tester.concurrent_load_test(
                total_requests=30, concurrent_requests=5, batch_size=15
            )

            print(f"   Success Rate: {load_stats['success_rate']:.1f}%")
            print(f"   Total Leads: {load_stats['total_leads_processed']}")
            print(f"   Requests/sec: {load_stats['requests_per_second']:.1f}")
            print(f"   Leads/sec: {load_stats['leads_per_second']:.1f}")
            print(f"   Avg Response: {load_stats.get('avg_response_time_ms', 0):.1f}ms")
            print(f"   P95 Response: {load_stats.get('p95_response_time_ms', 0):.1f}ms")
            print(f"   P99 Response: {load_stats.get('p99_response_time_ms', 0):.1f}ms")

        print("\nLoad test completed!")

    # Run the load test
    asyncio.run(run_load_test())
