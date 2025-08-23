"""
채용공고 자동생성 시스템 데이터 모델 패키지

이 패키지는 시스템에서 사용되는 모든 Pydantic 모델들을 포함합니다.
"""

from .job_posting import (
    # 열거형들
    JobTypeEnum,
    ExperienceLevel, 
    WorkLocationEnum,
    SalaryType,
    ValidationStatus,
    
    # 기본 모델들
    SalaryInfo,
    WorkLocation,
    CompanyData,
    UserInput,
    ValidationResult,
    JobPostingDrarft,
    JobPostingMetadata,
    JobPostingTemplate,
)

__all__ = [
    # 열거형들
    "JobTypeEnum",
    "ExperienceLevel",
    "WorkLocationEnum", 
    "SalaryType",
    "ValidationStatus",
    
    # 모델들
    "SalaryInfo",
    "WorkLocation",
    "CompanyData",
    "UserInput",
    "ValidationResult",
    "JobPostingMetadata", 
    "JobPostingTemplate",
]
