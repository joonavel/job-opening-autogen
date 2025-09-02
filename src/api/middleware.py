"""
FastAPI 커스텀 미들웨어

로깅, 에러 핸들링, 성능 모니터링 등을 위한 미들웨어를 정의합니다.
"""

import time
import logging
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """요청/응답 로깅 미들웨어"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """요청 처리 및 로깅"""
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        # 요청 로깅
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "user_agent": request.headers.get("user-agent"),
                "client_ip": request.client.host if request.client else None
            }
        )
        
        # 요청 ID를 request state에 저장
        request.state.request_id = request_id
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # 응답 로깅
            logger.info(
                f"Request completed",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "process_time": round(process_time, 4)
                }
            )
            
            # 응답 헤더에 요청 ID와 처리 시간 추가
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(round(process_time, 4))
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "process_time": round(process_time, 4)
                },
                exc_info=True
            )
            raise


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """에러 핸들링 미들웨어"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """에러 처리"""
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.exception("Unhandled error in middleware", exc_info=True)
            
            # 개발 환경에서는 에러를 다시 발생시켜 자세한 정보 제공
            raise
