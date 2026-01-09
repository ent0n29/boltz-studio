"""Tests for API routes."""

import pytest


class TestPredictionRoutes:
    """Tests for prediction API endpoints."""

    def test_predict_endpoint(self, client):
        """Test POST /api/predict creates a job."""
        response = client.post(
            "/api/predict",
            json={
                "sequences": [{"sequence": "MKLAVLKAGIAQGEVLVN"}],
                "name": "test",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        assert len(data["job_id"]) == 8  # UUID first 8 chars

    def test_predict_with_custom_params(self, client):
        """Test prediction with custom parameters."""
        response = client.post(
            "/api/predict",
            json={
                "sequences": [{"id": "A", "sequence": "MKLAVLK", "type": "protein"}],
                "name": "custom_test",
                "recycling_steps": 2,
                "sampling_steps": 100,
                "diffusion_samples": 1,
            },
        )

        assert response.status_code == 200

    def test_predict_validation_error(self, client):
        """Test prediction with invalid sequence."""
        response = client.post(
            "/api/predict",
            json={
                "sequences": [{"sequence": "INVALID123"}],  # Numbers not allowed
                "name": "test",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_predict_empty_sequences(self, client):
        """Test prediction with empty sequences list."""
        response = client.post(
            "/api/predict",
            json={
                "sequences": [],
                "name": "test",
            },
        )

        assert response.status_code == 422

    def test_predict_sequence_too_short(self, client):
        """Test prediction with sequence too short."""
        response = client.post(
            "/api/predict",
            json={
                "sequences": [{"sequence": "MKL"}],  # Less than 5
                "name": "test",
            },
        )

        assert response.status_code == 422

    def test_get_job_not_found(self, client):
        """Test GET /api/job/{id} with nonexistent job."""
        response = client.get("/api/job/nonexistent")

        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"

    def test_get_job_after_create(self, client):
        """Test GET /api/job/{id} after creating job."""
        # Create job
        create_response = client.post(
            "/api/predict",
            json={
                "sequences": [{"sequence": "MKLAVLK"}],
                "name": "test",
            },
        )
        job_id = create_response.json()["job_id"]

        # Get job
        get_response = client.get(f"/api/job/{job_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        # Job may be queued, running, or failed (if Boltz not installed)
        assert data["status"] in ["queued", "running", "failed", "completed"]
        assert "progress" in data


class TestDesignRoutes:
    """Tests for design API endpoints."""

    def test_random_mutate(self, client):
        """Test POST /api/random-mutate."""
        response = client.post(
            "/api/random-mutate",
            params={"sequence": "MKLAVLKAGIAQGEVLVN", "num_mutations": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert "mutated_sequence" in data
        assert "mutations" in data
        assert len(data["mutations"]) == 1
        assert len(data["mutated_sequence"]) == 18

    def test_random_mutate_multiple(self, client):
        """Test random mutate with multiple mutations."""
        response = client.post(
            "/api/random-mutate",
            params={"sequence": "MKLAVLKAGIAQGEVLVN", "num_mutations": 3},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["mutations"]) == 3

    def test_random_mutate_sequence_too_short(self, client):
        """Test random mutate with sequence too short."""
        response = client.post(
            "/api/random-mutate",
            params={"sequence": "MKL", "num_mutations": 1},
        )

        assert response.status_code == 422

    def test_random_mutate_uppercases(self, client):
        """Test that random mutate handles lowercase."""
        response = client.post(
            "/api/random-mutate",
            params={"sequence": "mklavlk", "num_mutations": 1},
        )

        assert response.status_code == 200
        data = response.json()
        # Result should be uppercase
        assert data["mutated_sequence"] == data["mutated_sequence"].upper()


class TestStaticRoutes:
    """Tests for static file serving."""

    def test_root_serves_html(self, client):
        """Test that root serves index.html."""
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Boltz Studio" in response.text

    def test_static_css(self, client):
        """Test that CSS is served."""
        response = client.get("/static/css/style.css")

        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_static_js(self, client):
        """Test that JS is served."""
        response = client.get("/static/js/app.js")

        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]


class TestRateLimitingIntegration:
    """Tests for rate limiting integration."""

    def test_rate_limit_applies_to_predict(self, client):
        """Test that rate limiting applies to predict endpoint."""
        # Reset the rate limiter for this test
        from boltz_studio.middleware import rate_limit
        rate_limit._limiter = None  # Reset singleton

        # Make requests up to the limit
        for i in range(10):  # Default limit is 10
            response = client.post(
                "/api/predict",
                json={
                    "sequences": [{"sequence": "MKLAVLK"}],
                    "name": f"ratelimit_test{i}",
                },
            )
            assert response.status_code == 200, f"Request {i} failed: {response.json()}"

        # Next request should be rate limited
        response = client.post(
            "/api/predict",
            json={
                "sequences": [{"sequence": "MKLAVLK"}],
                "name": "test_over_limit",
            },
        )
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]
