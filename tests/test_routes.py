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
        response = client.get("/css/style.css")

        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_static_js(self, client):
        """Test that JS is served."""
        response = client.get("/js/app.js")

        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]


class TestWebSocketRoutes:
    """Tests for WebSocket endpoints."""

    def test_websocket_job_not_found(self, client):
        """Test WebSocket connection to nonexistent job."""
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/job/nonexistent"):
                pass

    def test_websocket_connects_to_valid_job(self, client):
        """Test WebSocket connection to existing job."""
        # Reset rate limiter to avoid conflicts from previous tests
        from boltz_studio.middleware import rate_limit
        rate_limit._limiter = None

        # Create a job first
        create_response = client.post(
            "/api/predict",
            json={
                "sequences": [{"sequence": "MKLAVLK"}],
                "name": "ws_test",
            },
        )
        assert create_response.status_code == 200
        job_id = create_response.json()["job_id"]

        # Connect via WebSocket
        with client.websocket_connect(f"/ws/job/{job_id}") as websocket:
            # Should receive initial state
            data = websocket.receive_json()
            assert "status" in data
            assert "progress" in data

    def test_websocket_receives_job_state(self, client):
        """Test that WebSocket sends current job state on connect."""
        # Reset rate limiter to avoid conflicts from previous tests
        from boltz_studio.middleware import rate_limit
        rate_limit._limiter = None

        # Create job
        create_response = client.post(
            "/api/predict",
            json={
                "sequences": [{"sequence": "MKLAVLK"}],
                "name": "ws_state_test",
            },
        )
        assert create_response.status_code == 200
        job_id = create_response.json()["job_id"]

        with client.websocket_connect(f"/ws/job/{job_id}") as websocket:
            data = websocket.receive_json()
            # Should have all job fields
            assert data["status"] in ["queued", "running", "completed", "failed"]
            assert isinstance(data["progress"], (int, float))


class TestPDBRoutes:
    """Tests for PDB database API endpoints."""

    def test_pdb_id_validation_too_short(self, client):
        """Test PDB ID must be 4 characters."""
        response = client.get("/api/pdb/1AK")
        assert response.status_code == 400
        assert "4 characters" in response.json()["detail"]

    def test_pdb_id_validation_too_long(self, client):
        """Test PDB ID must be 4 characters."""
        response = client.get("/api/pdb/1AKEE")
        assert response.status_code == 400
        assert "4 characters" in response.json()["detail"]

    def test_pdb_structure_id_validation(self, client):
        """Test PDB structure endpoint validates ID length."""
        response = client.get("/api/pdb/1A/structure")
        assert response.status_code == 400
        assert "4 characters" in response.json()["detail"]

    def test_pdb_id_uppercase(self, client, monkeypatch):
        """Test PDB ID is uppercased."""
        from unittest.mock import AsyncMock, MagicMock

        # Mock httpx to avoid real API calls
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "struct": {"title": "Test Protein"},
            "rcsb_entry_info": {"resolution_combined": [2.0]},
            "exptl": [{"method": "X-RAY DIFFRACTION"}],
            "rcsb_accession_info": {"initial_release_date": "2020-01-01"},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: mock_client)

        response = client.get("/api/pdb/1ake")
        assert response.status_code == 200
        data = response.json()
        assert data["pdb_id"] == "1AKE"  # Should be uppercased

    def test_pdb_not_found(self, client, monkeypatch):
        """Test handling of nonexistent PDB entry."""
        from unittest.mock import AsyncMock, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: mock_client)

        response = client.get("/api/pdb/XXXX")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_pdb_search_returns_results(self, client, monkeypatch):
        """Test PDB search endpoint."""
        from unittest.mock import AsyncMock, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_count": 100,
            "result_set": [
                {"identifier": "1AKE", "score": 0.95},
                {"identifier": "2AKE", "score": 0.90},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: mock_client)

        response = client.get("/api/pdb/search/insulin")
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "insulin"
        assert "results" in data
        assert len(data["results"]) == 2
