"""
LLM 클라이언트 통합 래퍼

이 모듈은 OpenAI와 Anthropic API를 통합하여 관리하는 클라이언트를 제공합니다.
- LangChain의 with_structured_output() 메소드 활용
- 에러 처리 및 재시도 로직
- 토큰 사용량 추적
- Fallback 전략 구현
"""

import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional, Type, Union, List, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field
import openai
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnablePassthrough
from langchain_core.exceptions import LangChainException

from ..models.job_posting import UserInput, JobPostingTemplate
from ..exceptions import LLMError, ValidationError

logger = logging.getLogger(__name__)

# 🔍 프로젝트 루트에서 .env 파일 로드
project_root = Path(__file__).parent.parent.parent  # src/components/llm_client.py -> 프로젝트 루트
env_path = project_root / ".env"
load_result = load_dotenv(env_path, override=True)
logger.info(f"🔍 .env 파일 로드 - 경로: {env_path}, 성공: {load_result}, 파일 존재: {env_path.exists()}")

class LLMProvider(str, Enum):
    """LLM 제공업체 열거형"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class ModelType(str, Enum):
    """모델 타입 열거형"""
    # OpenAI 모델
    GPT_O3_MINI = "gpt-o3-mini"
    GPT_5_MINI = "gpt-5-mini"
    GPT_5 = "gpt-5"
    
    # Anthropic 모델
    CLAUDE_4_1_OPUS = "claude-opus-4-1-20250805"
    CLAUDE_4_SONNET = "claude-sonnet-4-20250514" 
    CLAUDE_3_5_HAIKU = "claude-3-5-haiku-latest"


@dataclass
class LLMUsageStats:
    """LLM 사용량 통계"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0
    total_cost: float = 0.0
    generation_time: float = 0.0


@dataclass
class LLMConfig:
    """LLM 설정"""
    provider: LLMProvider
    model: ModelType
    temperature: float = 0.1
    max_tokens: int = 6000  # 토큰 제한 확대
    max_retries: int = 3
    timeout: int = 60
    api_key: Optional[str] = None
    
    def __post_init__(self):
        """API 키 환경변수에서 자동 설정"""
        if not self.api_key:
            if self.provider == LLMProvider.OPENAI:
                self.api_key = os.getenv("OPENAI_API_KEY")
            elif self.provider == LLMProvider.ANTHROPIC:
                self.api_key = os.getenv("ANTHROPIC_API_KEY")


class BaseLLMClient(ABC):
    """기본 LLM 클라이언트 인터페이스"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.stats = LLMUsageStats()
        self.client = None
        self._initialize_client()
    
    @abstractmethod
    def _initialize_client(self):
        """클라이언트 초기화 추상 메서드"""
        pass
    
    @abstractmethod
    def generate_structured_output(self, 
                                 system_prompt: str, 
                                 user_prompt: str, 
                                 output_schema: Type[BaseModel],
                                 **kwargs) -> BaseModel:
        """구조화된 출력 생성 추상 메서드"""
        pass
    
    def get_stats(self) -> LLMUsageStats:
        """사용량 통계 반환"""
        return self.stats


class OpenAIClient(BaseLLMClient):
    """OpenAI LLM 클라이언트"""
    
    def _initialize_client(self):
        """OpenAI 클라이언트 초기화"""
        try:
            if not self.config.api_key:
                raise LLMError("OpenAI API 키가 설정되지 않았습니다")
                
            self.client = ChatOpenAI(
                model=self.config.model.value,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens, # type: ignore
                max_retries=self.config.max_retries,
                timeout=self.config.timeout,
                api_key=self.config.api_key
            )
            
            logger.info(f"OpenAI 클라이언트 초기화 완료: {self.config.model.value}")
            
        except Exception as e:
            logger.error(f"OpenAI 클라이언트 초기화 실패: {str(e)}")
            raise LLMError(f"OpenAI 클라이언트 초기화 실패: {str(e)}")
    
    def generate_structured_output(self, 
                                 system_prompt: str, 
                                 user_prompt: str, 
                                 output_schema: Type[BaseModel],
                                 **kwargs) -> BaseModel:
        """구조화된 출력 생성"""
        start_time = time.time()
        
        try:
            logger.info(f"OpenAI 구조화된 출력 생성 시작: {output_schema.__name__}")
            
            # with_structured_output을 사용하여 구조화된 출력 생성
            structured_llm = self.client.with_structured_output(output_schema)
            
            # 메시지 구성
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # LLM 호출
            result = structured_llm.invoke(messages)

            # 타입 변환: 딕셔너리인 경우 Pydantic 모델로 변환
            if isinstance(result, dict):
                result = output_schema(**result)
            elif not isinstance(result, BaseModel):
                raise LLMError(f"예상치 못한 반환 타입: {type(result)}")

            # 통계 업데이트
            generation_time = time.time() - start_time
            self.stats.request_count += 1
            self.stats.generation_time += generation_time

            # 토큰 사용량은 실제 구현에서 response.usage_metadata 등을 통해 추출해야 함
            # 현재는 임시로 추정값 사용
            estimated_prompt_tokens = len(system_prompt + user_prompt) // 4
            estimated_completion_tokens = 500  # 임시 추정값

            self.stats.prompt_tokens += estimated_prompt_tokens
            self.stats.completion_tokens += estimated_completion_tokens
            self.stats.total_tokens += estimated_prompt_tokens + estimated_completion_tokens

            logger.info(f"OpenAI 구조화된 출력 생성 완료 ({generation_time:.2f}초)")

            return result
            
        except Exception as e:
            logger.error(f"OpenAI 구조화된 출력 생성 실패: {str(e)}")
            raise LLMError(f"OpenAI 구조화된 출력 생성 실패: {str(e)}")


class AnthropicClient(BaseLLMClient):
    """Anthropic LLM 클라이언트"""
    
    def _initialize_client(self):
        """Anthropic 클라이언트 초기화"""
        try:
            if not self.config.api_key:
                raise LLMError("Anthropic API 키가 설정되지 않았습니다")
                
            self.client = ChatAnthropic(
                model=self.config.model.value, # type: ignore
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens, # type: ignore
                max_retries=self.config.max_retries,
                timeout=self.config.timeout,
                api_key=self.config.api_key
            ) # type: ignore
            
            logger.info(f"Anthropic 클라이언트 초기화 완료: {self.config.model.value}")
            
        except Exception as e:
            logger.error(f"Anthropic 클라이언트 초기화 실패: {str(e)}")
            raise LLMError(f"Anthropic 클라이언트 초기화 실패: {str(e)}")
    
    def generate_structured_output(self, 
                                 system_prompt: str, 
                                 user_prompt: str, 
                                 output_schema: Type[BaseModel],
                                 **kwargs) -> BaseModel:
        """구조화된 출력 생성"""
        start_time = time.time()
        
        try:
            logger.info(f"Anthropic 구조화된 출력 생성 시작: {output_schema.__name__}")
            
            # with_structured_output을 사용하여 구조화된 출력 생성
            structured_llm = self.client.with_structured_output(output_schema)
            
            # 메시지 구성
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # LLM 호출
            result = structured_llm.invoke(messages)

            # 타입 변환: 딕셔너리인 경우 Pydantic 모델로 변환
            if isinstance(result, dict):
                result = output_schema(**result)
            elif not isinstance(result, BaseModel):
                raise LLMError(f"예상치 못한 반환 타입: {type(result)}")

            # 통계 업데이트
            generation_time = time.time() - start_time
            self.stats.request_count += 1
            self.stats.generation_time += generation_time

            # 토큰 사용량은 실제 구현에서 response.usage_metadata 등을 통해 추출해야 함
            # 현재는 임시로 추정값 사용
            estimated_prompt_tokens = len(system_prompt + user_prompt) // 4
            estimated_completion_tokens = 500  # 임시 추정값

            self.stats.prompt_tokens += estimated_prompt_tokens
            self.stats.completion_tokens += estimated_completion_tokens
            self.stats.total_tokens += estimated_prompt_tokens + estimated_completion_tokens

            logger.info(f"Anthropic 구조화된 출력 생성 완료 ({generation_time:.2f}초)")

            return result
            
        except Exception as e:
            logger.error(f"Anthropic 구조화된 출력 생성 실패: {str(e)}")
            raise LLMError(f"Anthropic 구조화된 출력 생성 실패: {str(e)}")


class LLMClientManager:
    """
    통합 LLM 클라이언트 관리자
    
    여러 LLM 제공업체를 관리하고 Fallback 전략을 구현합니다.
    """
    
    def __init__(self):
        self.clients: Dict[str, BaseLLMClient] = {}
        self.primary_client: Optional[BaseLLMClient] = None
        self.fallback_clients: List[BaseLLMClient] = []
        self._initialize_default_clients()
    
    def _initialize_default_clients(self):
        """기본 클라이언트들 초기화"""
        try:
            # 🔍 디버깅: 환경변수 상태 확인
            openai_key = os.getenv("OPENAI_API_KEY")
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            logger.info(f"🔍 환경변수 확인 - OPENAI_API_KEY: {'있음' if openai_key else '없음'}, ANTHROPIC_API_KEY: {'있음' if anthropic_key else '없음'}")
            
            # OpenAI 클라이언트 (Primary)
            if openai_key:
                openai_config = LLMConfig(
                    provider=LLMProvider.OPENAI,
                    model=ModelType.GPT_5_MINI,
                    temperature=0.1,
                    max_tokens=6000
                )
                openai_client = OpenAIClient(openai_config)
                self.clients["openai"] = openai_client
                self.primary_client = openai_client
                logger.info("OpenAI 클라이언트가 Primary로 설정됨")
            
            # Anthropic 클라이언트 (Fallback)
            if anthropic_key:
                anthropic_config = LLMConfig(
                    provider=LLMProvider.ANTHROPIC,
                    model=ModelType.CLAUDE_4_SONNET,
                    temperature=0.1,
                    max_tokens=6000
                )
                anthropic_client = AnthropicClient(anthropic_config)
                self.clients["anthropic"] = anthropic_client
                self.fallback_clients.append(anthropic_client)
                logger.info("Anthropic 클라이언트가 Fallback으로 설정됨")
            
            # 🔍 디버깅: 최종 클라이언트 상태 확인
            logger.info(f"🔍 클라이언트 초기화 완료 - Primary: {'있음' if self.primary_client else '없음'}, Fallback: {len(self.fallback_clients)}개")
                
        except Exception as e:
            logger.warning(f"일부 클라이언트 초기화 실패: {str(e)}")
    
    def add_client(self, name: str, client: BaseLLMClient, is_primary: bool = False):
        """클라이언트 추가"""
        self.clients[name] = client
        
        if is_primary:
            self.primary_client = client
        else:
            self.fallback_clients.append(client)
        
        logger.info(f"클라이언트 추가: {name} ({'Primary' if is_primary else 'Fallback'})")
    
    def generate_structured_output(self, 
                                 system_prompt: str, 
                                 user_prompt: str, 
                                 output_schema: Type[BaseModel],
                                 **kwargs) -> Tuple[BaseModel, str]:
        """구조화된 출력 생성 (Fallback 전략 포함)"""
        
        # 🔍 디버깅: 메소드 호출 확인
        logger.info(f"🔍 generate_structured_output 호출됨 - Primary: {'있음' if self.primary_client else '없음'}, Fallback: {len(self.fallback_clients)}개")
        
        # Primary 클라이언트 시도
        if self.primary_client:
            try:
                logger.info("Primary 클라이언트로 구조화된 출력 생성 시도")
                return self.primary_client.generate_structured_output(
                    system_prompt, user_prompt, output_schema, **kwargs
                ), self.primary_client.config.model.value
            except Exception as e:
                logger.warning(f"Primary 클라이언트 실패: {str(e)}")
        
        # Fallback 클라이언트들 순차 시도
        for i, client in enumerate(self.fallback_clients):
            try:
                logger.info(f"Fallback 클라이언트 {i+1} 시도")
                return client.generate_structured_output(
                    system_prompt, user_prompt, output_schema, **kwargs
                ), self.fallback_clients[i].config.model.value
            except Exception as e:
                logger.warning(f"Fallback 클라이언트 {i+1} 실패: {str(e)}")
                continue
        
        # 모든 클라이언트 실패
        raise LLMError("모든 LLM 클라이언트가 실패했습니다")
    
    def get_client_stats(self) -> Dict[str, LLMUsageStats]:
        """모든 클라이언트의 사용량 통계 반환"""
        return {name: client.get_stats() for name, client in self.clients.items()}
    
    def get_available_clients(self) -> List[str]:
        """사용 가능한 클라이언트 목록 반환"""
        return list(self.clients.keys())


# 전역 LLM 클라이언트 관리자 인스턴스 (싱글톤)
_llm_manager_instance = None

def get_llm_manager() -> LLMClientManager:
    """LLM 클라이언트 관리자 인스턴스 반환 (싱글톤)"""
    global _llm_manager_instance
    if _llm_manager_instance is None:
        _llm_manager_instance = LLMClientManager()
    return _llm_manager_instance
