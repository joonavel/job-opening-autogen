"""
채용공고 생성 컴포넌트

이 모듈은 LLM을 활용하여 채용공고 초안을 생성하는 핵심 컴포넌트를 제공합니다.
- 구조화된 입력 데이터를 바탕으로 완성된 채용공고 생성
- 기업 정보와 사용자 요구사항 통합
- 다양한 직무와 업종에 맞는 맞춤형 생성
"""

import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass

from ..models.job_posting import (
    JobPostingDraft, UserInput, CompanyData, 
    ValidationResult, ValidationStatus, 
    SalaryInfo, WorkLocation
)
from ..exceptions import LLMError
from .llm_client import get_llm_manager
from config.prompts import (
    get_job_posting_generation_sys_prompt, get_job_posting_generation_user_prompt, get_company_info_prompt,
    get_job_requirements_prompt, get_compensation_prompt, get_location_prompt, get_additional_info_prompt,
    get_welfare_prompt, get_history_prompt, get_talent_prompt
)

logger = logging.getLogger(__name__)


@dataclass
class GenerationContext:
    """채용공고 생성 컨텍스트"""
    structured_input: Dict[str, Any]
    generation_metadata: Dict[str, Any]


class JobPostingGenerator:
    """
    채용공고 생성기
    
    LLM을 활용하여 구조화된 입력을 바탕으로 
    완성된 채용공고 초안을 생성합니다.
    """
    
    def __init__(self):
        """채용공고 생성기 초기화"""
        self.llm_manager = get_llm_manager()
        self.generation_stats = {
            "total_generated": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "average_generation_time": 0.0
        }
    
    def generate_job_posting(self, context: GenerationContext) -> Tuple[JobPostingDraft, Dict[str, Any]]:
        """
        채용공고 초안 생성
        
        Args:
            context: 생성 컨텍스트 (사용자 입력, 기업 데이터, 구조화된 데이터)
            
        Returns:
            생성된 채용공고 템플릿
            
        Raises:
            LLMError: 생성 실패시
        """
        start_time = time.time()
        
        try:
            logger.info("채용공고 생성 시작")
            
            # 시스템 프롬프트 로드
            system_prompt = get_job_posting_generation_sys_prompt()
            
            # 사용자 프롬프트 생성
            user_prompt = self._build_user_prompt(context)
            
            logger.info("LLM을 통한 구조화된 채용공고 생성 시작")
            
            # LLM 호출하여 구조화된 출력 생성
            job_posting, model_name = self.llm_manager.generate_structured_output(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=JobPostingDraft
            )
            
            generation_time = time.time() - start_time
            
            metadata = {
                "generation_time": generation_time,
                "generated_by": model_name
            }
            # 생성 메타데이터는 JobPostingDraft에 해당 필드가 없으므로 생략
            
            # 통계 업데이트
            self._update_generation_stats(True, generation_time)
            
            logger.info(f"채용공고 생성 완료 ({generation_time:.2f}초)")
            return job_posting, metadata
            
        except LLMError as e:
            logger.error(f"LLM 채용공고 생성 실패: {str(e)}")
            self._update_generation_stats(False, time.time() - start_time)
            metadata = {
                "generation_time": time.time() - start_time,
                "generated_by": "fallback"
            }
            # Fallback: 템플릿 기반 생성
            logger.info("템플릿 기반 Fallback 생성 시도")
            return self._generate_fallback_posting(context), metadata
    
    def _build_user_prompt(self, context: GenerationContext) -> str:
        """사용자 프롬프트 구성"""
    
        # 기업 정보 섹션
        if "company_info" in context.structured_input:
            company_data = context.structured_input.get("company_info", {})  
            company_classification = company_data.get("company_classification", "기타")
            if hasattr(company_classification, 'value'):
                company_classification = company_classification.value
            company_info_text = get_company_info_prompt().format(
                company_name=company_data.get("company_name", "정보 없음"),
                company_classification=company_classification,
                homepage=company_data.get("homepage", "정보 없음"),
                intro_summary=company_data.get("intro_summary", "정보 없음"),
                intro_detail=company_data.get("intro_detail", "정보 없음"),
                main_business=company_data.get("main_business", "정보 없음")
            )
        
        # 직무 요구사항 섹션
        if "requirements" in context.structured_input and "job_details" in context.structured_input:
            job_title = context.structured_input.get("job_title", "정보 없음")
            job_details = context.structured_input.get("job_details", {})
            requirements = context.structured_input.get("requirements", {})
            essential = "\n".join(f'- {req}' for req in requirements.get("essential", []))
            preferred = "\n".join(f'- {pref}' for pref in requirements.get("preferred", []))
            
            # Enum 값을 실제 문자열로 변환
            job_type = job_details.get("type", "정규직")
            if hasattr(job_type, 'value'):
                job_type = job_type.value
                
            experience_level = job_details.get("experience_level", "신입")
            if hasattr(experience_level, 'value'):
                experience_level = experience_level.value
            
            job_requirements_text = get_job_requirements_prompt().format(
                job_title=job_title,
                job_type=job_type,
                experience_level=experience_level,
                essential=essential,
                preferred=preferred
            )
                    
        # 급여 및 근무 조건 섹션
        if "job_details" in context.structured_input:
            job_details = context.structured_input.get("job_details", {})
            salary = job_details.get("salary", {})
            # Enum 값을 실제 문자열로 변환
            salary_type = salary.get("type", "연봉")
            if hasattr(salary_type, 'value'):  # Enum 객체인 경우
                salary_type = salary_type.value

            compensation_text = get_compensation_prompt().format(
                type=salary_type,  # compensation.prompt에서 {type}을 기대함
                min_amount=salary.get("min_amount", "정보 없음"),
                max_amount=salary.get("max_amount", "정보 없음"),
                currency=salary.get("currency", "정보 없음"),
                is_negotiable=salary.get("is_negotiable", False)
            )

            work_location = job_details.get("location", {})
            # Enum 값을 실제 문자열로 변환
            location_type = work_location.get("type", "재택근무")
            if hasattr(location_type, 'value'):  # Enum 객체인 경우
                location_type = location_type.value
            
            location_text = get_location_prompt().format(
                type=location_type,
                address=work_location.get("address", "정보 없음"),
                city=work_location.get("city", "정보 없음"),
                country=work_location.get("country", "정보 없음")
            )
            
        if "welfare_items" in context.structured_input:
            welfare_items = context.structured_input.get("welfare_items", [])
            welfare_items_text = "\n".join(f'- {item}' for item in welfare_items or [])
            welfare_text = get_welfare_prompt().format(
                welfares=welfare_items_text
            )
            
        if "history_items" in context.structured_input:
            history_items = context.structured_input.get("history_items", [])
            history_items_text = "\n".join(f'- {item}' for item in history_items or [])
            history_text = get_history_prompt().format(
                history=history_items_text
            )
            
        if "talent_criteria" in context.structured_input:
            talent_criteria = context.structured_input.get("talent_criteria", [])
            talent_criteria_text = "\n".join(f'- {item}' for item in talent_criteria or [])
            talent_text = get_talent_prompt().format(
                talents=talent_criteria_text
            )
            
        if "additional_info" in context.structured_input:
            additional_info = context.structured_input.get("additional_info", [])
            additional_info_text = "\n".join(f'- {info}' for info in additional_info or [])
            additional_text = get_additional_info_prompt().format(
                additional_info=additional_info_text
            )
        
        # 최종 프롬프트 조합
        user_prompt = get_job_posting_generation_user_prompt().format(
            company_info=company_info_text,
            job_requirements=job_requirements_text,
            compensation=compensation_text,
            location=location_text,
            welfare=welfare_text,
            history=history_text,
            talent=talent_text,
            additional_info=additional_text,   
        )
        
        return user_prompt
    
    def _generate_fallback_posting(self, context: GenerationContext) -> JobPostingDraft:
        """LLM 실패시 템플릿 기반 Fallback 생성"""
        logger.info("템플릿 기반 채용공고 생성 시작")
        company_info = context.structured_input.get("company_info", {})
        job_details = context.structured_input.get("job_details", {})
        requirements = context.structured_input.get("requirements", {})
        work_location = job_details.get("location", {})
        salary = job_details.get("salary", {})
        additional_info = context.structured_input.get("additional_info", {})
        
        try:
            # 기본 채용공고 초안 템플릿 생성
            # Enum 값을 실제 문자열로 변환
            job_type = job_details.get("type", "정규직")
            if hasattr(job_type, 'value'):
                job_type = job_type.value
                
            experience_level = job_details.get("experience_level", "신입")
            if hasattr(experience_level, 'value'):
                experience_level = experience_level.value
                
            salary_type = salary.get("type", "연봉")
            if hasattr(salary_type, 'value'):  # Enum 객체인 경우
                salary_type = salary_type.value
            
            location_type = work_location.get("type", "재택근무")
            if hasattr(location_type, 'value'):  # Enum 객체인 경우
                location_type = location_type.value
            
            fallback_posting = JobPostingDraft(
                title=f"{company_info.get('company_name', '정보 없음')} {job_details.get('job_title', '정보 없음')} 채용",
                company_name=company_info.get('company_name', '정보 없음'),
                job_description=self._generate_fallback_description(context),
                requirements=requirements.get("essential", []) or ["기본적인 업무 능력"],
                preferred_qualifications=requirements.get("preferred", []),
                job_type=job_type,
                experience_level=experience_level,
                salary_info=SalaryInfo(
                    type=salary_type,
                    min_amount=salary.get("min_amount", None),
                    max_amount=salary.get("max_amount", None),
                    currency=salary.get("currency", None),
                    is_negotiable=salary.get("is_negotiable", None)
                ),
                work_location=WorkLocation(
                    type=location_type,
                    address=work_location.get("address", None),
                    city=work_location.get("city", None),
                    country=work_location.get("country", None)
                ),
                application_deadline=None,
                contact_email=None
            )

            logger.info("템플릿 기반 채용공고 생성 완료")
            return fallback_posting
            
        except Exception as e:
            logger.error(f"템플릿 기반 생성도 실패: {str(e)}")
            raise LLMError(f"모든 생성 방법이 실패했습니다: {str(e)}")
    
    def _generate_fallback_description(self, context: GenerationContext) -> str:
        """Fallback용 직무 설명 생성"""
        company_info = context.structured_input.get("company_info", {})
        job_details = context.structured_input.get("job_details", {})
        requirements = context.structured_input.get("requirements", {})
        work_location = context.structured_input.get("work_location", {})
        
        description_parts = []
        
        # 회사 소개
        description_parts.append(f"""[회사 소개]
{company_info.get('company_name', "정보 없음")}은(는) {company_info.get('company_classification', '다양한 분야')}에서 활동하는 {company_info.get('intro_summary', '전문')} 기업입니다.""")
        
        if company_info.get("main_business", "정보 없음"):
            description_parts.append(f"주요 사업: {company_info.get('main_business', '정보 없음')}")
        
        if company_info.intro_detail:
            description_parts.append(f"\n{company_info.intro_detail[:300]}...")
        
        # 모집 내용
        description_parts.append(f"""
[모집 내용]
{company_info.get("company_name", "정보 없음")}에서 {job_details.get("job_title", "정보 없음")} 직책을 담당할 인재를 모집합니다.
우리와 함께 성장하며 전문성을 발휘하실 분을 기다리고 있습니다.

[주요 업무]
- {job_details.get("job_title", "정보 없음")} 관련 핵심 업무 수행
- 팀워크를 통한 프로젝트 목표 달성  
- 지속적인 학습과 성장을 통한 전문성 개발
- 조직 내 협업 및 커뮤니케이션

[근무 조건]
- 채용 형태: {job_details.get("type", "정보 없음")}
- 경력: {job_details.get("experience_level", "정보 없음")}""")
        
        if work_location:
            description_parts.append(f"- 근무 형태: {work_location.get('type', '정보 없음')}")
            if work_location.get("city", "정보 없음"):
                description_parts.append(f"- 근무 지역: {work_location.get('city', '정보 없음')}")
        
        return "\n".join(description_parts)
    
    def _update_generation_stats(self, success: bool, generation_time: float):
        """생성 통계 업데이트"""
        self.generation_stats["total_generated"] += 1
        
        if success:
            self.generation_stats["successful_generations"] += 1
        else:
            self.generation_stats["failed_generations"] += 1
        
        # 평균 생성 시간 업데이트
        total_generations = self.generation_stats["total_generated"]
        current_avg = self.generation_stats["average_generation_time"]
        self.generation_stats["average_generation_time"] = (
            (current_avg * (total_generations - 1) + generation_time) / total_generations
        )
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """생성 통계 반환"""
        return self.generation_stats.copy()
    
    def reset_stats(self):
        """통계 초기화"""
        self.generation_stats = {
            "total_generated": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "average_generation_time": 0.0
        }


# 전역 채용공고 생성기 인스턴스 (싱글톤)
_generator_instance = None

def get_job_posting_generator() -> JobPostingGenerator:
    """채용공고 생성기 인스턴스 반환 (싱글톤)"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = JobPostingGenerator()
    return _generator_instance

