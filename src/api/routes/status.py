"""
상태 및 헬스체크 API 라우터

시스템 상태, 헬스체크, 워크플로우 상태 등을 관리하는 엔드포인트를 제공합니다.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import get_settings
from ...database.fastapi_db import get_db
from ..schemas.requests import StatusQueryRequest
from ..schemas.responses import (
    HealthCheckResponse,
    WorkflowStatusResponse,
    BaseResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    """
    헬스체크 엔드포인트
    
    시스템의 전반적인 상태를 확인합니다.
    """
    try:
        components = {}
        
        # 데이터베이스 상태 확인
        try:
            db.execute(text("SELECT 1"))
            components["database"] = "healthy"
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            components["database"] = "unhealthy"
        
        # Redis 상태 확인 (구현 시)
        components["redis"] = "healthy"  # TODO: 실제 Redis 연결 확인
        
        # LLM 서비스 상태 확인 (구현 시)  
        components["llm_service"] = "healthy"  # TODO: 실제 LLM 서비스 확인
        
        # 전체 상태 결정
        overall_status = "healthy" if all(
            status == "healthy" for status in components.values()
        ) else "unhealthy"
        
        return HealthCheckResponse(
            status=overall_status,
            version=settings.version,
            components=components
        )
        
    except Exception as e:
        logger.exception("Health check failed")
        raise HTTPException(status_code=500, detail="Health check failed")


@router.get("/workflow/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: str,
    db: Session = Depends(get_db)
) -> WorkflowStatusResponse:
    """
    워크플로우 상태 조회
    
    특정 워크플로우의 현재 상태와 진행률을 확인합니다.
    """
    try:
        # TODO: 실제 워크플로우 상태 조회 로직 구현
        # 현재는 mock 데이터 반환
        
        return WorkflowStatusResponse(
            success=True,
            message=f"워크플로우 {workflow_id} 상태를 조회했습니다",
            workflow_id=workflow_id,
            status="running",  # pending, running, completed, failed, interrupted
            current_node="sensitivity_validation",
            progress_percentage=65.0,
            steps_completed=3,
            total_steps=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={
                "user_input_received": True,
                "validation_started": True,
                "feedback_requested": False
            }
        )
        
    except Exception as e:
        logger.exception(f"Failed to get workflow status for {workflow_id}")
        raise HTTPException(
            status_code=404, 
            detail=f"워크플로우 {workflow_id}를 찾을 수 없습니다"
        )


@router.get("/system", response_model=BaseResponse)
async def get_system_info() -> BaseResponse:
    """
    시스템 정보 조회
    
    현재 시스템의 설정 및 환경 정보를 반환합니다.
    """
    try:
        system_info = {
            "environment": settings.environment,
            "version": settings.version,
            "features": {
                "streaming_enabled": settings.features.enable_streaming,
                "caching_enabled": settings.features.enable_caching,
                "monitoring_enabled": settings.features.enable_monitoring
            },
            "performance": {
                "max_concurrent_requests": settings.performance.max_concurrent_requests,
                "request_timeout": settings.performance.request_timeout
            }
        }
        
        return BaseResponse(
            success=True,
            message="시스템 정보를 조회했습니다",
            **system_info
        )
        
    except Exception as e:
        logger.exception("Failed to get system info")
        raise HTTPException(status_code=500, detail="시스템 정보 조회에 실패했습니다")


@router.get("/metrics", response_model=BaseResponse)
async def get_metrics(
    period: str = Query("1h", description="통계 기간 (1h, 24h, 7d, 30d)"),
    db: Session = Depends(get_db)
) -> BaseResponse:
    """
    시스템 메트릭 조회
    
    지정된 기간의 시스템 성능 메트릭을 반환합니다.
    """
    try:
        # TODO: 실제 메트릭 수집 로직 구현
        
        mock_metrics = {
            "requests_total": 1547,
            "requests_per_minute": 12.3,
            "average_response_time": 245.7,
            "error_rate": 0.8,
            "templates_generated": 89,
            "feedback_sessions_active": 3
        }
        
        return BaseResponse(
            success=True,
            message=f"{period} 기간의 메트릭을 조회했습니다",
        )
        
    except Exception as e:
        logger.exception("Failed to get metrics")
        raise HTTPException(status_code=500, detail="메트릭 조회에 실패했습니다")
