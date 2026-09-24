from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.client_ip import get_client_ip
from app.core.config import get_settings
from app.core.deps import get_current_user, get_optional_current_user
from app.core.profiling import profile_block
from app.core.redis_client import RedisUnavailableError
from app.core.rate_limit import RedisBackedRateLimiter
from app.crud.detection_crud import get_detection_detail, get_detection_history
from app.db.session import get_db
from app.models.user import User
from app.schemas.detection import (
    DetectNewsApiResponse,
    DetectNewsRequest,
    DetectionTaskApiResponse,
    DetectionDetailApiResponse,
    DetectionDetailOut,
    DetectionHistoryApiResponse,
    DetectionHistoryData,
    DetectionHistoryItem,
    ExtractPreviewApiResponse,
    ExtractPreviewRequest,
)
from app.services.detection_service import (
    DetectionServiceError,
    KnowledgeRetrievalFailedError,
    detect_news_credibility,
)
from app.services.detection_detail_service import (
    read_detection_analysis_payload,
    restore_detection_detail_payload,
)
from app.services.detection_task_service import (
    attach_celery_task_id,
    create_detection_task,
    get_detection_task,
    serialize_detection_task,
)
from app.services.system_log_service import get_request_ip, record_system_log
from app.services.task_queue import TaskQueueUnavailable, enqueue_detection_task
from app.services.web.web_content_fetcher import (
    RecoverableExtractionError,
    SSRFBlockedError,
    WebContentFetchError,
    WebContentFetcher,
)
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/detect", tags=["detect"])
detector_rate_limiter = RedisBackedRateLimiter("detect:news")


async def enforce_detect_news_rate_limit(request: Request) -> None:
    settings = get_settings()
    client_ip = get_client_ip(request)
    try:
        is_allowed = await detector_rate_limiter.allow_request(
            key=client_ip,
            limit=settings.detect_rate_limit_count,
            window_seconds=settings.detect_rate_limit_window_seconds,
            settings=settings,
        )
    except RedisUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="妫€娴嬮檺娴佹湇鍔℃殏涓嶅彲鐢?",
        ) from exc
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="检测请求过于频繁，请稍后再试",
        )


@router.post(
    "/news",
    response_model=DetectNewsApiResponse | DetectionTaskApiResponse,
    dependencies=[Depends(enforce_detect_news_rate_limit)],
)
def detect_news(
    payload: DetectNewsRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> dict:
    settings = get_settings()
    if getattr(settings, "async_detection_enabled", False):
        task = create_detection_task(
            db=db,
            payload=payload,
            current_user=current_user,
        )
        try:
            celery_task_id = enqueue_detection_task(task.id)
            task = attach_celery_task_id(
                db=db,
                task=task,
                celery_task_id=celery_task_id,
            )
            db.refresh(task)
        except TaskQueueUnavailable as exc:
            task.status = "failed"
            task.error_message = str(exc)
            db.add(task)
            db.commit()
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=error_response(message=str(exc), code=503),
            )

        record_system_log(
            db,
            user_id=getattr(current_user, "id", None),
            module="detection",
            action="enqueue_detect_news",
            description=f"提交异步新闻检测任务 task_id={task.id}",
            ip_address=get_request_ip(request),
            target_type="detection_task",
            target_id=task.id,
            result_status="success",
            metadata_json={"status": task.status},
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=jsonable_encoder(
                success_response(
                    message="检测任务已提交",
                    data=serialize_detection_task(task),
                )
            ),
        )

    try:
        result = detect_news_credibility(
            db=db,
            payload=payload,
            current_user=current_user,
        )
    except KnowledgeRetrievalFailedError as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response(message=str(exc), code=503),
        )
    except DetectionServiceError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response(message=str(exc), code=400),
        )

    record_system_log(
        db,
        user_id=getattr(current_user, "id", None),
        module="detection",
        action="detect_news",
        description=(
            f"完成新闻检测 detection_id={result.get('detection_id')} "
            f"risk_level={result.get('risk_level')} "
            f"final_score={result.get('final_score')}"
        ),
        ip_address=get_request_ip(request),
        target_type="detection",
        target_id=result.get("detection_id"),
        result_status="success" if result.get("assessment_status", "completed") == "completed" else "degraded",
        metadata_json={
            "assessment_status": result.get("assessment_status", "legacy"),
            "risk_level": result.get("risk_level"),
            "final_score": result.get("final_score"),
        },
    )
    message = "检测完成" if result.get("assessment_status", "completed") == "completed" else result.get("assessment_reason", "本次无法判断")
    return success_response(message=message, data=result)


@router.post(
    "/extract-preview",
    response_model=ExtractPreviewApiResponse,
    dependencies=[Depends(enforce_detect_news_rate_limit)],
)
def extract_preview(
    payload: ExtractPreviewRequest,
    request: Request,
    current_user: User | None = Depends(get_optional_current_user),
) -> dict:
    """Fetch + extract a news article from a URL for review before detection.

    Returns article fields plus a normalized publication time and its precision
    so the frontend can back-fill the existing detect form (preview-then-edit).
    Shares the detect rate limiter to prevent fetch abuse. Does not touch the
    detection core.
    """
    settings = get_settings()
    fetcher = WebContentFetcher(allow_private_hosts=settings.article_fetch_allow_private_hosts)
    try:
        article = fetcher.fetch_article(payload.url)
    except RecoverableExtractionError as exc:
        recovery_data = {
            "status": exc.status,
            "recovery_action": exc.recovery_action,
        }
        if exc.page_type:
            recovery_data["page_type"] = exc.page_type
        if exc.confidence is not None:
            recovery_data["recognition_confidence"] = exc.confidence
        if exc.signals:
            recovery_data["recognition_signals"] = exc.signals
        if exc.recommended_method:
            recovery_data["recommended_extraction_method"] = exc.recommended_method
        if exc.login_url:
            recovery_data["login_url"] = exc.login_url
        elif exc.status == "login_required":
            recovery_data["login_url"] = payload.url
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=error_response(
                message=str(exc),
                code=422,
                data=recovery_data,
            ),
        )
    except (SSRFBlockedError, WebContentFetchError) as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=error_response(message=str(exc), code=422),
        )

    if not article.get("title") or not article.get("content"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=error_response(
                message="未能从该链接提取到有效的标题或正文，请检查链接或改用手动输入",
                code=422,
            ),
        )

    return success_response(message="提取成功", data=article)


@router.get("/history", response_model=DetectionHistoryApiResponse)
def read_detection_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    risk_level: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    items, total = get_detection_history(
        db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        risk_level=risk_level,
        keyword=keyword,
    )
    data = DetectionHistoryData(
        total=total,
        page=page,
        page_size=page_size,
        items=[DetectionHistoryItem.model_validate(item) for item in items],
    ).model_dump(mode="json")
    return success_response(data=data)


@router.get("/tasks/{task_id}", response_model=DetectionTaskApiResponse)
def read_detection_task(
    task_id: str = Path(..., min_length=1, max_length=36),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> dict:
    task = get_detection_task(db=db, task_id=task_id, current_user=current_user)
    if task is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response("Detection task not found", code=404),
        )
    return success_response(data=serialize_detection_task(task))


@router.post(
    "/{id}/re-evaluate",
    response_model=DetectNewsApiResponse,
    dependencies=[Depends(enforce_detect_news_rate_limit)],
)
def re_evaluate_detection(
    request: Request,
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a new detection from an owned historical record.

    The source record remains immutable for auditability. Retrieval and model
    analysis are intentionally rerun so failed or legacy arbitration can be
    recovered under the current contract.
    """

    record = get_detection_detail(db, detection_id=id, current_user=current_user)
    if record is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response("Detection record not found", code=404),
        )

    analysis_payload = read_detection_analysis_payload(record)
    stored_web_search_enabled = analysis_payload.get("web_search_enabled", True)
    try:
        payload = DetectNewsRequest(
            title=getattr(record, "input_title", ""),
            content=getattr(record, "input_content", ""),
            category=getattr(record, "category", None),
            source_name=analysis_payload.get("source_name"),
            source_url=analysis_payload.get("source_url"),
            publish_time=analysis_payload.get("publish_time"),
            enable_web_search=(
                stored_web_search_enabled
                if isinstance(stored_web_search_enabled, bool)
                else True
            ),
        )
    except ValidationError:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=error_response(
                "历史记录内容不符合当前检测要求，无法重新评估",
                code=422,
            ),
        )
    try:
        with profile_block({"operation": "detect_news_sync"}):
            result = detect_news_credibility(
                db=db,
                payload=payload,
                current_user=current_user,
            )
    except KnowledgeRetrievalFailedError as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response(message=str(exc), code=503),
        )
    except DetectionServiceError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response(message=str(exc), code=400),
        )

    record_system_log(
        db,
        user_id=getattr(current_user, "id", None),
        module="detection",
        action="re_evaluate_detection",
        description=(
            f"重新评估新闻检测 source_detection_id={id} "
            f"new_detection_id={result.get('detection_id')}"
        ),
        ip_address=get_request_ip(request),
        target_type="detection",
        target_id=result.get("detection_id"),
        result_status="success",
        metadata_json={
            "source_detection_id": id,
            "new_detection_id": result.get("detection_id"),
        },
    )
    return success_response(message="重新评估完成", data=result)


@router.get("/{id}", response_model=DetectionDetailApiResponse)
def read_detection_detail(
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    record = get_detection_detail(db, detection_id=id, current_user=current_user)
    if record is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response("Detection record not found", code=404),
        )

    data = restore_detection_detail_payload(
        DetectionDetailOut.model_validate(record).model_dump(mode="json"),
        record,
    )
    return success_response(data=data)
