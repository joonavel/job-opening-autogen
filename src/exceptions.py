"""
채용공고 자동생성 시스템 커스텀 예외 클래스들

이 모듈은 시스템에서 발생할 수 있는 다양한 예외 상황들을 처리하기 위한
구조화된 예외 클래스들을 정의합니다.
"""

from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class ErrorSeverity(str, Enum):
    """에러 심각도 레벨"""
    LOW = "낮음"
    MEDIUM = "중간"  
    HIGH = "높음"
    CRITICAL = "치명적"


class ErrorCategory(str, Enum):
    """에러 카테고리"""
    VALIDATION = "검증"
    LLM = "언어모델"
    DATABASE = "데이터베이스"
    NETWORK = "네트워크"
    AUTH = "인증"
    BUSINESS_LOGIC = "비즈니스로직"
    SYSTEM = "시스템"


class BaseJobPostingError(Exception):
    """
    채용공고 시스템 기본 예외 클래스
    
    모든 커스텀 예외는 이 클래스를 상속받아 구현됩니다.
    에러 추적과 디버깅을 위한 공통 기능을 제공합니다.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self._generate_error_code()
        self.severity = severity
        self.category = category
        self.details = details or {}
        self.suggestions = suggestions or []
        
    def _generate_error_code(self) -> str:
        """에러 코드 자동 생성"""
        class_name = self.__class__.__name__
        return f"{class_name.upper()}_001"
    
    def to_dict(self) -> Dict[str, Any]:
        """예외 정보를 딕셔너리로 변환"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "severity": self.severity.value,
            "category": self.category.value,
            "details": self.details,
            "suggestions": self.suggestions
        }
    
    def __str__(self) -> str:
        return f"[{self.error_code}] {self.category.value} 오류: {self.message}"


class ValidationError(BaseJobPostingError):
    """
    데이터 검증 관련 예외
    
    Pydantic 모델 검증, 입력 데이터 유효성 검사 등에서 발생하는 예외를 처리합니다.
    """
    
    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Any = None,
        validation_errors: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            **kwargs
        )
        self.field_name = field_name
        self.field_value = field_value
        self.validation_errors = validation_errors or []
        
        if field_name:
            self.details.update({
                "field_name": field_name,
                "field_value": field_value,
                "validation_errors": self.validation_errors
            })


class LLMError(BaseJobPostingError):
    """
    LLM (Large Language Model) 관련 예외
    
    LLM API 호출, 응답 처리, 토큰 제한 등에서 발생하는 예외를 처리합니다.
    """
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        response_time: Optional[float] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.LLM,
            **kwargs
        )
        self.model_name = model_name
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.response_time = response_time
        
        self.details.update({
            "model_name": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "response_time": response_time
        })


class LLMTimeoutError(LLMError):
    """LLM 요청 타임아웃 예외"""
    
    def __init__(self, timeout_seconds: float, **kwargs):
        super().__init__(
            f"LLM 요청이 {timeout_seconds}초 내에 완료되지 않았습니다",
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.timeout_seconds = timeout_seconds
        self.details["timeout_seconds"] = timeout_seconds
        self.suggestions.extend([
            "타임아웃 설정 시간을 늘려보세요",
            "프롬프트 길이를 줄여보세요",
            "다른 LLM 모델을 사용해보세요"
        ])


class LLMQuotaExceededError(LLMError):
    """LLM API 할당량 초과 예외"""
    
    def __init__(self, quota_type: str = "requests", **kwargs):
        super().__init__(
            f"LLM API {quota_type} 할당량이 초과되었습니다",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )
        self.quota_type = quota_type
        self.details["quota_type"] = quota_type
        self.suggestions.extend([
            "API 키의 할당량을 확인하세요",
            "요청 빈도를 줄여보세요",
            "다른 API 키를 사용해보세요"
        ])


class DatabaseError(BaseJobPostingError):
    """
    데이터베이스 관련 예외
    
    DB 연결, 쿼리 실행, 트랜잭션 등에서 발생하는 예외를 처리합니다.
    """
    
    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        table_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.DATABASE,
            **kwargs
        )
        self.query = query
        self.table_name = table_name
        
        if query:
            self.details["query"] = query
        if table_name:
            self.details["table_name"] = table_name


class DatabaseConnectionError(DatabaseError):
    """데이터베이스 연결 실패 예외"""
    
    def __init__(self, host: str, port: int, database: str, **kwargs):
        super().__init__(
            f"데이터베이스 연결 실패: {host}:{port}/{database}",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )
        self.host = host
        self.port = port
        self.database = database
        self.details.update({
            "host": host,
            "port": port,
            "database": database
        })
        self.suggestions.extend([
            "데이터베이스 서버가 실행 중인지 확인하세요",
            "연결 정보(호스트, 포트, 사용자명, 비밀번호)를 확인하세요",
            "네트워크 연결을 확인하세요"
        ])


class NetworkError(BaseJobPostingError):
    """
    네트워크 관련 예외
    
    API 호출, HTTP 요청 등에서 발생하는 네트워크 예외를 처리합니다.
    """
    
    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            **kwargs
        )
        self.url = url
        self.status_code = status_code
        
        if url:
            self.details["url"] = url
        if status_code:
            self.details["status_code"] = status_code


class AuthenticationError(BaseJobPostingError):
    """
    인증 관련 예외
    
    API 키 검증, 사용자 인증 등에서 발생하는 예외를 처리합니다.
    """
    
    def __init__(self, message: str, auth_type: str = "API", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.AUTH,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.auth_type = auth_type
        self.details["auth_type"] = auth_type
        self.suggestions.extend([
            "API 키나 인증 토큰을 확인하세요",
            "인증 정보의 유효 기간을 확인하세요"
        ])


class BusinessLogicError(BaseJobPostingError):
    """
    비즈니스 로직 관련 예외
    
    채용공고 생성 규칙, 워크플로우 제약 등 비즈니스 로직에서 발생하는 예외를 처리합니다.
    """
    
    def __init__(self, message: str, rule_name: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.BUSINESS_LOGIC,
            **kwargs
        )
        self.rule_name = rule_name
        if rule_name:
            self.details["rule_name"] = rule_name


class WorkflowError(BusinessLogicError):
    """워크플로우 실행 중 발생하는 예외"""
    
    def __init__(
        self,
        message: str,
        workflow_step: Optional[str] = None,
        state_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.workflow_step = workflow_step
        self.state_data = state_data or {}
        
        self.details.update({
            "workflow_step": workflow_step,
            "state_data": state_data
        })


class ContentModerationError(BusinessLogicError):
    """콘텐츠 조정(민감 정보 감지) 관련 예외"""
    
    def __init__(
        self,
        message: str,
        flagged_content: Optional[List[str]] = None,
        severity_score: Optional[float] = None,
        **kwargs
    ):
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.flagged_content = flagged_content or []
        self.severity_score = severity_score
        
        self.details.update({
            "flagged_content": self.flagged_content,
            "severity_score": severity_score
        })
        self.suggestions.extend([
            "플래그된 콘텐츠를 수정하거나 제거하세요",
            "더 중립적인 표현을 사용해보세요"
        ])


class ConfigurationError(BaseJobPostingError):
    """시스템 설정 관련 예외"""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        expected_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.config_key = config_key
        self.expected_type = expected_type
        
        if config_key:
            self.details.update({
                "config_key": config_key,
                "expected_type": expected_type
            })
        self.suggestions.extend([
            "환경 변수나 설정 파일을 확인하세요",
            "설정값의 형식이 올바른지 확인하세요"
        ])


class CacheError(BaseJobPostingError):
    """캐시 시스템 관련 예외"""
    
    def __init__(
        self,
        message: str,
        cache_key: Optional[str] = None,
        cache_type: str = "Redis",
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.SYSTEM,
            **kwargs
        )
        self.cache_key = cache_key
        self.cache_type = cache_type
        
        self.details.update({
            "cache_key": cache_key,
            "cache_type": cache_type
        })


# 예외 매핑 딕셔너리 (에러 코드로 예외 클래스 찾기)
ERROR_CODE_MAPPING = {
    "VALIDATION_ERROR": ValidationError,
    "LLM_ERROR": LLMError,
    "LLM_TIMEOUT": LLMTimeoutError,
    "LLM_QUOTA_EXCEEDED": LLMQuotaExceededError,
    "DATABASE_ERROR": DatabaseError,
    "DATABASE_CONNECTION_ERROR": DatabaseConnectionError,
    "NETWORK_ERROR": NetworkError,
    "AUTH_ERROR": AuthenticationError,
    "BUSINESS_LOGIC_ERROR": BusinessLogicError,
    "WORKFLOW_ERROR": WorkflowError,
    "CONTENT_MODERATION_ERROR": ContentModerationError,
    "CONFIGURATION_ERROR": ConfigurationError,
    "CACHE_ERROR": CacheError,
}


def create_error_response(error: BaseJobPostingError) -> Dict[str, Any]:
    """
    예외 객체로부터 표준화된 에러 응답을 생성합니다.
    
    Args:
        error: 기본 예외 클래스의 인스턴스
        
    Returns:
        표준화된 에러 응답 딕셔너리
    """
    return {
        "success": False,
        "error": error.to_dict(),
        "timestamp": str(datetime.now()),
        "suggestions": error.suggestions
    }


def handle_pydantic_validation_error(pydantic_error) -> ValidationError:
    """
    Pydantic ValidationError를 커스텀 ValidationError로 변환합니다.
    
    Args:
        pydantic_error: Pydantic의 ValidationError 인스턴스
        
    Returns:
        커스텀 ValidationError 인스턴스
    """
    errors = []
    for error in pydantic_error.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        msg = error["msg"]
        errors.append(f"{field}: {msg}")
    
    return ValidationError(
        "데이터 검증에 실패했습니다",
        validation_errors=errors,
        details={"pydantic_errors": pydantic_error.errors()}
    )
