from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import get_current_user_or_api_key
from app.models import Works
from app.schemas import WorkDetailResponse, WorkResponse, WorkSummaryUpdate

router = APIRouter(
    prefix="/api/works",
    tags=["works"],
    dependencies=[Depends(get_current_user_or_api_key)],  # 인증 필수 (JWT 또는 X-API-Key)
)

STATUS_EDITED = "edited"
_MAX_ID = 2**63 - 1  # DB 정수 범위를 넘는 id는 "없는 id"로 취급


def _get_work(db: Session, work_id: str) -> Works:
    # 프론트는 id를 문자열로 다룬다. 숫자가 아니거나 존재하지 않으면 모두 404.
    record = None
    if work_id.isascii() and work_id.isdigit() and int(work_id) <= _MAX_ID:
        record = db.scalar(
            select(Works)
            .where(Works.id == int(work_id))
            .options(selectinload(Works.changes), selectinload(Works.sources))
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
    description=(
        "조건에 맞는 작업 목록을 최신순(createdAt 내림차순)으로 페이징하여 조회합니다. "
        "필터 적용 후의 전체 개수는 `X-Total-Count` 응답 헤더로 내려갑니다."
    ),
)
def read_works(
    response: Response,
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(10, ge=1, le=100, description="페이지당 개수"),
    repository: str | None = Query(None, description="저장소 필터 (예: nolga/api-server)"),
    q: str | None = Query(None, description="제목/요약 검색 키워드"),
    status_filter: str | None = Query(None, alias="status", description="상태 필터 (auto | review | edited)"),
    author: str | None = Query(None, description="작성자 필터"),
    db: Session = Depends(get_db),
):
    skip = (page - 1) * size

    stmt = select(Works)

    # 필터링 조건
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
            )
        )

    # 전체 개수 집계
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0
    response.headers["X-Total-Count"] = str(total)

    # 페이징 및 정렬 (최신순, 같은 날짜는 id 내림차순으로 순서 고정)
    stmt = stmt.order_by(Works.created_at.desc(), Works.id.desc()).offset(skip).limit(size)
    return list(db.scalars(stmt).all())


@router.get(
    "/{work_id}",
    response_model=WorkDetailResponse,
    summary="작업 상세 조회",
    description="특정 ID의 작업 상세 정보를 조회합니다. 없는 id는 404를 반환합니다.",
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
    description="요약을 수정하고 status를 `edited`로 변경한 뒤, 수정된 작업 상세를 반환합니다.",
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
    db.refresh(record)
    return record