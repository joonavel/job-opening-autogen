"""
API 요청 스키마

FastAPI 엔드포인트의 요청 스키마들을 정의합니다.
job_posting.py의 모델들을 기반으로 API용 스키마를 작성합니다.
"""

from datetime import date, datetime
from typing import Optional, List, Dict, Any, Annotated
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, EmailStr, HttpUrl

from ...models.job_posting import (
    JobTypeEnum, 
    ExperienceLevel, 
    WorkLocationEnum, 
    SalaryType,
    SalaryInfo,
    WorkLocation,
    UserInput
)


class GenerateJobPostingRequest(BaseModel):
    """채용공고 생성 요청"""
    user_input: str = Field(..., description="사용자 입력 데이터")
    session_id: Optional[str] = Field(None, description="프론트엔드 세션 ID (워크플로우 추적용)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_input": """
                채용 직무명: 백엔드 개발자
                회사명: ABC 테크놀로지
                필수 요구사항:
                - Python 3년 이상 경험
                - Django/FastAPI 경험
                - PostgreSQL 사용 경험
                우대 사항:
                - AWS 클라우드 서비스 경험
                - Docker/Kubernetes 경험
                채용 형태: 정규직
                경력 수준: 중급
                급여 정보: 연봉 5000만원 이상
                근무 위치: 서울
                추가 정보: 회사 소개, 채용 프로세스
                """,
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }


class CompanyInfoRequest(BaseModel):
    """기업 정보 조회 요청"""
    company_name: Optional[str] = Field(None, description="회사명으로 검색")
    business_number: Optional[str] = Field(None, description="사업자등록번호로 검색") 
    page: int = Field(1, ge=1, description="페이지 번호")
    page_size: int = Field(10, ge=1, le=100, description="페이지 크기")


class CompanyDetailRequest(BaseModel):
    """기업 상세 정보 조회 요청"""
    company_id: int = Field(..., description="기업 ID")
    include_welfare: bool = Field(True, description="복리후생 정보 포함 여부")
    include_history: bool = Field(True, description="연혁 정보 포함 여부")
    include_talent_criteria: bool = Field(True, description="인재상 정보 포함 여부")


class FeedbackSessionRequest(BaseModel):
    """피드백 세션 생성 요청"""
    session_type: str = Field(..., description="피드백 유형")
    template_id: str = Field(..., description="템플릿 ID")
    feedback_request: Dict[str, Any] = Field(..., description="피드백 요청 데이터")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_type": "sensitivity_detected",
                "template_id": "123e4567-e89b-12d3-a456-426614174000",
                "feedback_request": {
                    "questions": ["민감한 표현이 감지되었습니다: '남성만 지원 가능' - 이를 어떻게 수정하시겠습니까?"],
                    "thread_id": "123e4567-e89b-12d3-a456-426614174000",
                }
            }
        }


class FeedbackSubmissionRequest(BaseModel):
    """피드백 제출 요청"""
    session_id: UUID = Field(..., description="세션 ID")
    user_feedback: List[str] = Field(..., description="사용자 피드백 데이터")
    timestamp: datetime = Field(..., description="피드백 제출 시간")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_feedback": ["제거해줘", "~로 변경해줘줘"],
                "timestamp": datetime.now().isoformat()
            }
        }


class StatusQueryRequest(BaseModel):
    """상태 조회 요청"""
    workflow_id: Optional[str] = Field(None, description="워크플로우 ID")
    session_id: Optional[UUID] = Field(None, description="세션 ID")
    template_id: Optional[UUID] = Field(None, description="템플릿 ID")


class ValidationRequest(BaseModel):
    """검증 요청"""
    user_input: UserInput = Field(..., description="검증할 사용자 입력")
    validation_types: List[str] = Field(
        default=["sensitivity", "completeness", "quality"],
        description="수행할 검증 유형들"
    )
    strict_mode: bool = Field(False, description="엄격 모드")


class TemplateUpdateRequest(BaseModel):
    """템플릿 수정 요청"""
    template_id: UUID = Field(..., description="템플릿 ID")
    updates: Dict[str, Any] = Field(..., description="수정할 데이터")
    update_reason: str = Field(..., description="수정 사유")
    
    class Config:
        json_schema_extra = {
            "example": {
                "template_id": "123e4567-e89b-12d3-a456-426614174000",
                "updates": {
                    "title": "수정된 채용공고 제목",
                    "requirements": ["수정된 요구사항1", "수정된 요구사항2"]
                },
                "update_reason": "사용자 피드백 반영"
            }
        }
