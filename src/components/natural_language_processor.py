"""
자연어 입력 처리 컴포넌트

이 모듈은 사용자의 자연어 입력을 구조화된 UserInput 모델로 변환하는 기능을 제공합니다.
- LLM을 활용한 자연어 이해 및 정보 추출
- 누락된 정보에 대한 적절한 기본값 설정
- 모호한 표현의 표준화 및 해석
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from ..models.job_posting import (
    UserInput, JobTypeEnum, ExperienceLevel, SalaryInfo, SalaryType, 
    WorkLocation, WorkLocationEnum, ValidationResult, ValidationStatus
)
from ..exceptions import LLMError
from .llm_client import get_llm_manager
from config.prompts import get_natural_language_structuring_sys_prompt, get_natural_language_structuring_user_prompt

logger = logging.getLogger(__name__)


@dataclass
class ProcessingContext:
    """자연어 처리 컨텍스트"""
    raw_input: str
    processing_metadata: Dict[str, Any]
    confidence_threshold: float = 0.7


class NaturalLanguageProcessor:
    """
    자연어 입력 처리기
    
    사용자의 자연어 입력을 분석하여 구조화된 UserInput 모델로 변환합니다.
    """
    
    def __init__(self):
        """자연어 처리기 초기화"""
        self.llm_manager = get_llm_manager()
        self.processing_stats = {
            "total_processed": 0,
            "successful_processing": 0,
            "failed_processing": 0,
            "average_processing_time": 0.0
        }
    
    def process_natural_language_input(self, context: ProcessingContext) -> Tuple[UserInput, Dict[str, Any]]:
        """
        자연어 입력을 구조화된 UserInput으로 변환
        
        Args:
            context: 처리 컨텍스트 (자연어 입력 및 메타데이터)
            
        Returns:
            구조화된 UserInput 객체
            
        Raises:
            LLMError: 생성 실패시
        """
        start_time = time.time()
        
        try:
            logger.info("자연어 입력 구조화 시작")
            
            # 시스템 프롬프트 로드
            system_prompt = get_natural_language_structuring_sys_prompt()
            
            # 사용자 프롬프트 생성
            user_prompt = self._build_user_prompt(context)
            
            logger.info("LLM을 통한 자연어 구조화 시작")
            
            # LLM 호출하여 구조화된 출력 생성
            structured_input, model_name = self.llm_manager.generate_structured_output(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=UserInput
            )
            
            generation_time = time.time() - start_time
            metadata = {
                "generation_time": generation_time,
                "generated_by": model_name
            }
            # 후처리 및 검증
            validated_input = self._post_process_structured_input(structured_input, context)
            
            # 통계 업데이트
            self._update_processing_stats(True, generation_time)
            
            logger.info(f"자연어 입력 구조화 완료 ({generation_time:.2f}초)")
            return validated_input, metadata
            
        except LLMError as e:
            logger.error(f"LLM 자연어 처리 실패: {str(e)}")
            self._update_processing_stats(False, generation_time)
            metadata = {
                "generation_time": generation_time,
                "generated_by": "fallback"
            }
            
            # Fallback: 규칙 기반 처리
            logger.info("규칙 기반 Fallback 처리 시도")
            return self._rule_based_fallback_processing(context), metadata
    
    def _build_user_prompt(self, context: ProcessingContext) -> str:
        """사용자 프롬프트 구성"""
        user_prompt = get_natural_language_structuring_user_prompt().format(raw_input=context.raw_input)

        return user_prompt
    
    def _post_process_structured_input(self, 
                                     structured_input: UserInput, 
                                     context: ProcessingContext) -> UserInput:
        """구조화된 입력 후처리 및 검증"""
        
        logger.info("구조화된 입력 후처리 시작")
        
        # 필수 필드 기본값 설정
        if not structured_input.job_title.strip():
            structured_input.job_title = "직무명 미정"
            logger.warning("직무명이 비어있어 기본값으로 설정")
        
        if not structured_input.company_name.strip():
            structured_input.company_name = "회사명 미정"  
            logger.warning("회사명이 비어있어 기본값으로 설정")
        
        if not structured_input.requirements:
            structured_input.requirements = ["기본적인 업무 능력"]
            logger.warning("필수 요구사항이 비어있어 기본값으로 설정")
        
        # 텍스트 정리
        structured_input.job_title = structured_input.job_title.strip()
        structured_input.company_name = structured_input.company_name.strip()
        structured_input.requirements = [req.strip() for req in structured_input.requirements if req.strip()]
        structured_input.preferred_qualifications = [pref.strip() for pref in structured_input.preferred_qualifications if pref.strip()]
        
        # 데이터 품질 검증
        quality_issues = self._validate_data_quality(structured_input)
        if quality_issues:
            logger.warning(f"데이터 품질 이슈 발견: {quality_issues}")
        
        logger.info("구조화된 입력 후처리 완료")
        return structured_input
    
    def _validate_data_quality(self, structured_input: UserInput) -> List[str]:
        """데이터 품질 검증"""
        issues = []
        
        # 직무명 검증
        if len(structured_input.job_title) < 2:
            issues.append("직무명이 너무 짧습니다")
        elif len(structured_input.job_title) > 20:
            issues.append("직무명이 너무 깁니다")
        
        # 회사명 검증  
        if len(structured_input.company_name) < 2:
            issues.append("회사명이 너무 짧습니다")
        elif len(structured_input.company_name) > 50:
            issues.append("회사명이 너무 깁니다")
        
        # 요구사항 검증
        if len(structured_input.requirements) > 15:
            issues.append("필수 요구사항이 너무 많습니다")
        
        if len(structured_input.preferred_qualifications) > 10:
            issues.append("우대사항이 너무 많습니다")
        
        return issues
    
    def _rule_based_fallback_processing(self, context: ProcessingContext) -> UserInput:
        """LLM 실패시 규칙 기반 Fallback 처리"""
        logger.info("규칙 기반 자연어 처리 시작")
        
        try:
            raw_text = context.raw_input.lower().strip()
            
            # 기본 값들
            job_title = "직무명 미정"
            company_name = "회사명 미정"  
            requirements = ["기본 업무 능력"]
            preferred_qualifications = []
            job_type = JobTypeEnum.FULL_TIME
            experience_level = ExperienceLevel.ENTRY
            
            # 간단한 키워드 추출
            
            # 직무 키워드 추출
            job_keywords = ["개발자", "엔지니어", "매니저", "디자이너", "마케터", "분석가", "컨설턴트"]
            for keyword in job_keywords:
                if keyword in raw_text:
                    job_title = keyword
                    break
            
            # 회사명 추출 (간단한 패턴)
            company_patterns = ["회사", "기업", "스타트업", "코퍼레이션", "그룹"]
            for pattern in company_patterns:
                if pattern in raw_text:
                    # 패턴 앞의 단어들을 회사명으로 추정
                    words = raw_text.split()
                    for i, word in enumerate(words):
                        if pattern in word and i > 0:
                            company_name = words[i-1] + pattern
                            break
                    break
            
            # 경력 수준 추출
            if "신입" in raw_text or "신규" in raw_text:
                experience_level = ExperienceLevel.ENTRY
            elif "시니어" in raw_text or "선임" in raw_text:
                experience_level = ExperienceLevel.SENIOR
            elif "주니어" in raw_text:
                experience_level = ExperienceLevel.JUNIOR
            elif any(str(i) in raw_text for i in range(1, 10)) and "년" in raw_text:
                experience_level = ExperienceLevel.MID
            
            # 채용 형태 추출
            if "계약직" in raw_text:
                job_type = JobTypeEnum.PART_TIME
            elif "인턴" in raw_text:
                job_type = JobTypeEnum.INTERN
            elif "프리랜서" in raw_text:
                job_type = JobTypeEnum.CONTRACTOR
            
            # 기술/요구사항 키워드 추출 (간단한 버전)
            tech_keywords = ["python", "java", "javascript", "react", "vue", "aws", "docker", "kubernetes"]
            found_tech = [keyword for keyword in tech_keywords if keyword in raw_text]
            if found_tech:
                requirements = found_tech[:5]  # 최대 5개만
            
            fallback_input = UserInput(
                job_title=job_title,
                company_name=company_name,
                requirements=requirements,
                preferred_qualifications=preferred_qualifications,
                job_type=job_type,
                experience_level=experience_level,
                additional_info={
                    "processing_method": "rule_based_fallback",
                    "original_input": context.raw_input,
                    "confidence": "low"
                }
            )
            
            logger.info("규칙 기반 자연어 처리 완료")
            return fallback_input
            
        except Exception as e:
            logger.error(f"규칙 기반 처리도 실패: {str(e)}")
            
            # 최종 Fallback: 최소한의 기본값
            return UserInput(
                job_title="직무명 미정",
                company_name="회사명 미정",
                requirements=["기본 업무 능력"],
                additional_info={
                    "processing_method": "minimal_fallback",
                    "original_input": context.raw_input,
                    "error": str(e)
                }
            )
    
    def _update_processing_stats(self, success: bool, processing_time: float):
        """처리 통계 업데이트"""
        self.processing_stats["total_processed"] += 1
        
        if success:
            self.processing_stats["successful_processing"] += 1
        else:
            self.processing_stats["failed_processing"] += 1
        
        # 평균 처리 시간 업데이트
        total_processed = self.processing_stats["total_processed"]
        current_avg = self.processing_stats["average_processing_time"]
        self.processing_stats["average_processing_time"] = (
            (current_avg * (total_processed - 1) + processing_time) / total_processed
        )
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """처리 통계 반환"""
        return self.processing_stats.copy()
    
    def reset_stats(self):
        """통계 초기화"""
        self.processing_stats = {
            "total_processed": 0,
            "successful_processing": 0,
            "failed_processing": 0,
            "average_processing_time": 0.0
        }


# 전역 자연어 처리기 인스턴스 (싱글톤)
_processor_instance = None

def get_natural_language_processor() -> NaturalLanguageProcessor:
    """자연어 처리기 인스턴스 반환 (싱글톤)"""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = NaturalLanguageProcessor()
    return _processor_instance

