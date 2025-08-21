"""
채용공고 자동생성 시스템 구조화 로깅 모듈

이 모듈은 structlog를 기반으로 한 구조화된 로깅 시스템을 제공합니다.
개발, 스테이징, 운영 환경에 따른 로깅 설정과 커스텀 로거들을 포함합니다.
"""

import sys
import os
import json
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime, timezone
from pathlib import Path

import structlog
from structlog.typing import FilteringBoundLogger, Processor


class JobPostingLogFormatter:
    """
    채용공고 시스템 전용 로그 포맷터
    
    구조화된 로그 메시지를 JSON 형태로 포맷팅하고,
    시스템 특화 필드들을 추가합니다.
    """
    
    @staticmethod
    def add_timestamp(
        logger: FilteringBoundLogger, 
        method_name: str, 
        event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """타임스탬프 추가"""
        event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
        return event_dict
    
    @staticmethod
    def add_log_level(
        logger: FilteringBoundLogger,
        method_name: str,
        event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """로그 레벨 추가"""
        event_dict["level"] = method_name.upper()
        return event_dict
    
    @staticmethod
    def add_service_info(
        logger: FilteringBoundLogger,
        method_name: str,
        event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """서비스 정보 추가"""
        event_dict.setdefault("service", "job-posting-autogen")
        event_dict.setdefault("version", "1.0.0")
        return event_dict
    
    @staticmethod
    def filter_sensitive_data(
        logger: FilteringBoundLogger,
        method_name: str,
        event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """민감한 데이터 필터링"""
        sensitive_keys = {
            "password", "token", "api_key", "secret", 
            "auth_token", "access_token", "refresh_token"
        }
        
        def _filter_dict(data: Dict[str, Any]) -> Dict[str, Any]:
            filtered = {}
            for key, value in data.items():
                if key.lower() in sensitive_keys:
                    filtered[key] = "***REDACTED***"
                elif isinstance(value, dict):
                    filtered[key] = _filter_dict(value)
                else:
                    filtered[key] = value
            return filtered
        
        return _filter_dict(event_dict)


class LogContextManager:
    """
    로그 컨텍스트 관리자
    
    요청별, 작업별 컨텍스트 정보를 추가하여 로그 추적을 용이하게 합니다.
    """
    
    def __init__(self):
        self._context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs) -> None:
        """컨텍스트 정보 설정"""
        self._context.update(kwargs)
    
    def clear_context(self) -> None:
        """컨텍스트 정보 초기화"""
        self._context.clear()
    
    def get_context(self) -> Dict[str, Any]:
        """현재 컨텍스트 반환"""
        return self._context.copy()
    
    def context_processor(
        self,
        logger: FilteringBoundLogger,
        method_name: str,
        event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """컨텍스트 정보를 이벤트 딕셔너리에 추가"""
        event_dict.update(self._context)
        return event_dict


# 전역 컨텍스트 관리자
_context_manager = LogContextManager()


def setup_logging(
    level: str = "INFO",
    environment: str = "development",
    log_file: Optional[str] = None,
    structured: bool = True
) -> FilteringBoundLogger:
    """
    로깅 시스템 초기 설정
    
    Args:
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        environment: 실행 환경 (development, staging, production)
        log_file: 로그 파일 경로 (None이면 콘솔만 출력)
        structured: 구조화된 로깅 사용 여부
        
    Returns:
        설정된 structlog 로거
    """
    
    # 로그 레벨 설정
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # 기본 프로세서들
    processors: list[Processor] = [
        JobPostingLogFormatter.add_timestamp,
        JobPostingLogFormatter.add_log_level,
        JobPostingLogFormatter.add_service_info,
        _context_manager.context_processor,
        JobPostingLogFormatter.filter_sensitive_data,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # 환경별 설정
    if environment == "production":
        # 운영 환경: JSON 출력, 더 적은 로그
        processors.append(structlog.processors.JSONRenderer())
    elif environment == "staging":
        # 스테이징 환경: JSON 출력, 개발용 정보 포함
        processors.extend([
            structlog.dev.set_exc_info,
            structlog.processors.JSONRenderer()
        ])
    else:  # development
        # 개발 환경: 컬러 출력, 자세한 정보
        processors.extend([
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer() if structured else structlog.processors.JSONRenderer()
        ])
    
    # structlog 설정
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # 표준 라이브러리 로깅 설정
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    
    # 파일 핸들러 추가 (옵션)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
    
    return structlog.get_logger()


def get_logger(name: str = __name__) -> FilteringBoundLogger:
    """
    named 로거 반환
    
    Args:
        name: 로거 이름
        
    Returns:
        structlog 로거 인스턴스
    """
    return structlog.get_logger(name)


def set_log_context(**kwargs) -> None:
    """
    로그 컨텍스트 설정
    
    Args:
        **kwargs: 컨텍스트로 설정할 키-값 쌍들
    """
    _context_manager.set_context(**kwargs)


def clear_log_context() -> None:
    """로그 컨텍스트 초기화"""
    _context_manager.clear_context()


def get_log_context() -> Dict[str, Any]:
    """현재 로그 컨텍스트 반환"""
    return _context_manager.get_context()


class LogContextDecorator:
    """
    함수 실행시 로그 컨텍스트를 자동으로 설정하는 데코레이터
    """
    
    def __init__(self, **context_kwargs):
        self.context_kwargs = context_kwargs
    
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            # 기존 컨텍스트 백업
            original_context = get_log_context()
            
            try:
                # 새 컨텍스트 설정
                set_log_context(
                    function_name=func.__name__,
                    **self.context_kwargs
                )
                
                logger = get_logger(func.__module__)
                logger.debug(
                    "함수 실행 시작",
                    function=func.__name__,
                    args=args,
                    kwargs=kwargs
                )
                
                result = func(*args, **kwargs)
                
                logger.debug(
                    "함수 실행 완료", 
                    function=func.__name__
                )
                
                return result
                
            except Exception as e:
                logger = get_logger(func.__module__)
                logger.error(
                    "함수 실행 중 오류 발생",
                    function=func.__name__,
                    error=str(e),
                    exc_info=True
                )
                raise
                
            finally:
                # 원래 컨텍스트 복원
                clear_log_context()
                set_log_context(**original_context)
        
        return wrapper


# 자주 사용되는 로거들
workflow_logger = get_logger("workflows")
llm_logger = get_logger("llm") 
database_logger = get_logger("database")
api_logger = get_logger("api")
validation_logger = get_logger("validation")


def log_performance(
    operation: str,
    start_time: datetime,
    end_time: Optional[datetime] = None,
    **additional_data
) -> None:
    """
    성능 로깅 유틸리티
    
    Args:
        operation: 작업명
        start_time: 시작 시간
        end_time: 종료 시간 (None이면 현재 시간)
        **additional_data: 추가 로깅 데이터
    """
    if end_time is None:
        end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    
    perf_logger = get_logger("performance")
    perf_logger.info(
        "성능 메트릭",
        operation=operation,
        duration_seconds=duration,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        **additional_data
    )


def log_llm_interaction(
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    response_time: float,
    cost: Optional[float] = None,
    **additional_data
) -> None:
    """
    LLM 상호작용 로깅 유틸리티
    
    Args:
        model_name: 사용된 모델명
        prompt_tokens: 프롬프트 토큰 수
        completion_tokens: 완성 토큰 수
        response_time: 응답 시간
        cost: 비용 (옵션)
        **additional_data: 추가 로깅 데이터
    """
    llm_logger.info(
        "LLM 상호작용",
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        response_time=response_time,
        cost=cost,
        **additional_data
    )


def log_validation_result(
    validator_type: str,
    status: str,
    score: float,
    issues: list,
    **additional_data
) -> None:
    """
    검증 결과 로깅 유틸리티
    
    Args:
        validator_type: 검증기 타입
        status: 검증 상태
        score: 검증 점수
        issues: 발견된 문제들
        **additional_data: 추가 로깅 데이터
    """
    validation_logger.info(
        "검증 결과",
        validator_type=validator_type,
        status=status,
        score=score,
        issue_count=len(issues),
        issues=issues,
        **additional_data
    )


# 환경 변수에서 로깅 설정 읽기
def configure_logging_from_env() -> FilteringBoundLogger:
    """
    환경 변수에서 로깅 설정을 읽어서 구성
    
    Environment Variables:
        LOG_LEVEL: 로그 레벨 (default: INFO)
        LOG_ENVIRONMENT: 환경 (default: development)  
        LOG_FILE: 로그 파일 경로 (optional)
        LOG_STRUCTURED: 구조화된 로깅 사용 (default: true)
        
    Returns:
        설정된 로거
    """
    level = os.getenv("LOG_LEVEL", "INFO")
    environment = os.getenv("LOG_ENVIRONMENT", "development")
    log_file = os.getenv("LOG_FILE")
    structured = os.getenv("LOG_STRUCTURED", "true").lower() == "true"
    
    return setup_logging(
        level=level,
        environment=environment,
        log_file=log_file,
        structured=structured
    )


# 기본 로거 인스턴스 (모듈 로드시 자동 설정)
logger = configure_logging_from_env()
