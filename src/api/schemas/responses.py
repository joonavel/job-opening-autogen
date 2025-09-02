"""
API 응답 스키마

FastAPI 엔드포인트의 응답 스키마들을 정의합니다.
job_posting.py와 models.py의 모델들을 기반으로 API용 스키마를 작성합니다.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from enum import Enum

from pydantic import BaseModel, Field

from ...models.job_posting import (
    JobPostingTemplate,
    CompanyData,
    ValidationResult,
    ValidationStatus,
    JobPostingDraft
)


class BaseResponse(BaseModel):
    """기본 응답 스키마"""
    success: bool = Field(..., description="요청 성공 여부")
    message: str = Field(..., description="응답 메시지")
    timestamp: datetime = Field(default_factory=datetime.now, description="응답 시각")


class ErrorResponse(BaseResponse):
    """에러 응답 스키마"""
    success: bool = Field(default=False)
    error_type: str = Field(..., description="에러 타입")
    error_details: Optional[Dict[str, Any]] = Field(None, description="상세 에러 정보")


class GenerationStatusResponse(BaseModel):
    """생성 상태 응답"""
    workflow_id: str = Field(..., description="워크플로우 ID")
    status: str = Field(..., description="현재 상태")
    current_step: str = Field(..., description="현재 단계")
    job_posting_draft: Optional[JobPostingDraft] = Field(None, description="채용공고 템플릿")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="워크플로우 메타데이터")

class JobPostingResponse(BaseResponse):
    """채용공고 생성 완료 응답"""
    template: JobPostingTemplate = Field(..., description="생성된 채용공고 템플릿")
    generation_metadata: Dict[str, Any] = Field(..., description="생성 메타데이터")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "채용공고가 성공적으로 생성되었습니다",
                "timestamp": "2024-01-01T00:00:00",
                "template": {
                    "title": "백엔드 개발자 채용",
                    "company_name": "ABC 테크놀로지",
                    "job_description": "우리 회사의 백엔드 시스템을 개발할 인재를 찾습니다...",
                },
                "generation_metadata": {
                    "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
                    "generated_by": "gpt-4o-mini",
                },
            }
        }


class CompanyListResponse(BaseResponse):
    """기업 목록 응답"""
    companies: List[CompanyData] = Field(..., description="기업 목록")
    total_count: int = Field(..., description="전체 기업 수")
    page: int = Field(..., description="현재 페이지")
    page_size: int = Field(..., description="페이지 크기")
    total_pages: int = Field(..., description="전체 페이지 수")


class CompanyDetailResponse(BaseResponse):
    """기업 상세 정보 응답"""
    company: CompanyData = Field(..., description="기업 정보")
    welfare_items: List[Dict[str, Any]] = Field(default_factory=list, description="복리후생 정보")
    history_items: List[Dict[str, Any]] = Field(default_factory=list, description="연혁 정보")
    talent_criteria: List[Dict[str, Any]] = Field(default_factory=list, description="인재상 정보")


class FeedbackSessionResponse(BaseResponse):
    """피드백 세션 응답"""
    session_id: str = Field(..., description="세션 ID")
    session_type: str = Field(..., description="세션 유형")
    status: str = Field(..., description="세션 상태")
    feedback_request: List[str] = Field(..., description="피드백 요청 데이터")
    user_feedback: Optional[List[str]] = Field(None, description="사용자 피드백")
    expires_at: datetime = Field(..., description="세션 만료 시각")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "피드백 세션이 생성되었습니다",
                "timestamp": "2024-01-01T00:00:00",
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "session_type": "sensitivity_detected",
                "status": "pending",
                "feedback_request": ["민감한 표현이 감지되었습니다. 수정이 필요합니다."],
                "user_feedback": ["제거해줘"],
                "expires_at": "2024-01-01T01:00:00"
            }
        }


class FeedbackSubmissionResponse(BaseResponse):
    """피드백 제출 응답"""
    session_id: str = Field(..., description="세션 ID")
    user_feedback: List[str] = Field(..., description="사용자 피드백")

class FeedbackSessionListResponse(BaseResponse):
    """피드백 세션 목록 응답"""
    sessions: List[Dict[str, Any]] = Field(..., description="피드백 세션 목록")

class SensitivityValidationStartResponse(BaseResponse):
    """민감성 검증 시작 응답"""
    thread_id: str = Field(..., description="스레드 ID")

class ValidationSummaryResponse(BaseResponse):
    """검증 요약 응답"""
    validation_results: List[ValidationResult] = Field(..., description="검증 결과들")
    overall_status: ValidationStatus = Field(..., description="전체 검증 상태")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="전체 점수")
    recommendations: List[str] = Field(default_factory=list, description="개선 권장사항")


class HealthCheckResponse(BaseModel):
    """헬스체크 응답"""
    status: str = Field(..., description="서비스 상태")
    version: str = Field(..., description="서비스 버전")
    timestamp: datetime = Field(default_factory=datetime.now, description="응답 시각")
    components: Dict[str, str] = Field(..., description="컴포넌트별 상태")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0", 
                "timestamp": "2024-01-01T00:00:00",
                "components": {
                    "database": "healthy",
                    "redis": "healthy",
                    "llm_service": "healthy"
                }
            }
        }


class WorkflowStatusResponse(BaseResponse):
    """워크플로우 상태 응답"""
    workflow_id: str = Field(..., description="워크플로우 ID")
    status: str = Field(..., description="워크플로우 상태")
    current_node: Optional[str] = Field(None, description="현재 노드")
    progress_percentage: float = Field(..., ge=0.0, le=100.0, description="진행률")
    steps_completed: int = Field(..., description="완료된 단계 수")
    total_steps: int = Field(..., description="전체 단계 수")
    created_at: datetime = Field(..., description="생성 시각")
    updated_at: datetime = Field(..., description="업데이트 시각")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="워크플로우 메타데이터")


class PaginatedResponse(BaseModel):
    """페이지네이션 응답"""
    items: List[Any] = Field(..., description="항목 목록")
    total_count: int = Field(..., description="전체 항목 수")
    page: int = Field(..., description="현재 페이지")
    page_size: int = Field(..., description="페이지 크기")
    total_pages: int = Field(..., description="전체 페이지 수")
    has_next: bool = Field(..., description="다음 페이지 존재 여부")
    has_previous: bool = Field(..., description="이전 페이지 존재 여부")


class StreamingResponse(BaseModel):
    """스트리밍 응답 (Server-Sent Events용)"""
    event_type: str = Field(..., description="이벤트 타입")
    data: Dict[str, Any] = Field(..., description="이벤트 데이터") 
    timestamp: datetime = Field(default_factory=datetime.now, description="이벤트 시각")
    sequence: int = Field(..., description="이벤트 순서")


class TemplateListResponse(PaginatedResponse):
    """템플릿 목록 응답"""
    items: List[JobPostingTemplate] = Field(..., description="템플릿 목록")


class StatisticsResponse(BaseResponse):
    """통계 응답"""
    period: str = Field(..., description="통계 기간")
    metrics: Dict[str, Any] = Field(..., description="통계 지표")
    charts: Dict[str, Any] = Field(default_factory=dict, description="차트 데이터")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "통계 데이터를 조회했습니다",
                "timestamp": "2024-01-01T00:00:00",
                "period": "last_30_days",
                "metrics": {
                    "total_templates_generated": 150,
                    "success_rate": 94.5,
                    "average_generation_time": 18.7,
                    "feedback_sessions": 23
                },
                "charts": {
                    "daily_generation_count": [5, 8, 12, 6, 9],
                    "validation_score_distribution": [10, 25, 45, 15, 5]
                }
            }
        }
