from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user_or_api_key
from app.models import Notification, Works
from app.schemas import NotificationResponse

router = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_user_or_api_key)],
)


@router.get("", response_model=list[NotificationResponse])
def read_notifications(
    current_user=Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Notification, Works.title)
        .join(Works, Notification.work_id == Works.id)
        .where(Notification.user_id == current_user.id)
        .order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
    )

    rows = db.execute(stmt).all()

    return [
        {
            "id": notification.id,
            "workId": str(notification.work_id),
            "workTitle": title,
            "isRead": notification.is_read,
            "createdAt": notification.created_at,
        }
        for notification, title in rows
    ]


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
def read_notification(
    notification_id: int,
    current_user=Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    notification.is_read = True
    db.commit()
    db.refresh(notification)

    work_title = db.scalar(
        select(Works.title).where(Works.id == notification.work_id)
    )

    return {
        "id": notification.id,
        "workId": str(notification.work_id),
        "workTitle": work_title,
        "isRead": notification.is_read,
        "createdAt": notification.created_at,
    }