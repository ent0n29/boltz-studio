"""Tests for SQLite job store."""

import uuid



def unique_id(prefix: str = "test") -> str:
    """Generate a unique job ID for testing."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestJobStore:
    """Tests for JobStore SQLite backend."""

    def test_create_job(self, job_store):
        """Test job creation."""
        job_id = unique_id("create")
        job = job_store.create(job_id)

        assert job["status"] == "queued"
        assert job["progress"] == 0.0
        assert job["result"] is None
        assert job["error"] is None

    def test_get_job(self, job_store):
        """Test job retrieval."""
        job_id = unique_id("get")
        job_store.create(job_id)
        job = job_store.get(job_id)

        assert job is not None
        assert job["status"] == "queued"

    def test_get_nonexistent_job(self, job_store):
        """Test retrieval of nonexistent job."""
        job = job_store.get("nonexistent-xyz123")
        assert job is None

    def test_update_status(self, job_store):
        """Test status update."""
        job_id = unique_id("update")
        job_store.create(job_id)
        job_store.update(job_id, status="running", progress=0.5)

        job = job_store.get(job_id)
        assert job["status"] == "running"
        assert job["progress"] == 0.5

    def test_update_with_result(self, job_store):
        """Test update with JSON result."""
        job_id = unique_id("result")
        job_store.create(job_id)

        result = {
            "structure_pdb": "ATOM 1 ...",
            "confidence": {"plddt": 0.85},
            "plddt_per_residue": [0.9, 0.8, 0.85],
        }
        job_store.update(
            job_id,
            status="completed",
            progress=1.0,
            result=result,
        )

        job = job_store.get(job_id)
        assert job["status"] == "completed"
        assert job["progress"] == 1.0
        assert job["result"] == result
        assert job["result"]["confidence"]["plddt"] == 0.85

    def test_update_with_error(self, job_store):
        """Test update with error."""
        job_id = unique_id("error")
        job_store.create(job_id)
        job_store.update(job_id, status="failed", error="Something went wrong")

        job = job_store.get(job_id)
        assert job["status"] == "failed"
        assert job["error"] == "Something went wrong"

    def test_exists(self, job_store):
        """Test job existence check."""
        job_id = unique_id("exists")
        assert not job_store.exists(job_id)

        job_store.create(job_id)
        assert job_store.exists(job_id)

    def test_delete(self, job_store):
        """Test job deletion."""
        job_id = unique_id("delete")
        job_store.create(job_id)
        assert job_store.exists(job_id)

        result = job_store.delete(job_id)
        assert result is True
        assert not job_store.exists(job_id)

    def test_delete_nonexistent(self, job_store):
        """Test deletion of nonexistent job."""
        result = job_store.delete("nonexistent-abc123")
        assert result is False

    def test_list_jobs(self, job_store):
        """Test listing jobs."""
        # Create multiple jobs with unique prefix
        prefix = unique_id("list")
        job_ids = [f"{prefix}-{i}" for i in range(3)]
        for job_id in job_ids:
            job_store.create(job_id)

        jobs = job_store.list_jobs()
        assert len(jobs) >= 3

        # Check that our jobs are in the list
        all_job_ids = [j["id"] for j in jobs]
        for job_id in job_ids:
            assert job_id in all_job_ids

    def test_list_jobs_by_status(self, job_store):
        """Test listing jobs filtered by status."""
        prefix = unique_id("status")
        job1 = f"{prefix}-queued"
        job2 = f"{prefix}-running"

        job_store.create(job1)
        job_store.create(job2)
        job_store.update(job2, status="running")

        queued_jobs = job_store.list_jobs(status="queued")
        running_jobs = job_store.list_jobs(status="running")

        queued_ids = [j["id"] for j in queued_jobs]
        running_ids = [j["id"] for j in running_jobs]

        assert job1 in queued_ids
        assert job2 in running_ids
        assert job2 not in queued_ids

    def test_list_jobs_limit(self, job_store):
        """Test list jobs with limit."""
        prefix = unique_id("limit")
        for i in range(10):
            job_store.create(f"{prefix}-{i}")

        jobs = job_store.list_jobs(limit=5)
        assert len(jobs) == 5

    def test_cleanup_old_jobs(self, job_store):
        """Test cleanup of old jobs."""
        job_id = unique_id("cleanup")
        job_store.create(job_id)
        assert job_store.exists(job_id)

        # Cleanup with very large hours should not remove recent jobs
        cleaned = job_store.cleanup_old_jobs(hours=24)
        # Recent job should still exist
        assert job_store.exists(job_id)

        # Test that cleanup function works (returns int)
        assert isinstance(cleaned, int)
        assert cleaned >= 0

    def test_multiple_updates(self, job_store):
        """Test multiple sequential updates."""
        job_id = unique_id("multi")
        job_store.create(job_id)

        job_store.update(job_id, progress=0.1)
        job_store.update(job_id, progress=0.3)
        job_store.update(job_id, status="running", progress=0.5)
        job_store.update(job_id, progress=0.9)
        job_store.update(job_id, status="completed", progress=1.0)

        job = job_store.get(job_id)
        assert job["status"] == "completed"
        assert job["progress"] == 1.0
