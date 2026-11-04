from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from datetime import date, datetime, time, timedelta

from app.database import get_db
from app.deps import get_current_user_or_api_key
from app.models import Works
from app.schemas import (
    WorkDetailResponse,
    WorkResponse,
    WorkSummaryUpdate,
)


router = APIRouter(
    prefix="/api/works",
    tags=["works"],
    dependencies=[Depends(get_current_user_or_api_key)],
)

STATUS_EDITED = "edited"
VALID_STATUSES = {"auto", "review", "edited"}

_MAX_ID = 2**63 - 1
_MAX_ID_STR = str(_MAX_ID)

def _get_work(db: Session, work_id: str) -> Works:
    record = None

    if work_id.isascii() and work_id.isdigit():
        normalized_id = work_id.lstrip("0") or "0"

        # DB 정수 범위를 초과하는 ID 방지
        if (
            len(normalized_id) < len(_MAX_ID_STR)
            or (
                len(normalized_id) == len(_MAX_ID_STR)
                and normalized_id <= _MAX_ID_STR
            )
        ):
            record = db.scalar(
                select(Works)
                .where(Works.id == int(normalized_id))
                .options(
                    selectinload(Works.changes),
                    selectinload(Works.sources),
                )
            )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work with ID {work_id} not found",
        )
    return record

@router.get(
    "",
    response_model=list[WorkResponse],
    summary="작업 목록 조회",
    description="조건에 맞는 작업 목록을 최신순으로 페이징하여 조회합니다.",
)
def read_works(
    response: Response,
    page: int | None = Query(None, ge=1, description="페이지 번호"),
    size: int | None = Query(None, ge=1, le=100, description="페이지당 개수"),
    repository: str | None = Query(
        None,
        description="저장소 필터",
    ),
    q: str | None = Query(
        None,
        description="제목/요약/저장소 검색 키워드",
    ),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="상태 필터 (auto | review | edited)",
    ),
    author: str | None = Query(
        None,
        description="작성자 필터",
    ),
    created_from: date | None = Query(
        None,
        description="작업 생성 시작 날짜 (YYYY-MM-DD)",
    ),
    created_to: date | None = Query(
        None,
        description="작업 생성 종료 날짜 (YYYY-MM-DD)",
    ),
    db: Session = Depends(get_db),
):
    if status_filter is not None and status_filter not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Allowed values: auto, review, edited",
        )

    stmt = select(Works)

    if created_from:
        start_datetime = datetime.combine(created_from, time.min)
        stmt = stmt.where(Works.created_at >= start_datetime)

    if created_to:
        end_datetime = datetime.combine(
            created_to + timedelta(days=1),
            time.min,
        )
        stmt = stmt.where(Works.created_at < end_datetime)
    if repository:
        stmt = stmt.where(Works.repository == repository)
    if status_filter:
        stmt = stmt.where(Works.status == status_filter)
    if author:
        stmt = stmt.where(Works.author == author)
    if q and q.strip():
        keyword = q.strip()
        stmt = stmt.where(
            or_(
                Works.title.icontains(keyword, autoescape=True),
                Works.summary.icontains(keyword, autoescape=True),
                Works.repository.icontains(keyword, autoescape=True),
            )
        )

    # 필터 적용 후 전체 개수
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0
    response.headers["X-Total-Count"] = str(total)

    # 최신순 정렬 및 페이지네이션
    stmt = stmt.order_by(
        Works.created_at.desc(),
        Works.id.desc(),
    )

    if page is not None and size is not None:
        skip = (page - 1) * size
        stmt = stmt.offset(skip).limit(size)

    return list(db.scalars(stmt).all())

@router.get(
    "/me",
    response_model=list[WorkResponse],
    summary="내 작업 목록 조회",
    description="로그인한 사용자가 작성한 작업 목록을 최신순으로 조회합니다.",
)
def read_my_works(
    current_user=Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    username = getattr(current_user, "username", None)

    if not username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User authentication is required",
        )

    stmt = (
        select(Works)
        .where(Works.author == username)
        .order_by(
            Works.created_at.desc(),
            Works.id.desc(),
        )
    )

    return list(db.scalars(stmt).all())

@router.get(
    "/{work_id}",
    response_model=WorkDetailResponse,
    summary="작업 상세 조회",
    description="특정 ID의 작업 상세 정보를 조회합니다.",
)
def read_work(
    work_id: str,
    db: Session = Depends(get_db),
):
    return _get_work(db, work_id=work_id)

@router.patch(
    "/{work_id}",
    response_model=WorkDetailResponse,
    summary="작업 요약 수정",
    description="요약을 수정하고 status를 edited로 변경합니다.",
)
def update_work_summary(
    work_id: str,
    body: WorkSummaryUpdate,
    db: Session = Depends(get_db),
):
    record = _get_work(db, work_id=work_id)
    if not body.summary.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="summary must not be blank",
        )

    record.summary = body.summary
    record.status = STATUS_EDITED
    db.commit()

    # 관계 데이터까지 포함하여 상세 정보 재조회
    return _get_work(db, work_id=work_id)
