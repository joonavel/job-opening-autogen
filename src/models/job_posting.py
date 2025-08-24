"""
채용공고 관련 Pydantic 모델들

이 모듈은 채용공고 자동생성 시스템에서 사용되는 핵심 데이터 모델들을 정의합니다.
- JobPostingTemplate: 채용공고 템플릿 모델
- CompanyData: 기업 정보 모델
- UserInput: 사용자 입력 데이터 모델  
- ValidationResult: 검증 결과 모델
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional, List, Dict, Any, Union, Annotated
from typing_extensions import Self
from uuid import UUID, uuid4

from pydantic import (
    BaseModel, 
    Field, 
    field_validator, 
    model_validator, 
    EmailStr,
    HttpUrl,
    model_serializer
)


class JobTypeEnum(str, Enum):
    """채용 형태 열거형"""
    FULL_TIME = "정규직"
    PART_TIME = "계약직"
    INTERN = "인턴십"
    CONTRACTOR = "프리랜서"
    TEMPORARY = "임시직"

class CompanyClassificationEnum(str, Enum):
    """기업 구분명 열거형"""
    PUBLIC = "공기업"
    LARGE = "대기업"
    MID = "중견기업"
    SMALL = "중소기업"
    STARTUP = "스타트업"
    FOREIGN = "외국계"
    ETC = "기타"

class ExperienceLevel(str, Enum):
    """경력 수준 열거형"""
    ENTRY = "신입"
    JUNIOR = "주니어"
    MID = "중급"
    SENIOR = "시니어"
    LEAD = "리드"
    EXECUTIVE = "임원"


class WorkLocationEnum(str, Enum):
    """근무 위치 타입 열거형"""
    ONSITE = "재택근무"
    REMOTE = "원격근무"
    HYBRID = "하이브리드"


class SalaryType(str, Enum):
    """급여 타입 열거형"""
    HOURLY = "시급"
    MONTHLY = "월급"
    ANNUAL = "연봉"


class ValidationStatus(str, Enum):
    """검증 상태 열거형"""
    PENDING = "대기중"
    PASSED = "통과"
    FAILED = "실패"
    REQUIRES_REVIEW = "검토필요"


class SalaryInfo(BaseModel):
    """급여 정보 모델"""
    type: SalaryType = Field(..., description="급여 타입")
    min_amount: Optional[Annotated[float, Field(ge=0)]] = Field(None, description="최소 급여")
    max_amount: Optional[Annotated[float, Field(ge=0)]] = Field(None, description="최대 급여")
    currency: Annotated[str, Field(min_length=3, max_length=3)] = Field("KRW", description="통화 코드")
    is_negotiable: bool = Field(False, description="협의 가능 여부")
    
    @field_validator('max_amount')
    @classmethod
    def validate_max_amount(cls, v, info):
        """최대 급여가 최소 급여보다 큰지 검증"""
        if v is not None and 'min_amount' in info.data and info.data['min_amount'] is not None:
            if v < info.data['min_amount']:
                raise ValueError('최대 급여는 최소 급여보다 크거나 같아야 합니다')
        return v


class WorkLocation(BaseModel):
    """근무 위치 정보 모델"""
    type: WorkLocationEnum = Field(..., description="근무 위치 타입")
    address: Optional[Annotated[str, Field(max_length=200)]] = Field(None, description="주소")
    city: Optional[Annotated[str, Field(max_length=50)]] = Field(None, description="도시")
    country: Annotated[str, Field(max_length=50)] = Field("한국", description="국가")


class CompanyData(BaseModel):
    """기업 정보 모델"""
    company_name: Annotated[str, Field(min_length=1, max_length=100, description="회사명")]
    company_classification: Optional[CompanyClassificationEnum] = Field(None, description="기업구분명")
    homepage: Optional[str] = Field(None, description="홈페이지 URL")
    logo_url: Optional[str] = Field(None, description="로고 이미지 URL")
    intro_summary: Optional[Annotated[str, Field(max_length=100)]] = Field(None, description="기업 요약")
    intro_detail: Optional[Annotated[str, Field(max_length=1000)]] = Field(None, description="기업 상세 소개")
    main_business: Optional[Annotated[str, Field(max_length=1000)]] = Field(None, description="주요사업")

    @field_validator("homepage", "logo_url")
    def validate_url(cls, value: Optional[str]) -> Optional[str]:
        if value:
            try:
                # HttpUrl로 변환해 유효성 검사
                url = HttpUrl(value)
                return str(url)
            except ValueError:
                raise ValueError(f"Invalid URL: {value}")
        return value

    @model_serializer
    def ser_model(self) -> Dict[str, Any]:
        return {
            "company_name": self.company_name,
            "company_classification": self.company_classification,
            "homepage": self.homepage,
            "logo_url": self.logo_url,
            "intro_summary": self.intro_summary,
            "intro_detail": self.intro_detail,
            "main_business": self.main_business,
        }

    class Config:
        """Pydantic 설정"""
        use_enum_values = True
        validate_assignment = True


class UserInput(BaseModel):
    """사용자 입력 구조화를 위한 데이터 모델"""
    job_title: Annotated[str, Field(min_length=1, max_length=100, description="채용 직무명")]
    company_name: Annotated[str, Field(min_length=1, max_length=100, description="회사명")]
    requirements: List[Annotated[str, Field(max_length=200)]] = Field(default_factory=list, description="필수 요구사항")
    preferred_qualifications: List[Annotated[str, Field(max_length=200)]] = Field(default_factory=list, description="우대사항")
    job_type: JobTypeEnum = Field(JobTypeEnum.FULL_TIME, description="채용 형태")
    experience_level: ExperienceLevel = Field(ExperienceLevel.ENTRY, description="경력 수준")
    salary_info: Optional[SalaryInfo] = Field(None, description="급여 정보")
    work_location: Optional[WorkLocation] = Field(None, description="근무 위치")
    additional_info: Optional[List[str]] = Field(default_factory=list, description="추가 정보")
    
    @field_validator('requirements')
    @classmethod
    def validate_requirements(cls, v):
        """요구사항 리스트 검증"""
        if len(v) > 20:
            raise ValueError('요구사항은 최대 20개까지 입력 가능합니다')
        return v


class ValidationResult(BaseModel):
    """검증 결과 모델"""
    status: ValidationStatus = Field(..., description="검증 상태")
    score: Annotated[float, Field(ge=0, le=100)] = Field(..., description="검증 점수")
    issues: List[str] = Field(default_factory=list, description="발견된 문제점들")
    suggestions: List[str] = Field(default_factory=list, description="개선 제안사항")
    validated_at: datetime = Field(default_factory=datetime.now, description="검증 시각")
    validator_type: Annotated[str, Field(max_length=50)] = Field(..., description="검증기 타입")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="검증 메타데이터")


class JobPostingDraft(BaseModel):
    """채용공고 초안 모델
    이 모델은 LLM이 생성하는 채용공고의 구조화된 형태를 정의합니다.
    필수적으로 채워야 하는 필드들은 필수로 채워야 하는 필드로 표시되어 있습니다
    선택 필드의 경우, 제공된 사용자 입력에 정보가 제시되어 있지 않은 경우 None 값으로 채우면 됩니다.
    """
    # === 필수 필드 ===
    title: Annotated[str, Field(min_length=5, max_length=100)] = Field(..., description="채용공고의 제목, 필수로 채워야하는 필드")
    company_name: Annotated[str, Field(min_length=1, max_length=100)] = Field(..., description="회사명, 필수로 채워야하는 필드") 
    job_description: Annotated[str, Field(min_length=20, max_length=3000)] = Field(..., description="직무에 대한 설명, 필수로 채워야하는 필드")
    requirements: List[Annotated[str, Field(max_length=200)]] = Field(..., min_length=1, description="필수 요구사항, 필수로 채워야하는 필드")
    job_type: JobTypeEnum = Field(JobTypeEnum.FULL_TIME, description="채용 형태, 필수로 채워야하는 필드")
    experience_level: ExperienceLevel = Field(ExperienceLevel.ENTRY, description="경력 수준, 필수로 채워야하는 필드")
    # === 선택 필드 ===
    preferred_qualifications: List[Annotated[str, Field(max_length=200)]] = Field(
        default_factory=list, description="우대 사항"
    )
    
    benefits: List[Annotated[str, Field(max_length=200)]] = Field(
        default_factory=list, description="복리후생"
    )
    
    salary_info: Optional[SalaryInfo] = Field(None, description="급여 정보")
    work_location: Optional[WorkLocation] = Field(None, description="근무 위치")
    application_deadline: Optional[date] = Field(None, description="지원 마감일")
    contact_email: Optional[EmailStr] = Field(None, description="담당자 연락처")
    
    class Config:
        """Pydantic 설정"""
        use_enum_values = True

class JobPostingMetadata(BaseModel):
    """채용공고 메타데이터 모델"""
    id: UUID = Field(default_factory=uuid4, description="고유 식별자")
    created_at: datetime = Field(default_factory=datetime.now, description="생성 시각")
    updated_at: datetime = Field(default_factory=datetime.now, description="수정 시각")
    created_by: Optional[str] = Field(None, description="생성자")
    version: Annotated[int, Field(ge=1)] = Field(1, description="버전")
    status: ValidationStatus = Field(ValidationStatus.PENDING, description="현재 상태")
    tags: List[str] = Field(default_factory=list, description="태그 목록")
    
    class Config:
        """Pydantic 설정"""
        use_enum_values = True


class JobPostingTemplate(BaseModel):
    """
    채용공고 템플릿 모델
    
    이 모델은 LLM이 생성하는 채용공고의 구조화된 형태를 정의합니다.
    필수 필드와 선택 필드를 구분하고, 추적을 위한 메타데이터를 포함합니다.
    """
    
    # === 필수 필드 ===
    title: Annotated[str, Field(min_length=5, max_length=100)] = Field(..., description="채용공고 제목")
    company_name: Annotated[str, Field(min_length=1, max_length=100)] = Field(..., description="회사명") 
    job_description: Annotated[str, Field(min_length=20, max_length=3000)] = Field(..., description="직무 설명")
    # === 선택 필드 ===
    preferred_qualifications: List[Annotated[str, Field(max_length=200)]] = Field(
        default_factory=list, description="우대 사항"
    )
    responsibilities: List[Annotated[str, Field(max_length=200)]] = Field(
        default_factory=list, description="주요 업무"
    )
    benefits: List[Annotated[str, Field(max_length=200)]] = Field(
        default_factory=list, description="복리후생"
    )
    job_type: JobTypeEnum = Field(JobTypeEnum.FULL_TIME, description="채용 형태")
    experience_level: ExperienceLevel = Field(ExperienceLevel.ENTRY, description="경력 수준")
    salary_info: Optional[SalaryInfo] = Field(None, description="급여 정보")
    work_location: Optional[WorkLocation] = Field(None, description="근무 위치")
    application_deadline: Optional[date] = Field(None, description="지원 마감일")
    contact_email: Optional[EmailStr] = Field(None, description="담당자 연락처")
    
    # === 추적용 메타데이터 ===
    metadata: JobPostingMetadata = Field(default_factory=JobPostingMetadata, description="메타데이터")
    
    # === 검증 관련 ===
    validation_results: List[ValidationResult] = Field(
        default_factory=list, description="검증 결과들"
    )
    
    # === 생성 정보 ===
    generated_by: Optional[str] = Field(None, description="생성한 LLM 모델명")
    prompt_tokens: Optional[Annotated[int, Field(ge=0)]] = Field(None, description="사용된 프롬프트 토큰 수")
    completion_tokens: Optional[Annotated[int, Field(ge=0)]] = Field(None, description="생성된 완성 토큰 수")
    generation_time: Optional[Annotated[float, Field(ge=0)]] = Field(None, description="생성 소요 시간(초)")
    
    class Config:
        """Pydantic 설정"""
        use_enum_values = True
        validate_assignment = True
        extra = "forbid"  # 정의되지 않은 필드 금지
        
    @field_validator('application_deadline')
    @classmethod
    def validate_deadline(cls, v):
        """지원 마감일이 미래 날짜인지 검증"""
        if v is not None and v <= date.today():
            raise ValueError('지원 마감일은 오늘보다 이후 날짜여야 합니다')
        return v
        
    @model_validator(mode='after')
    def validate_consistency(self) -> Self:
        """모델 전체 일관성 검증"""
        # 급여 정보와 채용 형태 일관성 체크
        if self.salary_info and self.job_type:
            if self.job_type == JobTypeEnum.INTERN and self.salary_info.type == SalaryType.ANNUAL:
                raise ValueError('인턴십은 연봉 정보를 사용할 수 없습니다')
                
        return self
    
    def get_required_fields(self) -> List[str]:
        """필수 필드 목록 반환"""
        return ["title", "company_name", "job_description", "requirements"]
    
    def get_completion_score(self) -> float:
        """완성도 점수 계산 (0~100)"""
        total_fields = len(self.__class__.model_fields)
        filled_fields = sum(1 for field_name, field_info in self.__class__.model_fields.items() 
                          if getattr(self, field_name) is not None)
        
        return (filled_fields / total_fields) * 100
    
    def add_validation_result(self, result: ValidationResult) -> None:
        """검증 결과 추가"""
        self.validation_results.append(result)
        self.metadata.updated_at = datetime.now()
        
        # 상태 업데이트
        if result.status == ValidationStatus.FAILED:
            self.metadata.status = ValidationStatus.FAILED
        elif result.status == ValidationStatus.PASSED and self.metadata.status != ValidationStatus.FAILED:
            self.metadata.status = ValidationStatus.PASSED
    
    def get_latest_validation(self) -> Optional[ValidationResult]:
        """가장 최근 검증 결과 반환"""
        return self.validation_results[-1] if self.validation_results else None
    
    def is_ready_for_publication(self) -> bool:
        """게시 준비 완료 여부 확인"""
        # 필수 필드 모두 채워졌는지 확인
        required_filled = all(getattr(self, field) for field in self.get_required_fields())
        
        # 최근 검증이 통과했는지 확인
        latest_validation = self.get_latest_validation()
        validation_passed = (latest_validation is not None and 
                           latest_validation.status == ValidationStatus.PASSED)
        
        return required_filled and validation_passed
