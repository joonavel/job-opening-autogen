"""
중앙화된 애플리케이션 설정 관리

이 모듈은 모든 애플리케이션 설정을 중앙에서 관리합니다.
환경변수를 통해 설정값을 로드하고, Pydantic을 사용하여 타입 안전성을 보장합니다.
"""

from typing import Optional, Literal, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from pathlib import Path
import os


class DatabaseSettings(BaseSettings):
    """데이터베이스 관련 설정"""
    
    url: str = Field(
        default="postgresql://postgres:postgres123@localhost:5432/job_openings_db",
        description="데이터베이스 연결 URL"
    )
    echo: bool = Field(default=False, description="SQLAlchemy SQL 쿼리 로깅")
    pool_size: int = Field(default=20, description="연결 풀 크기")
    max_overflow: int = Field(default=30, description="최대 오버플로우 연결 수")
    pool_timeout: int = Field(default=30, description="연결 풀 타임아웃 (초)")
    
    class Config:
        env_prefix = "DATABASE_"


class RedisSettings(BaseSettings):
    """Redis 관련 설정"""
    
    url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis 연결 URL"
    )
    encoding: str = Field(default="utf-8", description="인코딩")
    decode_responses: bool = Field(default=True, description="응답 디코딩")
    max_connections: int = Field(default=50, description="최대 연결 수")
    
    class Config:
        env_prefix = "REDIS_"


class LLMSettings(BaseSettings):
    """LLM 관련 설정"""
    
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API 키")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API 키")
    
    primary_provider: Literal["openai", "anthropic"] = Field(
        default="openai", 
        description="주 LLM 제공자"
    )
    secondary_provider: Literal["openai", "anthropic"] = Field(
        default="anthropic",
        description="보조 LLM 제공자"
    )
    
    model_name: str = Field(default="gpt-4o-mini", description="사용할 모델명")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="생성 온도")
    max_tokens: int = Field(default=2048, gt=0, description="최대 토큰 수")
    timeout: int = Field(default=30, description="API 타임아웃 (초)")
    max_retries: int = Field(default=3, description="최대 재시도 횟수")
    
    @field_validator('primary_provider', 'secondary_provider')
    @classmethod
    def validate_providers(cls, v):
        if v not in ["openai", "anthropic"]:
            raise ValueError("Provider must be 'openai' or 'anthropic'")
        return v
    
    class Config:
        env_prefix = "LLM_"


class APISettings(BaseSettings):
    """API 서버 관련 설정"""
    
    host: str = Field(default="0.0.0.0", description="서버 호스트")
    port: int = Field(default=8000, description="서버 포트")
    reload: bool = Field(default=True, description="자동 리로드")
    workers: int = Field(default=1, description="워커 프로세스 수")
    
    # Security
    secret_key: str = Field(
        default="change-this-secret-key-in-production",
        description="JWT 서명용 비밀키"
    )
    algorithm: str = Field(default="HS256", description="JWT 알고리즘")
    access_token_expire_minutes: int = Field(
        default=30, 
        description="액세스 토큰 만료 시간 (분)"
    )
    
    class Config:
        env_prefix = "API_"


class CacheSettings(BaseSettings):
    """캐싱 관련 설정"""
    
    ttl_seconds: int = Field(default=86400, description="기본 TTL (초)")
    prefix: str = Field(default="job_autogen", description="캐시 키 접두사")
    enabled: bool = Field(default=True, description="캐싱 활성화")
    
    # 특정 캐시 TTL 설정
    company_data_ttl: int = Field(default=86400, description="기업 정보 캐시 TTL")
    template_ttl: int = Field(default=604800, description="템플릿 캐시 TTL (7일)")
    prompt_ttl: int = Field(default=3600, description="프롬프트 캐시 TTL")
    
    class Config:
        env_prefix = "CACHE_"


class HumanLoopSettings(BaseSettings):
    """Human-in-the-Loop 관련 설정"""
    
    session_timeout: int = Field(
        default=3600,
        description="피드백 세션 타임아웃 (초)"
    )
    max_retry_count: int = Field(
        default=3,
        description="최대 재시도 횟수"
    )
    cleanup_interval: int = Field(
        default=300,
        description="만료된 세션 정리 간격 (초)"
    )
    
    class Config:
        env_prefix = "HUMAN_LOOP_"


class PerformanceSettings(BaseSettings):
    """성능 관련 설정"""
    
    max_concurrent_requests: int = Field(
        default=10,
        description="최대 동시 요청 수"
    )
    request_timeout: int = Field(
        default=30,
        description="요청 타임아웃 (초)"
    )
    streaming_chunk_size: int = Field(
        default=1024,
        description="스트리밍 청크 크기"
    )
    
    class Config:
        env_prefix = "PERFORMANCE_"


class FeatureFlags(BaseSettings):
    """기능 플래그 설정"""
    
    enable_streaming: bool = Field(default=True, description="스트리밍 활성화")
    enable_caching: bool = Field(default=True, description="캐싱 활성화")
    enable_fallback: bool = Field(default=True, description="Fallback 활성화")
    enable_monitoring: bool = Field(default=True, description="모니터링 활성화")
    
    class Config:
        env_prefix = "ENABLE_"


class LoggingSettings(BaseSettings):
    """로깅 관련 설정"""
    
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="로그 레벨"
    )
    format: Literal["json", "text"] = Field(
        default="json",
        description="로그 포맷"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="로그 파일 경로 (None이면 stdout)"
    )
    max_file_size: int = Field(
        default=10485760,  # 10MB
        description="로그 파일 최대 크기 (바이트)"
    )
    backup_count: int = Field(
        default=5,
        description="로그 파일 백업 개수"
    )
    
    class Config:
        env_prefix = "LOG_"


class Settings(BaseSettings):
    """메인 설정 클래스"""
    
    # Environment
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="실행 환경"
    )
    
    # Project info
    project_name: str = Field(
        default="Job Opening AutoGen",
        description="프로젝트 이름"
    )
    version: str = Field(default="1.0.0", description="버전")
    description: str = Field(
        default="GenAI 기반 채용공고 자동 생성 서비스",
        description="프로젝트 설명"
    )
    
    # Sub-settings
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    llm: LLMSettings = LLMSettings()
    api: APISettings = APISettings()
    cache: CacheSettings = CacheSettings()
    human_loop: HumanLoopSettings = HumanLoopSettings()
    performance: PerformanceSettings = PerformanceSettings()
    features: FeatureFlags = FeatureFlags()
    logging: LoggingSettings = LoggingSettings()
    
    # Paths
    @property
    def project_root(self) -> Path:
        """프로젝트 루트 디렉토리"""
        return Path(__file__).parent.parent
    
    @property
    def src_path(self) -> Path:
        """소스 코드 디렉토리"""
        return self.project_root / "src"
    
    @property
    def config_path(self) -> Path:
        """설정 디렉토리"""
        return self.project_root / "config"
    
    @property
    def data_path(self) -> Path:
        """데이터 디렉토리"""
        return self.project_root / "data"
    
    @property
    def prompts_path(self) -> Path:
        """프롬프트 템플릿 디렉토리"""
        return self.config_path / "prompts"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 필수 디렉토리 생성
        self.prompts_path.mkdir(exist_ok=True)
    
    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v):
        if v not in ["development", "staging", "production"]:
            raise ValueError("Environment must be development, staging, or production")
        return v
    
    @property
    def is_development(self) -> bool:
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # 정의되지 않은 환경변수 무시


# Global settings instance
settings = Settings()

# Backward compatibility
PROJECT_ROOT = settings.project_root


def get_settings() -> Settings:
    """설정 인스턴스 반환 (FastAPI dependency injection용)"""
    return settings
