"""
프롬프트 템플릿 관리 유틸리티

이 모듈은 채용공고 자동생성에 사용되는 프롬프트 템플릿들을 
로드하고 관리하는 기능을 제공합니다.
"""

import os
from typing import Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# 프롬프트 파일 경로들
PROMPT_DIR = Path(__file__).parent
NATURAL_LANGUAGE_STRUCTURING_SYS_PROMPT = PROMPT_DIR / "natural_language_structuring_sys.prompt"
NATURAL_LANGUAGE_STRUCTURING_USER_PROMPT = PROMPT_DIR / "natural_language_structuring_user.prompt"
JOB_POSTING_GENERATION_SYS_PROMPT = PROMPT_DIR / "job_posting_generation_sys.prompt"
JOB_POSTING_GENERATION_USER_PROMPT = PROMPT_DIR / "job_posting_generation_user.prompt"
COMPANY_INFO_PROMPT = PROMPT_DIR / "input_structure" / "company_info.prompt"
JOB_REQUIREMENTS_PROMPT = PROMPT_DIR / "input_structure" / "job_requirements.prompt"
COMPENSATION_PROMPT = PROMPT_DIR / "input_structure" / "compensation.prompt"
LOCATION_PROMPT = PROMPT_DIR / "input_structure" / "location.prompt"
ADDITIONAL_INFO_PROMPT = PROMPT_DIR / "input_structure" / "additional_info.prompt"
WELFARE_PROMPT = PROMPT_DIR / "input_structure" / "company_welfare.prompt"
HISTORY_PROMPT = PROMPT_DIR / "input_structure" / "company_history.prompt"
TALENT_PROMPT = PROMPT_DIR / "input_structure" / "company_talent.prompt"

def load_prompt_template(file_path: Path) -> str:
    """
    프롬프트 템플릿 파일을 로드합니다.
    
    Args:
        file_path: 프롬프트 파일 경로
        
    Returns:
        프롬프트 템플릿 문자열
        
    Raises:
        FileNotFoundError: 파일이 존재하지 않는 경우
        IOError: 파일 읽기 실패한 경우
    """
    try:
        if not file_path.exists():
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {file_path}")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
        if not content:
            logger.warning(f"프롬프트 파일이 비어있습니다: {file_path}")
            
        logger.info(f"프롬프트 템플릿 로드 완료: {file_path.name}")
        return content
        
    except Exception as e:
        logger.error(f"프롬프트 파일 로드 실패: {file_path} - {str(e)}")
        raise IOError(f"프롬프트 파일 로드 실패: {str(e)}")


def get_natural_language_structuring_sys_prompt() -> str:
    """자연어 입력 구조화 프롬프트 반환"""
    return load_prompt_template(NATURAL_LANGUAGE_STRUCTURING_SYS_PROMPT)


def get_natural_language_structuring_user_prompt() -> str:
    """자연어 입력 구조화 프롬프트 반환"""
    return load_prompt_template(NATURAL_LANGUAGE_STRUCTURING_USER_PROMPT)


def get_job_posting_generation_sys_prompt() -> str:
    """채용공고 생성 프롬프트 반환"""
    return load_prompt_template(JOB_POSTING_GENERATION_SYS_PROMPT)


def get_job_posting_generation_user_prompt() -> str:
    """채용공고 생성 프롬프트 반환"""
    return load_prompt_template(JOB_POSTING_GENERATION_USER_PROMPT)


def get_company_info_prompt() -> str:
    """기업 정보 프롬프트 반환"""
    return load_prompt_template(COMPANY_INFO_PROMPT)


def get_job_requirements_prompt() -> str:
    """직무 요구사항 프롬프트 반환"""
    return load_prompt_template(JOB_REQUIREMENTS_PROMPT)


def get_compensation_prompt() -> str:
    """보상 프롬프트 반환"""
    return load_prompt_template(COMPENSATION_PROMPT)


def get_location_prompt() -> str:
    """근무 위치 프롬프트 반환"""
    return load_prompt_template(LOCATION_PROMPT)


def get_welfare_prompt() -> str:
    """복리후생 프롬프트 반환"""
    return load_prompt_template(WELFARE_PROMPT)

def get_history_prompt() -> str:
    """기업 연혁 프롬프트 반환"""
    return load_prompt_template(HISTORY_PROMPT)

def get_talent_prompt() -> str:
    """인재상 프롬프트 반환"""
    return load_prompt_template(TALENT_PROMPT)

def get_additional_info_prompt() -> str:
    """추가 정보 프롬프트 반환"""
    return load_prompt_template(ADDITIONAL_INFO_PROMPT)


def get_all_prompts() -> Dict[str, str]:
    """모든 프롬프트 템플릿 반환"""
    return {
        "natural_language_structuring_sys": get_natural_language_structuring_sys_prompt(),
        "natural_language_structuring_user": get_natural_language_structuring_user_prompt(),
        "job_posting_generation_sys": get_job_posting_generation_sys_prompt(),
        "job_posting_generation_user": get_job_posting_generation_user_prompt(),
        "company_info": get_company_info_prompt(),
        "job_requirements": get_job_requirements_prompt(),
        "compensation": get_compensation_prompt(),
        "location": get_location_prompt(),
        "additional_info": get_additional_info_prompt(),
        "welfare": get_welfare_prompt(),
        "history": get_history_prompt(),
        "talent": get_talent_prompt(),
    }


def validate_prompts() -> Dict[str, bool]:
    """
    모든 프롬프트 파일의 유효성 검증
    
    Returns:
        각 프롬프트 파일의 유효성 상태
    """
    validation_results = {}
    
    prompts = {
        "natural_language_structuring_sys": NATURAL_LANGUAGE_STRUCTURING_SYS_PROMPT,
        "natural_language_structuring_user": NATURAL_LANGUAGE_STRUCTURING_USER_PROMPT,
        "job_posting_generation_sys": JOB_POSTING_GENERATION_SYS_PROMPT,
        "job_posting_generation_user": JOB_POSTING_GENERATION_USER_PROMPT,
        "company_info": COMPANY_INFO_PROMPT,
        "job_requirements": JOB_REQUIREMENTS_PROMPT,
        "compensation": COMPENSATION_PROMPT,
        "location": LOCATION_PROMPT,
        "additional_info": ADDITIONAL_INFO_PROMPT,
        "welfare": WELFARE_PROMPT,
        "history": HISTORY_PROMPT,
        "talent": TALENT_PROMPT,
    }
    
    for name, path in prompts.items():
        try:
            content = load_prompt_template(path)
            validation_results[name] = bool(content and len(content) > 100)
        except Exception as e:
            logger.error(f"프롬프트 검증 실패 ({name}): {str(e)}")
            validation_results[name] = False
    
    return validation_results


# 프롬프트 캐시 (메모리 최적화)
_prompt_cache: Dict[str, str] = {}

def get_cached_prompt(prompt_name: str) -> Optional[str]:
    """캐시된 프롬프트 반환"""
    return _prompt_cache.get(prompt_name)

def cache_prompt(prompt_name: str, content: str) -> None:
    """프롬프트 캐시에 저장"""
    _prompt_cache[prompt_name] = content

def clear_prompt_cache() -> None:
    """프롬프트 캐시 초기화"""
    global _prompt_cache
    _prompt_cache.clear()
    logger.info("프롬프트 캐시 초기화 완료")
