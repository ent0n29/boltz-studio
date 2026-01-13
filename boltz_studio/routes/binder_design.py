"""API routes for binder design (BoltzGen integration)."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import asyncio
import json

from ..middleware import RequiredUser
from ..models.binder_design import (
    DesignJobCreate,
    DesignJobDetail,
    DesignJobList,
    DesignJobPublic,
    DesignProgress,
    DesignResultDetail,
    DesignResultList,
    DesignResultPublic,
    DesignTargetDetail,
    DesignTargetList,
    DesignTargetPublic,
    SynthesisOrderCreate,
    SynthesisOrderPublic,
    SynthesisStatus,
    TargetCategory,
)
from ..services.boltzgen_runner import get_boltzgen_runner
from ..services.database import get_connection
from ..logger import get_logger

router = APIRouter(prefix="/api/design", tags=["binder-design"])
logger = get_logger("routes.design")


# === Target Endpoints ===


@router.get("/targets", response_model=DesignTargetList)
async def list_targets(
    category: TargetCategory | None = None,
    search: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List available design targets.

    Returns curated therapeutic targets that users can design binders for.
    """
    with get_connection() as conn:
        # Build query
        conditions = []
        params = []

        if category:
            conditions.append("category = ?")
            params.append(category)

        if search:
            conditions.append("(name LIKE ? OR description LIKE ? OR pdb_id LIKE ?)")
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Get total count
        total = conn.execute(
            f"SELECT COUNT(*) FROM design_targets {where_clause}",
            params
        ).fetchone()[0]

        # Get targets
        rows = conn.execute(
            f"""
            SELECT id, slug, name, description, category, subcategory,
                   pdb_id, uniprot_id, organism, therapeutic_area, difficulty,
                   is_curated, design_count, successful_designs, created_at
            FROM design_targets
            {where_clause}
            ORDER BY is_curated DESC, design_count DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset]
        ).fetchall()

        targets = [DesignTargetPublic(**dict(row)) for row in rows]

        # Get category counts
        category_rows = conn.execute(
            "SELECT category, COUNT(*) as count FROM design_targets GROUP BY category"
        ).fetchall()
        categories = {row["category"]: row["count"] for row in category_rows}

        return DesignTargetList(targets=targets, total=total, categories=categories)


@router.get("/targets/{target_id}", response_model=DesignTargetDetail)
async def get_target(target_id: str):
    """Get detailed target information including structure."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM design_targets WHERE id = ? OR slug = ?
            """,
            (target_id, target_id)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Target not found")

        return DesignTargetDetail(**dict(row))


# === Job Endpoints ===


@router.post("/jobs", response_model=DesignJobPublic)
async def submit_design_job(
    job_data: DesignJobCreate,
    user: RequiredUser,
):
    """Submit a new binder design job.

    Starts a BoltzGen design pipeline to generate binders for the specified target.
    """
    runner = get_boltzgen_runner()

    try:
        job_id = await runner.submit_job(user.id, job_data)
        job = runner.get_job(job_id)

        if not job:
            raise HTTPException(status_code=500, detail="Failed to create job")

        return DesignJobPublic(**job)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to submit design job: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit job")


@router.get("/jobs", response_model=DesignJobList)
async def list_user_jobs(
    user: RequiredUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List current user's design jobs."""
    runner = get_boltzgen_runner()
    jobs = runner.get_user_jobs(user.id, offset, limit)

    # Get total count
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM design_jobs WHERE user_id = ?",
            (user.id,)
        ).fetchone()[0]

    return DesignJobList(
        jobs=[DesignJobPublic(**j) for j in jobs],
        total=total
    )


@router.get("/jobs/{job_id}", response_model=DesignJobDetail)
async def get_job(
    job_id: str,
    user: RequiredUser,
):
    """Get design job details."""
    runner = get_boltzgen_runner()
    job = runner.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check ownership
    if job["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return DesignJobDetail(**job)


@router.get("/jobs/{job_id}/progress")
async def stream_job_progress(
    job_id: str,
    user: RequiredUser,
):
    """Stream real-time job progress updates via SSE."""
    runner = get_boltzgen_runner()
    job = runner.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    async def event_generator():
        queue: asyncio.Queue[DesignProgress] = asyncio.Queue()

        async def progress_callback(progress: DesignProgress):
            await queue.put(progress)

        # Register callback
        runner.register_progress_callback(job_id, progress_callback)

        try:
            # Send initial state
            current_job = runner.get_job(job_id)
            if current_job:
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "job_id": job_id,
                        "status": current_job["status"],
                        "progress": current_job["progress"],
                        "current_step": current_job.get("current_step"),
                    })
                }

            # Stream updates
            while True:
                try:
                    progress = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {
                        "event": "progress",
                        "data": progress.model_dump_json()
                    }

                    # Stop if job is done
                    if progress.status in ("completed", "failed", "cancelled"):
                        break

                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield {"event": "heartbeat", "data": ""}

                    # Check if job still exists and is running
                    current_job = runner.get_job(job_id)
                    if not current_job or current_job["status"] in ("completed", "failed", "cancelled"):
                        break

        finally:
            runner.unregister_progress_callback(job_id, progress_callback)

    return EventSourceResponse(event_generator())


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    user: RequiredUser,
):
    """Cancel a running design job."""
    runner = get_boltzgen_runner()
    job = runner.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if job["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail="Job is not running")

    cancelled = await runner.cancel_job(job_id)

    if not cancelled:
        raise HTTPException(status_code=400, detail="Could not cancel job")

    return {"status": "cancelled"}


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    user: RequiredUser,
    force: bool = Query(False, description="Force delete even if job appears to be running"),
):
    """Delete a design job and its results."""
    runner = get_boltzgen_runner()
    job = runner.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Don't allow deleting running jobs (must cancel first) - unless force=true
    if not force:
        running_statuses = ["queued", "generating", "folding", "analyzing", "filtering", "downloading_models"]
        if job["status"] in running_statuses:
            raise HTTPException(status_code=400, detail="Cannot delete a running job. Cancel it first, or use force delete.")

    deleted = runner.delete_job(job_id)

    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete job")

    return {"status": "deleted"}


# === Result Endpoints ===


@router.get("/jobs/{job_id}/results", response_model=DesignResultList)
async def get_job_results(
    job_id: str,
    user: RequiredUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Get results from a completed design job."""
    runner = get_boltzgen_runner()
    job = runner.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    results = runner.get_job_results(job_id, offset, limit)

    # Get total count
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM design_results WHERE job_id = ?",
            (job_id,)
        ).fetchone()[0]

    return DesignResultList(
        results=[DesignResultPublic(**r) for r in results],
        total=total,
        job_id=job_id
    )


@router.get("/results/{result_id}", response_model=DesignResultDetail)
async def get_result(
    result_id: str,
    user: RequiredUser,
):
    """Get detailed result including structure."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT r.*, j.user_id
            FROM design_results r
            JOIN design_jobs j ON r.job_id = j.id
            WHERE r.id = ?
            """,
            (result_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Result not found")

        if row["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

        return DesignResultDetail(**dict(row))


@router.get("/results/{result_id}/pdb")
async def download_result_pdb(
    result_id: str,
    user: RequiredUser,
):
    """Download result structure as PDB file."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT r.structure_pdb, r.rank, j.user_id, j.name
            FROM design_results r
            JOIN design_jobs j ON r.job_id = j.id
            WHERE r.id = ?
            """,
            (result_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Result not found")

        if row["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

        if not row["structure_pdb"]:
            raise HTTPException(status_code=404, detail="Structure not available")

        filename = f"{row['name']}_rank{row['rank']}.pdb"

        return StreamingResponse(
            iter([row["structure_pdb"]]),
            media_type="chemical/x-pdb",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@router.post("/results/{result_id}/publish")
async def publish_result(
    result_id: str,
    user: RequiredUser,
):
    """Publish a design result to the community.

    Creates a public design from the result that can be starred, forked, etc.
    """
    with get_connection() as conn:
        # Get result and verify ownership
        row = conn.execute(
            """
            SELECT r.*, j.user_id, j.name as job_name, j.target_id, t.name as target_name
            FROM design_results r
            JOIN design_jobs j ON r.job_id = j.id
            LEFT JOIN design_targets t ON j.target_id = t.id
            WHERE r.id = ?
            """,
            (result_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Result not found")

        if row["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

        if row["is_published"]:
            raise HTTPException(status_code=400, detail="Already published")

        # Create design
        import uuid
        design_id = str(uuid.uuid4())

        target_info = f" for {row['target_name']}" if row["target_name"] else ""
        name = f"{row['job_name']} - Rank {row['rank']}"
        description = f"Binder design{target_info} generated by BoltzGen. pLDDT: {row['plddt_score']:.1f}" if row["plddt_score"] else f"Binder design{target_info} generated by BoltzGen."

        conn.execute(
            """
            INSERT INTO designs (id, user_id, name, description, sequence, structure_pdb, is_public)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (design_id, user.id, name, description, row["sequence"], row["structure_pdb"])
        )

        # Mark result as published
        conn.execute(
            "UPDATE design_results SET is_published = 1, design_id = ? WHERE id = ?",
            (design_id, result_id)
        )

        # Update target design count
        if row["target_id"]:
            conn.execute(
                "UPDATE design_targets SET design_count = design_count + 1 WHERE id = ?",
                (row["target_id"],)
            )

        logger.info(f"Published design result {result_id} as design {design_id}")

        return {"design_id": design_id, "message": "Design published successfully"}


# === Synthesis Order Endpoints ===


@router.post("/results/{result_id}/order", response_model=SynthesisOrderPublic)
async def create_synthesis_order(
    result_id: str,
    order_data: SynthesisOrderCreate,
    user: RequiredUser,
):
    """Create a synthesis order for a design result.

    Allows users to order DNA/plasmid/protein synthesis from providers like Twist, IDT, or GenScript.
    """
    import uuid
    from datetime import datetime

    with get_connection() as conn:
        # Verify result exists and user owns it
        row = conn.execute(
            """
            SELECT r.*, j.user_id
            FROM design_results r
            JOIN design_jobs j ON r.job_id = j.id
            WHERE r.id = ?
            """,
            (result_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Result not found")

        if row["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

        # Estimate cost based on provider and order type
        cost_estimates = {
            ("twist", "dna"): 0.09,  # per bp
            ("twist", "plasmid"): 199.0,  # flat + per bp
            ("twist", "protein"): 8.0,  # per aa
            ("idt", "dna"): 0.10,
            ("idt", "plasmid"): 249.0,
            ("idt", "protein"): 10.0,
            ("genscript", "dna"): 0.08,
            ("genscript", "plasmid"): 189.0,
            ("genscript", "protein"): 7.0,
        }

        sequence = row["sequence"] or ""
        seq_len = len(sequence)
        base_cost = cost_estimates.get((order_data.provider, order_data.order_type), 100.0)

        if order_data.order_type == "dna":
            estimated_cost = base_cost * seq_len * 3  # Convert aa to bp
        elif order_data.order_type == "plasmid":
            estimated_cost = base_cost + (0.05 * seq_len * 3)
        else:  # protein
            estimated_cost = base_cost * seq_len

        # Create order
        order_id = str(uuid.uuid4())
        now = datetime.utcnow()

        conn.execute(
            """
            INSERT INTO synthesis_orders (
                id, user_id, design_result_id, provider, order_type, status,
                codon_optimized_for, quantity, notes, estimated_cost, created_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
            """,
            (
                order_id, user.id, result_id, order_data.provider,
                order_data.order_type, order_data.codon_optimized_for,
                order_data.quantity, order_data.notes, estimated_cost, now
            )
        )

        logger.info(f"Created synthesis order {order_id} for result {result_id}")

        return SynthesisOrderPublic(
            id=order_id,
            design_result_id=result_id,
            provider=order_data.provider,
            order_type=order_data.order_type,
            status="pending",
            estimated_cost=estimated_cost,
            created_at=now,
        )


@router.get("/orders", response_model=list[SynthesisOrderPublic])
async def list_synthesis_orders(
    user: RequiredUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List user's synthesis orders."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM synthesis_orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user.id, limit, offset)
        ).fetchall()

        return [SynthesisOrderPublic(**dict(row)) for row in rows]


@router.get("/orders/{order_id}", response_model=SynthesisOrderPublic)
async def get_synthesis_order(
    order_id: str,
    user: RequiredUser,
):
    """Get synthesis order details."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM synthesis_orders WHERE id = ?",
            (order_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Order not found")

        if row["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

        return SynthesisOrderPublic(**dict(row))


@router.patch("/orders/{order_id}")
async def update_synthesis_order(
    order_id: str,
    user: RequiredUser,
    status: SynthesisStatus | None = None,
    external_order_id: str | None = None,
    tracking_url: str | None = None,
):
    """Update synthesis order status.

    Users can update status when they place the actual order with the provider
    and track shipping progress.
    """
    from datetime import datetime

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM synthesis_orders WHERE id = ?",
            (order_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Order not found")

        if row["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

        updates = []
        params = []

        if status:
            updates.append("status = ?")
            params.append(status)

            # Update timestamps based on status
            now = datetime.utcnow()
            if status == "ordered":
                updates.append("ordered_at = ?")
                params.append(now)
            elif status == "shipped":
                updates.append("shipped_at = ?")
                params.append(now)
            elif status == "delivered":
                updates.append("delivered_at = ?")
                params.append(now)

        if external_order_id:
            updates.append("external_order_id = ?")
            params.append(external_order_id)

        if tracking_url:
            updates.append("tracking_url = ?")
            params.append(tracking_url)

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        params.append(order_id)
        conn.execute(
            f"UPDATE synthesis_orders SET {', '.join(updates)} WHERE id = ?",
            params
        )

        logger.info(f"Updated synthesis order {order_id}: {updates}")

        # Return updated order
        row = conn.execute(
            "SELECT * FROM synthesis_orders WHERE id = ?",
            (order_id,)
        ).fetchone()

        return SynthesisOrderPublic(**dict(row))
