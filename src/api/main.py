"""
FastAPI 메인 애플리케이션

이 모듈은 채용공고 자동생성 서비스의 메인 FastAPI 애플리케이션을 정의합니다.
LangGraph 워크플로우와 연동되는 RESTful API 엔드포인트를 제공합니다.
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from dotenv import load_dotenv

from config.settings import get_settings
from ..exceptions import ValidationError
from .routes import generate, companies, feedback, status
from .middleware import LoggingMiddleware, ErrorHandlingMiddleware
from src.database.data_loader import initialize_database_with_sample_data

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    load_dotenv(override=True)
    # 시작업 시 실행
    logger.info("FastAPI 애플리케이션 시작")
    logger.info(f"환경: {settings.environment}")
    logger.info(f"API 서버: {settings.api.host}:{settings.api.port}")
    logger.info("데이터베이스 초기화 시작")
    initialize_database_with_sample_data()
    logger.info("데이터베이스 초기화 완료")
    yield
    
    # 종료 시 실행
    logger.info("FastAPI 애플리케이션 종료")


def create_app() -> FastAPI:
    """FastAPI 애플리케이션 팩토리"""
    
    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        description=settings.description,
        openapi_url="/api/v1/openapi.json" if settings.is_development else None,
        docs_url="/api/v1/docs" if settings.is_development else None,
        redoc_url="/api/v1/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )
    
    # CORS 미들웨어 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else ["https://your-domain.com"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # 신뢰할 수 있는 호스트 미들웨어 (프로덕션용)
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["your-domain.com", "*.your-domain.com"]
        )
    
    # 커스텀 미들웨어 추가
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    
    # 라우터 등록
    app.include_router(
        status.router,
        prefix="/api/v1/status",
        tags=["status"]
    )
    
    app.include_router(
        generate.router,
        prefix="/api/v1/generate",
        tags=["generate"]
    )
    
    app.include_router(
        companies.router,
        prefix="/api/v1/companies",
        tags=["companies"]
    )
    
    app.include_router(
        feedback.router,
        prefix="/api/v1/feedback",
        tags=["feedback"]
    )
    
    # 전역 예외 핸들러 등록
    register_exception_handlers(app)
    
    return app


def register_exception_handlers(app: FastAPI) -> None:
    """전역 예외 핸들러 등록"""
    
    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        """비즈니스 로직 검증 오류 핸들러"""
        logger.error(f"Validation error: {exc}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "Validation Error",
                "message": str(exc),
                "type": "validation_error"
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(request: Request, exc: RequestValidationError):
        """요청 데이터 검증 오류 핸들러"""
        logger.error(f"Request validation error: {exc}")
        return JSONResponse(
            status_code=422,
            content={
                "error": "Request Validation Error",
                "message": "요청 데이터가 올바르지 않습니다",
                "details": exc.errors(),
                "type": "request_validation_error"
            }
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """HTTP 예외 핸들러"""
        logger.error(f"HTTP error: {exc.status_code} - {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": f"HTTP {exc.status_code}",
                "message": exc.detail,
                "type": "http_error"
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """일반 예외 핸들러"""
        logger.exception("Unhandled exception occurred", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "서버에 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                "type": "internal_error"
            }
        )


# 애플리케이션 인스턴스 생성
app = create_app()


@app.get("/", include_in_schema=False)
async def root():
    """루트 엔드포인트"""
    return {
        "service": settings.project_name,
        "version": settings.version,
        "status": "running",
        "docs_url": "/api/v1/docs" if settings.is_development else None
    }


def main():
    """메인 실행 함수"""
    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload and settings.is_development,
        workers=1 if settings.is_development else settings.api.workers,
        log_level=settings.logging.level.lower(),
    )


if __name__ == "__main__":
    main()
