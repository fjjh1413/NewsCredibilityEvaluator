from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.client_ip import get_client_ip
from app.core.deps import get_current_user
from app.core.redis_client import RedisUnavailableError
from app.core.rate_limit import RedisBackedRateLimiter
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    CurrentUserApiResponse,
    LoginApiResponse,
    RegisterApiResponse,
    TokenResponse,
    UserLogin,
)
from app.schemas.user import UserCreate, UserOut, UserSimpleResponse
from app.services.auth_service import (
    DisabledUserError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    authenticate_user,
    register_user,
)
from app.services.system_log_service import get_request_ip, record_system_log
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/auth", tags=["auth"])
login_rate_limiter = RedisBackedRateLimiter("auth:login")
register_rate_limiter = RedisBackedRateLimiter("auth:register")

LOGIN_RATE_LIMIT_COUNT = 5
REGISTER_RATE_LIMIT_COUNT = 2
AUTH_RATE_LIMIT_WINDOW_SECONDS = 60


async def enforce_register_rate_limit(request: Request) -> None:
    client_ip = get_client_ip(request)
    try:
        is_allowed = await register_rate_limiter.allow_request(
            key=client_ip,
            limit=REGISTER_RATE_LIMIT_COUNT,
            window_seconds=AUTH_RATE_LIMIT_WINDOW_SECONDS,
        )
    except RedisUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="娉ㄥ唽闄愭祦鏈嶅姟鏆備笉鍙敤",
        ) from exc
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="注册请求过于频繁，请稍后再试",
        )


async def enforce_login_rate_limit(request: Request) -> None:
    client_ip = get_client_ip(request)
    try:
        is_allowed = await login_rate_limiter.allow_request(
            key=client_ip,
            limit=LOGIN_RATE_LIMIT_COUNT,
            window_seconds=AUTH_RATE_LIMIT_WINDOW_SECONDS,
        )
    except RedisUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="鐧诲綍闄愭祦鏈嶅姟鏆備笉鍙敤",
        ) from exc
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录请求过于频繁，请稍后再试",
        )


@router.post(
    "/register",
    response_model=RegisterApiResponse,
    dependencies=[Depends(enforce_register_rate_limit)],
)
def register(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    try:
        user = register_user(db, payload)
    except UserAlreadyExistsError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response(str(exc), code=400),
        )

    data = UserSimpleResponse.model_validate(user).model_dump()
    record_system_log(
        db,
        user_id=user.id,
        module="auth",
        action="register",
        description=f"用户注册成功 username={user.username}",
        ip_address=get_request_ip(request),
        target_type="user",
        target_id=user.id,
        result_status="success",
    )
    return success_response(message="注册成功", data=data)


@router.post(
    "/login",
    response_model=LoginApiResponse,
    dependencies=[Depends(enforce_login_rate_limit)],
)
def login(
    payload: UserLogin,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    try:
        user = authenticate_user(db, payload.username, payload.password)
    except InvalidCredentialsError as exc:
        record_system_log(
            db,
            module="auth",
            action="login_failed",
            description=f"登录失败 username={payload.username}",
            ip_address=get_request_ip(request),
            target_type="auth_account",
            target_id=payload.username,
            result_status="failure",
            metadata_json={"reason": "invalid_credentials"},
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=error_response(str(exc), code=401),
        )
    except DisabledUserError as exc:
        record_system_log(
            db,
            module="auth",
            action="login_disabled",
            description=f"禁用账号登录被拒绝 username={payload.username}",
            ip_address=get_request_ip(request),
            target_type="auth_account",
            target_id=payload.username,
            result_status="blocked",
            metadata_json={"reason": "disabled_user"},
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=error_response(str(exc), code=403),
        )

    access_token = create_access_token(
        subject=user.id,
        role=user.role,
        extra_data={"username": user.username},
    )
    data = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserSimpleResponse.model_validate(user),
    ).model_dump()
    record_system_log(
        db,
        user_id=user.id,
        module="auth",
        action="login",
        description=f"用户登录成功 username={user.username}",
        ip_address=get_request_ip(request),
        target_type="user",
        target_id=user.id,
        result_status="success",
    )
    return success_response(message="登录成功", data=data)


@router.get("/me", response_model=CurrentUserApiResponse)
def read_current_user(current_user: User = Depends(get_current_user)) -> dict:
    data = UserOut.model_validate(current_user).model_dump(mode="json")
    return success_response(data=data)
