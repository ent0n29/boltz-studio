"""Lab validation routes."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..logger import get_logger
from ..middleware import RequiredUser
from ..models.validation import (
    ValidationCreate,
    ValidationList,
    ValidationPublic,
    ValidationSummary,
)
from ..services.validation_store import ValidationStore, get_validation_store
from ..services.activity_store import ActivityStore, get_activity_store
from ..services.notification_store import NotificationStore, get_notification_store

logger = get_logger("routes.validation")

router = APIRouter(prefix="/api/validations", tags=["validations"])


@router.post("/designs/{design_id}", response_model=dict)
async def create_validation(
    design_id: str,
    data: ValidationCreate,
    user: RequiredUser,
    store: ValidationStore = Depends(get_validation_store),
    activity_store: ActivityStore = Depends(get_activity_store),
    notification_store: NotificationStore = Depends(get_notification_store),
) -> dict:
    """Submit a lab validation for a design.

    Args:
        design_id: Design being validated
        data: Validation data
        user: Authenticated user
        store: Validation store
        activity_store: Activity store
        notification_store: Notification store

    Returns:
        Created validation ID
    """
    validation_id = store.create(design_id, user.id, data)

    # Record activity
    activity_store.record(
        user_id=user.id,
        activity_type="design_validated",
        target_type="design",
        target_id=design_id,
        metadata={"result": data.result, "type": data.validation_type},
    )

    # Notify design owner
    from ..services.design_store import get_design_store
    design_store = get_design_store()
    design = design_store.get_by_id(design_id)
    if design and design.user_id != user.id:
        notification_store.create(
            user_id=design.user_id,
            notification_type="validation",
            actor_id=user.id,
            target_type="design",
            target_id=design_id,
            message=f"{user.display_name} submitted a {data.result} validation for {design.name}",
        )

    return {"id": validation_id, "message": "Validation submitted"}


@router.get("/designs/{design_id}", response_model=ValidationList)
async def get_design_validations(
    design_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    store: ValidationStore = Depends(get_validation_store),
) -> ValidationList:
    """Get validations for a design.

    Args:
        design_id: Design ID
        offset: Pagination offset
        limit: Max results
        store: Validation store

    Returns:
        List of validations
    """
    return store.get_by_design(design_id, offset, limit)


@router.get("/designs/{design_id}/summary", response_model=ValidationSummary)
async def get_validation_summary(
    design_id: str,
    store: ValidationStore = Depends(get_validation_store),
) -> ValidationSummary:
    """Get validation summary for a design.

    Args:
        design_id: Design ID
        store: Validation store

    Returns:
        Validation summary
    """
    return store.get_summary(design_id)


@router.delete("/{validation_id}")
async def delete_validation(
    validation_id: str,
    user: RequiredUser,
    store: ValidationStore = Depends(get_validation_store),
) -> dict:
    """Delete a validation.

    Args:
        validation_id: Validation ID
        user: Authenticated user (must be owner)
        store: Validation store

    Returns:
        Success message

    Raises:
        403 if not owner
    """
    if not store.delete(validation_id, user.id):
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"message": "Validation deleted"}
