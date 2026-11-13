from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user_or_api_key
from app.models import Notification, Works
from app.schemas import (
    NotificationResponse, 
    NotificationItemResponse, 
    NotificationCreateRequest,
    NotificationUnreadCountResponse,
    NotificationReadAllResponse
)

from app.models import User

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
            "title": notification.title,
            "message": notification.message,
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
        "title": notification.title,
        "message": notification.message,
        "isRead": notification.is_read,
        "createdAt": notification.created_at,
    }

@router.post(
    "/create",
    response_model=list[NotificationItemResponse],
    status_code=status.HTTP_201_CREATED,
    summary="작업 등록 알림 생성",
    description="지정한 작업을 현재 사용자 외 활성 사용자에게 알림으로 등록합니다.",
)
def create_work_notifications(
    body: NotificationCreateRequest,
    current_user=Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    work = db.get(Works, body.work_id)
    if work is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work not found",
        )

    # 동일 작업에 대한 중복 알림 생성을 방지합니다.
    existing_user_ids = set(
        db.scalars(
            select(Notification.user_id).where(
                Notification.work_id == body.work_id
            )
        ).all()
    )

    recipients = db.scalars(
        select(User).where(
            User.is_active.is_(True),
            User.id != current_user.id,
        )
    ).all()

    notifications = []
    for recipient in recipients:
        if recipient.id in existing_user_ids:
            continue

        notification = Notification(
            user_id=recipient.id,
            work_id=work.id,
            title="새 작업이 등록되었습니다.",
            message=f"{work.repository or '저장소'}에 새로운 작업 '{work.title}'이 등록되었습니다.",
            is_read=False,
        )
        db.add(notification)
        notifications.append(notification)

    db.commit()

    result = []
    for notification in notifications:
        db.refresh(notification)
        result.append({
            "id": notification.id,
            "work_id": str(work.id),
            "work_title": work.title,
            "title": notification.title,
            "message": notification.message,
            "is_read": notification.is_read,
            "created_at": notification.created_at,
        })
    return result

@router.get(
    "/unread-count",
    response_model=NotificationUnreadCountResponse,
    summary="읽지 않은 알림 개수 조회",
)
def read_unread_notification_count(
    current_user=Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    count = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    ) or 0
    return {"unread_count": count}


@router.patch(
    "/read-all",
    response_model=NotificationReadAllResponse,
    summary="모든 알림 읽음 처리",
)
def read_all_notifications(
    current_user=Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    result = db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    db.commit()
    return {"updated_count": result.rowcount or 0}