"""
환각 검증 에이전트 테스트

이 모듈은 analyze_intrinsic_consistency_with_agent 함수의 테스트를 제공합니다.
"""

import pytest
import logging
import uuid
from dotenv import load_dotenv
from unittest.mock import patch, MagicMock
from datetime import datetime
from typing import Dict, Any

from src.agents.hallucination_validator import (
    analyze_intrinsic_consistency_with_agent,
    HallucinationValidationRequest,
    create_intrinsic_validation_prompt
)
from src.models.job_posting import (
    JobPostingDraft,
    SalaryInfo,
    SalaryType,
    WorkLocation,
    WorkLocationEnum,
    JobTypeEnum,
    ExperienceLevel
)
from src.exceptions import ValidationError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(override=True)


class TestHallucinationValidator:
    """환각 검증 에이전트 테스트 클래스"""
    
    @pytest.fixture
    def sample_job_posting_draft(self):
        """테스트용 채용공고 초안 (일부 환각 요소 포함)"""
        return JobPostingDraft(
            title="일일일퍼센트 백엔드 개발자 채용",
            company_name="일일일퍼센트",
            job_description="[회사 소개]\n- 111퍼센트는 '재미'라는 본질에 집중하여 기존 장르를 넘어 새로운 게임 장르를 만들어가는 게임 개발사입니다. 게임 개발과 퍼블리싱을 통해 다양한 플레이 경험을 제공하며 창의성과 기술력을 중시합니다.\n\n[모집 배경 및 직무 개요]\n- 서비스 확장과 안정적인 서버 운영을 위해 중급 수준의 백엔드 개발자를 찾습니다. 본 포지션은 게임 서버 및 관련 백엔드 인프라를 설계·구축하고, 퍼포먼스 최적화와 안정성 향상을 통해 플레이어 경험을 개선하는 역할을 담당합니다.\n\n[주요 업무]\n- Python 및 FastAPI 기반의 게임/서비스용 REST API 설계 및 개발\n- 데이터베이스(PostgreSQL 등) 설계, 쿼리 최적화 및 성능 튜닝\n- Redis 등 캐시 시스템을 활용한 성능 개선 및 세션/상태 관리\n- Docker 기반 컨테이너화 및 배포 파이프라인 협업(우대사항에 해당)\n- Git을 활용한 팀 협업 및 코드리뷰 참여\n- 서비스 모니터링, 로깅 및 장애 대응 프로세스 개선\n\n[우리가 추구하는 문화와 성장 기회]\n- 소규모(5-10명) 팀 단위로 자율성과 책임을 중시하는 근무 문화를 지향합니다. 실무 중심의 의사결정과 빠른 실험을 통해 기술적 성장을 도모할 수 있으며, AI/ML 모델 서빙·클라우드 아키텍처 등 최신 기술 도입 기회가 있습니다.\n\n[근무 환경 및 조건]\n- 채용 형태: 정규직\n- 경력 수준: 중급(경력 3년 이상)\n- 근무 형태: 하이브리드(서울 강남구 테헤란로 123, 서울)\n- 팀 규모: 5-10명\n- 주요 기술 스택: Python, FastAPI, PostgreSQL, Redis, Docker\n- 복리후생: 4대보험, 연차 15일, 교육비 지원 등",
            requirements=[
                "경력 3년 이상",
                "Python 및 FastAPI 프레임워크 경험 3년 이상",
                "데이터베이스 설계 및 최적화 경험 (예: PostgreSQL 쿼리 튜닝, 인덱스 설계)",
                "REST API 설계 및 개발 경험",
                "Git을 활용한 협업 경험 (브랜치 전략, 코드리뷰 등)"
            ],
            job_type=JobTypeEnum.FULL_TIME,
            experience_level=ExperienceLevel.MID,
            preferred_qualifications=[
                "AI/ML 모델 서빙 경험",
                "Docker, Kubernetes 사용 경험",
                "AWS 클라우드 서비스 활용 경험"
            ],
            benefits=[
                "4대보험",
                "연차 15일", 
                "교육비 지원",
                "하이브리드 근무(원격 + 오피스)"
            ],
            salary_info=SalaryInfo(
                type=SalaryType.ANNUAL,
                min_amount=40000000.0,
                max_amount=60000000.0,
                currency="KRW",
                is_negotiable=True
            ),
            work_location=WorkLocation(
                type=WorkLocationEnum.HYBRID,
                address="서울 강남구 테헤란로 123",
                city="서울",
                country="대한민국"
            ),
            application_deadline=None,
            contact_email=None
        )
    
    @pytest.fixture
    def sample_structured_input(self):
        """테스트용 구조화된 입력 데이터 (원본 사용자 입력)"""
        return {
            "job_title": "백엔드 개발자",
            "company_name": "일일일퍼센트",  # 회사명이 일치
            "requirements": [
                "Python 경험 3년 이상",
                "FastAPI 프레임워크 경험",
                "데이터베이스 설계 경험",
                "REST API 개발 경험"
            ],
            "preferred_qualifications": [
                "AI/ML 경험 우대",
                "Docker 사용 경험",
                "AWS 클라우드 경험"
            ],
            "job_type": "정규직",
            "experience_level": "중급",
            "salary_range": "4000만원~6000만원",
            "work_location": "서울 강남구",
            "benefits": ["4대보험", "연차", "교육비 지원"],
            "company_info": {
                "industry": "게임 개발",
                "size": "스타트업",
                "description": "게임 개발 및 퍼블리싱 회사"
            }
        }
    
    @pytest.fixture
    def inconsistent_job_posting_draft(self):
        """논리적 모순이 있는 채용공고 초안 (Pydantic validator는 통과하지만 논리적으로 모순)"""
        return JobPostingDraft(
            title="일일일퍼센트 신입 시니어 개발자 채용",  # 모순: 신입 + 시니어
            company_name="일일일퍼센트",
            job_description="[회사 소개]\n- 일일일퍼센트는 설립 100년의 전통 있는 AI 스타트업입니다.\n- 직원 수 5명의 대기업으로 전 세계 50개국에서 서비스하고 있습니다.\n\n[주요 업무]\n- 신입 개발자로서 10년 이상의 시니어 업무 담당\n- Python을 사용하지 않는 Python 개발\n- 원격 근무 불가능한 100% 원격 근무",
            requirements=[
                "신입 개발자 (경력 10년 이상)",  # 모순: 신입 + 10년 경력
                "Python 사용 경험 없음 필수",  # 모순: Python 개발자인데 경험 없음
                "서울 거주 (부산 근무)",  # 모순: 서울 거주 + 부산 근무
                "풀타임 파트타임 근무"  # 모순: 풀타임 + 파트타임
            ],
            job_type=JobTypeEnum.FULL_TIME,
            experience_level=ExperienceLevel.ENTRY,  # 모순: 신입인데 시니어 업무
            preferred_qualifications=[
                "경험 없는 10년차 개발자",
                "사용 안하는 Docker 전문가"
            ],
            benefits=[
                "4대보험 미제공",
                "연차 0일",  # 비현실적이지만 양수 제약은 없음
                "야근 수당 삭감"
            ],
            salary_info=SalaryInfo(
                type=SalaryType.ANNUAL,
                min_amount=50000000.0,  # validator 통과하도록 min < max
                max_amount=100000000.0, 
                currency="USD",  # 한국 회사인데 USD (논리적 모순)
                is_negotiable=False
            ),
            work_location=WorkLocation(
                type=WorkLocationEnum.ONSITE,  # "재택근무"인데 사무실 주소 제공 (모순)
                address="서울 강남구 테헤란로 123",
                city="부산",  # 모순: 서울 주소 + 부산 도시
                country="일본"  # 모순: 한국 회사 + 일본 위치
            ),
            application_deadline=None,
            contact_email=None
        )
    
    @pytest.fixture
    def mock_corrected_job_posting(self):
        """첨삭된 채용공고 (환각 요소가 수정됨)"""
        return JobPostingDraft(
            title="일일일퍼센트 백엔드 개발자 채용",
            company_name="일일일퍼센트",
            job_description="[회사 소개]\n- 일일일퍼센트는 '재미'라는 본질에 집중하여 새로운 게임 장르를 만들어가는 게임 개발사입니다.\n\n[주요 업무]\n- Python 및 FastAPI 기반의 게임 서버 REST API 개발\n- 데이터베이스 설계, 쿼리 최적화 및 성능 튜닝\n- Redis를 활용한 캐시 시스템 및 세션 관리\n- 팀 협업 및 코드리뷰 참여",
            requirements=[
                "경력 3년 이상",
                "Python 및 FastAPI 프레임워크 경험",
                "데이터베이스 설계 및 최적화 경험",
                "REST API 설계 및 개발 경험"
            ],
            job_type=JobTypeEnum.FULL_TIME,
            experience_level=ExperienceLevel.MID,
            preferred_qualifications=[
                "AI/ML 모델 서빙 경험",
                "Docker, Kubernetes 사용 경험",
                "AWS 클라우드 서비스 경험"
            ],
            benefits=[
                "4대보험",
                "연차 15일",
                "교육비 지원"
            ],
            salary_info=SalaryInfo(
                type=SalaryType.ANNUAL,
                min_amount=40000000.0,
                max_amount=60000000.0,
                currency="KRW",
                is_negotiable=True
            ),
            work_location=WorkLocation(
                type=WorkLocationEnum.HYBRID,
                address="서울 강남구 테헤란로 123",
                city="서울",
                country="대한민국"
            ),
            application_deadline=None,
            contact_email=None
        )
    
    def test_create_intrinsic_validation_prompt(self, sample_job_posting_draft, sample_structured_input):
        """프롬프트 생성 함수 테스트"""
        system_prompt, user_prompt = create_intrinsic_validation_prompt(
            sample_job_posting_draft, 
            sample_structured_input
        )
        
        # 시스템 프롬프트 검증
        assert isinstance(system_prompt, str)
        assert len(system_prompt) > 500  # 충분한 길이의 프롬프트
        assert "내재적 일관성" in system_prompt
        assert "논리적 모순" in system_prompt
        assert "사실 불일치" in system_prompt
        assert "일일일퍼센트" in system_prompt  # 회사명 포함
        
        # 사용자 프롬프트 검증
        assert isinstance(user_prompt, str)
        assert "참조 정보" in user_prompt
        assert "게임 개발" in user_prompt  # 구조화된 입력의 내용 포함
        
        logger.info("프롬프트 생성 함수 테스트 통과")
    
    @patch('src.agents.hallucination_validator.create_react_agent')
    @patch('src.agents.hallucination_validator.init_chat_model')
    def test_analyze_intrinsic_consistency_mock_success(
        self, 
        mock_init_chat_model, 
        mock_create_react_agent,
        sample_job_posting_draft,
        sample_structured_input,
        mock_corrected_job_posting
    ):
        """Mock을 사용한 성공적인 환각 검증 테스트"""
        
        # Mock 설정
        mock_llm = MagicMock()
        mock_init_chat_model.return_value = mock_llm
        
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "structured_response": mock_corrected_job_posting
        }
        mock_create_react_agent.return_value = mock_agent
        
        # 테스트 실행
        request = HallucinationValidationRequest(
            job_posting_draft=sample_job_posting_draft,
            structured_input=sample_structured_input
        )
        result, metadata = analyze_intrinsic_consistency_with_agent(request, thread_id=str(uuid.uuid4()))
        
        # Mock 호출 확인
        mock_init_chat_model.assert_called_once()
        mock_create_react_agent.assert_called_once()
        mock_agent.invoke.assert_called_once()
        
        # Agent가 올바른 설정으로 생성되었는지 확인
        create_args = mock_create_react_agent.call_args
        assert create_args[1]['response_format'] == JobPostingDraft
        assert len(create_args[1]['tools']) == 0  # 환각 검증은 도구 없음
        
        # 결과 검증
        assert isinstance(result, JobPostingDraft)
        assert result.title == "일일일퍼센트 백엔드 개발자 채용"
        assert result.company_name == "일일일퍼센트"
        
        # 메타데이터 검증
        assert isinstance(metadata, dict)
        assert "thread_id" in metadata
        assert "generated_by" in metadata
        assert metadata["generated_by"] == "gpt-4o-mini"
        
        logger.info("Mock을 사용한 환각 검증 성공 테스트 통과")
    
    @patch('src.agents.hallucination_validator.create_react_agent')
    @patch('src.agents.hallucination_validator.init_chat_model')
    def test_analyze_intrinsic_consistency_error_handling(
        self, 
        mock_init_chat_model, 
        mock_create_react_agent,
        sample_job_posting_draft,
        sample_structured_input
    ):
        """에러 처리 테스트"""
        
        # Mock이 예외를 발생시키도록 설정
        mock_init_chat_model.side_effect = Exception("LLM 초기화 실패")
        
        # 테스트 실행
        request = HallucinationValidationRequest(
            job_posting_draft=sample_job_posting_draft,
            structured_input=sample_structured_input
        )
        
        # 에러 발생 시 원본 JobPostingDraft가 반환되어야 함 (보수적 접근)
        result, metadata = analyze_intrinsic_consistency_with_agent(request, thread_id=str(uuid.uuid4()))
        
        # 원본이 그대로 반환되는지 확인
        assert result == sample_job_posting_draft
        assert "error" in metadata
        assert "LLM 초기화 실패" in metadata["error"]
        
        logger.info("에러 처리 테스트 통과")
    
    @patch('src.agents.hallucination_validator.create_react_agent')
    @patch('src.agents.hallucination_validator.init_chat_model')
    def test_no_structured_response_error(
        self, 
        mock_init_chat_model, 
        mock_create_react_agent,
        sample_job_posting_draft,
        sample_structured_input
    ):
        """structured_response가 없을 때의 처리 테스트"""
        
        # Mock 설정 - structured_response가 없는 응답
        mock_llm = MagicMock()
        mock_init_chat_model.return_value = mock_llm
        
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"other_key": "value"}  # 잘못된 응답
        mock_create_react_agent.return_value = mock_agent
        
        # 테스트 실행 및 예외 확인
        request = HallucinationValidationRequest(
            job_posting_draft=sample_job_posting_draft,
            structured_input=sample_structured_input
        )
        
        with pytest.raises(ValidationError) as exc_info:
            analyze_intrinsic_consistency_with_agent(request, thread_id=str(uuid.uuid4()))
        
        assert "환각 검증 결과를 받지 못했습니다" in str(exc_info.value)
        logger.info("structured_response 없음 에러 처리 테스트 통과")
    
    def test_hallucination_validation_request_model(self, sample_job_posting_draft, sample_structured_input):
        """HallucinationValidationRequest 모델 테스트"""
        
        request = HallucinationValidationRequest(
            job_posting_draft=sample_job_posting_draft,
            structured_input=sample_structured_input
        )
        
        assert isinstance(request.job_posting_draft, JobPostingDraft)
        assert isinstance(request.structured_input, dict)
        assert request.job_posting_draft.company_name == "일일일퍼센트"
        assert "company_info" in request.structured_input
        
        logger.info("HallucinationValidationRequest 모델 테스트 통과")
    
    def test_detect_logical_inconsistencies(self, inconsistent_job_posting_draft, sample_structured_input):
        """논리적 모순 감지 시뮬레이션 테스트"""
        
        # 실제 환각 요소들을 확인 (시뮬레이션)
        job_posting = inconsistent_job_posting_draft
        
        detected_issues = []
        
        # 제목에서 모순 감지
        if "신입" in job_posting.title and "시니어" in job_posting.title:
            detected_issues.append("제목에 '신입'과 '시니어'가 동시에 포함된 모순")
        
        # 급여 정보에서 모순 감지 (통화가 한국 회사에 맞지 않음)
        if (job_posting.salary_info and 
            job_posting.salary_info.currency == "USD" and 
            job_posting.company_name and "일일일퍼센트" in job_posting.company_name):
            detected_issues.append("한국 회사임에도 불구하고 USD로 급여가 설정된 모순")
        
        # 위치 정보에서 모순 감지
        if (job_posting.work_location and 
            "서울" in job_posting.work_location.address and 
            job_posting.work_location.city == "부산"):
            detected_issues.append("주소는 서울인데 도시는 부산으로 설정된 모순")
        
        # WorkLocation 타입과 주소 정보의 모순 감지
        if (job_posting.work_location and 
            job_posting.work_location.type == WorkLocationEnum.ONSITE and  # ONSITE = "재택근무" 
            job_posting.work_location.address):
            detected_issues.append("재택근무임에도 불구하고 구체적인 사무실 주소가 제공된 모순")
        
        # 요구사항에서 모순 감지
        for req in job_posting.requirements:
            if "신입" in req and "10년" in req:
                detected_issues.append(f"요구사항에서 신입과 10년 경력의 모순: {req}")
        
        # 결과 검증
        assert len(detected_issues) >= 5  # 최소 5개의 모순 감지
        assert any("신입" in issue and "시니어" in issue for issue in detected_issues)
        assert any("USD" in issue and "한국" in issue for issue in detected_issues)  # 통화 모순
        assert any("서울" in issue and "부산" in issue for issue in detected_issues)
        assert any("재택근무" in issue and "사무실 주소" in issue for issue in detected_issues)  # 근무형태 모순
        
        logger.info(f"논리적 모순 감지 테스트 통과: {len(detected_issues)}개 문제 감지")
        for issue in detected_issues:
            logger.info(f"  - {issue}")


# 실제 테스트 실행을 위한 헬퍼 함수들
def run_real_test_hallucination_detection():
    """실제 API를 사용한 환각 검증 테스트 실행"""
    
    # 환각 요소가 포함된 채용공고 생성 (Pydantic validator는 통과하지만 논리적으로 모순)
    problematic_draft = JobPostingDraft(
        title="스타트업 대기업 신입 시니어 개발자",  # 모순적 표현
        company_name="테스트회사",
        job_description="[회사 소개]\n- 저희는 설립 1년된 100년 전통의 AI 스타트업입니다.\n- 직원 3명의 글로벌 대기업으로 전 세계에서 활동합니다.\n\n[업무]\n- 신입으로서 10년차 시니어 업무 담당\n- Python을 전혀 사용하지 않는 Python 개발",
        requirements=[
            "신입 개발자 (10년 경력 필수)",
            "Python 사용 경험 전혀 없음",
            "풀타임 파트타임 근무 가능자"
        ],
        job_type=JobTypeEnum.FULL_TIME,
        experience_level=ExperienceLevel.ENTRY,
        preferred_qualifications=[
            "경험 없는 전문가 우대"
        ],
        benefits=[
            "연차 0일",  # validator 통과하지만 비현실적
            "4대보험 미가입"
        ],
        salary_info=SalaryInfo(
            type=SalaryType.ANNUAL,
            min_amount=40000000.0,  # validator 통과하도록 수정
            max_amount=80000000.0,  # min < max로 변경
            currency="USD",  # 한국 회사인데 USD (논리적 모순)
            is_negotiable=False
        ),
        work_location=WorkLocation(
            type=WorkLocationEnum.REMOTE,
            address="서울 강남구",
            city="부산",  # 주소와 도시 불일치
            country="일본"  # 한국 회사인데 일본
        )
    )
    
    structured_input = {
        "job_title": "개발자",
        "company_name": "테스트회사",
        "requirements": ["Python 개발 경험", "신입 환영"],
        "job_type": "정규직",
        "experience_level": "신입",
        "work_location": "서울"
    }
    
    print("🧪 환각 검증 에이전트 실제 테스트")
    print("=" * 50)
    
    print("📝 원본 채용공고 (환각 요소 포함):")
    print(f"   제목: {problematic_draft.title}")
    print(f"   설명: {problematic_draft.job_description[:100]}...")
    print(f"   요구사항: {problematic_draft.requirements}")
    print(f"   급여: {problematic_draft.salary_info.min_amount:,}~{problematic_draft.salary_info.max_amount:,} {problematic_draft.salary_info.currency}")
    print(f"   위치: {problematic_draft.work_location.city}")
    
    try:
        request = HallucinationValidationRequest(
            job_posting_draft=problematic_draft,
            structured_input=structured_input
        )
        
        result, metadata = analyze_intrinsic_consistency_with_agent(request, thread_id=str(uuid.uuid4()))
        
        print(f"\n✅ 환각 검증 완료!")
        print(f"   결과 타입: {type(result)}")
        print(f"   수정된 제목: {result.title}")
        print(f"   수정된 요구사항: {result.requirements}")
        print(f"   메타데이터: {metadata}")
        
        return result, metadata
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return None, None


if __name__ == "__main__":
    """직접 실행시 실제 환각 검증 테스트 수행"""
    print("🔍 환각 검증 에이전트 실제 테스트 실행\n")
    
    run_real_test_hallucination_detection()
    print()
    
    print("💡 전체 테스트 스위트 실행: pytest tests/test_hallucination_validator.py -v")
