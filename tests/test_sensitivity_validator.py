"""
민감성 검증 에이전트 테스트

이 모듈은 analyze_sensitivity_with_agent 함수의 테스트를 제공합니다.
"""

import pytest
import logging
from dotenv import load_dotenv
from unittest.mock import patch, MagicMock
from datetime import datetime
import uuid

from src.agents.sensitivity_validator import (
    analyze_sensitivity_with_agent,
    SensitivityValidationRequest,
    SensitivityAnalysisResult
)
from src.models.job_posting import (
    UserInput, 
    JobTypeEnum, 
    ExperienceLevel,
    SalaryInfo,
    SalaryType,
    WorkLocation,
    WorkLocationEnum
)
from src.exceptions import ValidationError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(override=True)


class TestSensitivityValidator:
    """민감성 검증 에이전트 테스트 클래스"""
    
    @pytest.fixture
    def safe_user_input(self):
        """민감한 내용이 없는 안전한 사용자 입력"""
        return UserInput(
            job_title="백엔드 개발자",
            company_name="테크 스타트업",
            requirements=[
                "Python 3년 이상 경험",
                "Django 또는 FastAPI 프레임워크 경험",
                "RESTful API 설계 및 개발 경험",
                "데이터베이스 설계 및 최적화 경험"
            ],
            preferred_qualifications=[
                "AWS 클라우드 서비스 경험",
                "Docker, Kubernetes 경험",
                "CI/CD 파이프라인 구축 경험"
            ],
            job_type=JobTypeEnum.FULL_TIME,
            experience_level=ExperienceLevel.MID,
            salary_info=SalaryInfo(
                type=SalaryType.ANNUAL,
                min_amount=4000,
                max_amount=6000,
                currency="KRW",
                is_negotiable=True
            ),
            work_location=WorkLocation(
                type=WorkLocationEnum.HYBRID,
                city="서울",
                country="한국"
            ),
            additional_info=["유연근무제", "개발자 성장 지원"]
        )
    
    @pytest.fixture
    def sensitive_user_input(self):
        """민감한 내용이 포함된 사용자 입력"""
        return UserInput(
            job_title="프론트엔드 개발자",
            company_name="전통 기업",
            requirements=[
                "React 2년 이상 경험",
                "25세 이상 35세 미만만 지원 가능",  # 나이 차별
                "남성 개발자 우대",  # 성별 차별
                "서울 거주자만 지원 가능"  # 지역 차별
            ],
            preferred_qualifications=[
                "미혼자 우대",  # 결혼 여부 차별
                "주민등록번호 제출 필수",  # 개인정보 요구
                "가족사항 상세 기재"  # 사생활 침해
            ],
            job_type=JobTypeEnum.FULL_TIME,
            experience_level=ExperienceLevel.JUNIOR,
            additional_info=["외모 단정한 분", "종교 활동 참여 필수"]  # 외모/종교 차별
        )
    
    @pytest.fixture
    def mock_successful_agent_response(self):
        """성공적인 에이전트 응답 모의 객체"""
        mock_response = {
            "structured_response": SensitivityAnalysisResult(
                is_sensitive=False,
                risk_score=2.0,
                detected_issues=[],
                requires_human_review=False,
                sanitized_version=None
            )
        }
        return mock_response
    
    @pytest.fixture 
    def mock_sensitive_agent_response(self):
        """민감한 내용이 감지된 에이전트 응답 모의 객체"""
        mock_response = {
            "structured_response": SensitivityAnalysisResult(
                is_sensitive=True,
                risk_score=8.5,
                detected_issues=[
                    "나이 제한 (25세 이상 35세 미만만 지원 가능)",
                    "성별 차별 (남성 개발자 우대)", 
                    "지역 차별 (서울 거주자만 지원 가능)",
                    "결혼 여부 차별 (미혼자 우대)",
                    "개인정보 과도 요구 (주민등록번호 제출 필수)",
                    "사생활 침해 (가족사항 상세 기재)"
                ],
                requires_human_review=True,
                sanitized_version="수정이 필요한 여러 민감한 표현들이 발견되었습니다."
            )
        }
        return mock_response
    
    def test_analyze_sensitivity_safe_content_real(self, safe_user_input):
        """
        실제 LLM을 사용한 안전한 콘텐츠 테스트
        
        주의: 이 테스트는 실제 API를 호출하므로 API 키가 필요하고 비용이 발생할 수 있습니다.
        """
        # 실제 API 호출 테스트 (선택적 실행)
        pytest.skip("실제 API 호출 테스트는 수동으로 실행하세요")
        
        request = SensitivityValidationRequest(user_input=safe_user_input)
        
        result, metadata = analyze_sensitivity_with_agent(request, thread_id=str(uuid.uuid4()))
        
        # 결과 검증
        assert isinstance(result, SensitivityAnalysisResult)
        assert isinstance(metadata, dict)
        
        # 안전한 콘텐츠이므로 민감성이 낮을 것으로 예상
        assert result.is_sensitive in [True, False]  # 모델 판단에 따라 결정
        assert 0 <= result.risk_score <= 10
        assert isinstance(result.detected_issues, list)
        assert isinstance(result.requires_human_review, bool)
        
        # 메타데이터 검증
        assert "thread_id" in metadata
        assert "generated_by" in metadata
        assert metadata["generated_by"] == "gpt-4o-mini"
        
        logger.info(f"안전한 콘텐츠 분석 결과: 민감성={result.is_sensitive}, 위험도={result.risk_score}")
    
    def test_analyze_sensitivity_sensitive_content_real(self, sensitive_user_input):
        """
        실제 LLM을 사용한 민감한 콘텐츠 테스트
        
        주의: 이 테스트는 실제 API를 호출하므로 API 키가 필요하고 비용이 발생할 수 있습니다.
        """
        # 실제 API 호출 테스트 (선택적 실행)
        pytest.skip("실제 API 호출 테스트는 수동으로 실행하세요")
        
        request = SensitivityValidationRequest(user_input=sensitive_user_input)
        
        result, metadata = analyze_sensitivity_with_agent(request, thread_id=str(uuid.uuid4()))
        
        # 결과 검증
        assert isinstance(result, SensitivityAnalysisResult)
        assert isinstance(metadata, dict)
        
        # 민감한 콘텐츠이므로 높은 위험도 예상
        assert result.is_sensitive == True  # 명확히 민감한 내용이 포함됨
        assert result.risk_score >= 5.0  # 높은 위험도 예상
        assert len(result.detected_issues) > 0  # 문제가 감지되어야 함
        assert result.requires_human_review == True  # 사람의 검토 필요
        
        # 메타데이터 검증
        assert "thread_id" in metadata
        assert "generated_by" in metadata
        
        logger.info(f"민감한 콘텐츠 분석 결과: 민감성={result.is_sensitive}, 위험도={result.risk_score}")
        logger.info(f"감지된 문제 수: {len(result.detected_issues)}")
    
    @patch('src.agents.sensitivity_validator.create_react_agent')
    @patch('src.agents.sensitivity_validator.init_chat_model')
    def test_analyze_sensitivity_safe_content_mock(
        self, 
        mock_init_chat_model, 
        mock_create_react_agent,
        safe_user_input,
        mock_successful_agent_response
    ):
        """Mock을 사용한 안전한 콘텐츠 테스트"""
        # Mock 설정
        mock_llm = MagicMock()
        mock_init_chat_model.return_value = mock_llm
        
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = mock_successful_agent_response
        mock_create_react_agent.return_value = mock_agent
        
        # 테스트 실행
        request = SensitivityValidationRequest(user_input=safe_user_input)
        result, metadata = analyze_sensitivity_with_agent(request, thread_id=str(uuid.uuid4()))
        
        # Mock 호출 확인
        mock_init_chat_model.assert_called_once()
        mock_create_react_agent.assert_called_once()
        mock_agent.invoke.assert_called_once()
        
        # 결과 검증
        assert isinstance(result, SensitivityAnalysisResult)
        assert result.is_sensitive == False
        assert result.risk_score == 2.0
        assert len(result.detected_issues) == 0
        assert result.requires_human_review == False
        
        # 메타데이터 검증
        assert isinstance(metadata, dict)
        assert "thread_id" in metadata
        assert "generated_by" in metadata
        
        logger.info("Mock을 사용한 안전한 콘텐츠 테스트 통과")
    
    @patch('src.agents.sensitivity_validator.create_react_agent')
    @patch('src.agents.sensitivity_validator.init_chat_model')
    def test_analyze_sensitivity_sensitive_content_mock(
        self, 
        mock_init_chat_model, 
        mock_create_react_agent,
        sensitive_user_input,
        mock_sensitive_agent_response
    ):
        """Mock을 사용한 민감한 콘텐츠 테스트"""
        # Mock 설정
        mock_llm = MagicMock()
        mock_init_chat_model.return_value = mock_llm
        
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = mock_sensitive_agent_response
        mock_create_react_agent.return_value = mock_agent
        
        # 테스트 실행
        request = SensitivityValidationRequest(user_input=sensitive_user_input)
        result, metadata = analyze_sensitivity_with_agent(request, thread_id=str(uuid.uuid4()))
        
        # Mock 호출 확인
        mock_init_chat_model.assert_called_once()
        mock_create_react_agent.assert_called_once()
        mock_agent.invoke.assert_called_once()
        
        # 결과 검증
        assert isinstance(result, SensitivityAnalysisResult)
        assert result.is_sensitive == True
        assert result.risk_score == 8.5
        assert len(result.detected_issues) > 0
        assert result.requires_human_review == True
        
        # 감지된 문제 상세 확인 (List[str] 형태로 변경됨)
        assert any("나이 제한" in issue for issue in result.detected_issues)
        assert any("성별 차별" in issue for issue in result.detected_issues)
        assert any("개인정보" in issue for issue in result.detected_issues)
        
        # 메타데이터 검증
        assert isinstance(metadata, dict)
        assert "thread_id" in metadata
        assert "generated_by" in metadata
        
        logger.info("Mock을 사용한 민감한 콘텐츠 테스트 통과")
        logger.info(f"감지된 문제 내용: {result.detected_issues}")
    
    @patch('src.agents.sensitivity_validator.create_react_agent')
    @patch('src.agents.sensitivity_validator.init_chat_model')
    def test_analyze_sensitivity_error_handling(
        self, 
        mock_init_chat_model, 
        mock_create_react_agent,
        safe_user_input
    ):
        """에러 처리 테스트"""
        # Mock이 예외를 발생시키도록 설정
        mock_init_chat_model.side_effect = Exception("API 연결 실패")
        
        # 테스트 실행 및 예외 확인
        request = SensitivityValidationRequest(user_input=safe_user_input)
        
        with pytest.raises(ValidationError) as exc_info:
            analyze_sensitivity_with_agent(request, thread_id=str(uuid.uuid4()))
        
        assert "민감성 분석 중 오류 발생" in str(exc_info.value)
        logger.info("에러 처리 테스트 통과")
    
    @patch('src.agents.sensitivity_validator.create_react_agent')
    @patch('src.agents.sensitivity_validator.init_chat_model')
    def test_analyze_sensitivity_no_response(
        self, 
        mock_init_chat_model, 
        mock_create_react_agent,
        safe_user_input
    ):
        """응답 없음 에러 처리 테스트"""
        # Mock 설정 - 응답에서 generate_structured_response가 없는 경우
        mock_llm = MagicMock()
        mock_init_chat_model.return_value = mock_llm
        
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"other_key": "value"}  # 잘못된 응답
        mock_create_react_agent.return_value = mock_agent
        
        # 테스트 실행 및 예외 확인
        request = SensitivityValidationRequest(user_input=safe_user_input)
        
        with pytest.raises(ValidationError) as exc_info:
            analyze_sensitivity_with_agent(request, thread_id=str(uuid.uuid4()))
        
        assert "민감성 분석 결과를 받지 못했습니다" in str(exc_info.value)
        logger.info("응답 없음 에러 처리 테스트 통과")


# 실제 테스트 실행을 위한 헬퍼 함수들
def run_real_test_safe():
    """실제 API를 사용한 안전한 콘텐츠 테스트 실행"""
    safe_input = UserInput(
        job_title="풀스택 개발자",
        company_name="혁신 기업",
        requirements=[
            "JavaScript 및 Python 경험",
            "프론트엔드 및 백엔드 개발 경험",
            "협업 능력 및 문제 해결 능력"
        ],
        preferred_qualifications=[
            "클라우드 서비스 경험",
            "오픈소스 기여 경험"
        ],
        job_type=JobTypeEnum.FULL_TIME,
        experience_level=ExperienceLevel.MID,
        additional_info=["유연근무제", "성장 지원 프로그램"]
    )
    
    request = SensitivityValidationRequest(user_input=safe_input)
    
    try:
        result, metadata = analyze_sensitivity_with_agent(request, thread_id=str(uuid.uuid4()))
        print(f"✅ 안전한 콘텐츠 분석 완료:")
        print(f"   민감성: {result.is_sensitive}")
        print(f"   위험도: {result.risk_score}")
        print(f"   감지된 문제 수: {len(result.detected_issues)}")
        print(f"   사람 검토 필요: {result.requires_human_review}")
        print(f"   모델: {metadata['generated_by']}")
        return result, metadata
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return None, None


def run_real_test_sensitive():
    """실제 API를 사용한 민감한 콘텐츠 테스트 실행"""
    sensitive_input = UserInput(
        job_title="마케팅 담당자",
        company_name="전통 회사",
        requirements=[
            "30세 미만 여성만 지원 가능",  # 나이 + 성별 차별
            "용모 단정하고 키 160cm 이상",  # 외모 차별
            "미혼자 우대, 결혼 계획 없는 분"  # 결혼 상태 차별
        ],
        preferred_qualifications=[
            "주민등록번호 및 가족관계증명서 제출",  # 개인정보 과도 요구
            "특정 종교 신자 우대"  # 종교 차별
        ],
        job_type=JobTypeEnum.FULL_TIME,
        experience_level=ExperienceLevel.ENTRY,
        additional_info=["외모 중시", "특정 종교 우대"]
    )
    
    request = SensitivityValidationRequest(user_input=sensitive_input)
    
    try:
        result, metadata = analyze_sensitivity_with_agent(request, thread_id=str(uuid.uuid4()))
        print(f"✅ 민감한 콘텐츠 분석 완료:")
        print(f"   민감성: {result.is_sensitive}")
        print(f"   위험도: {result.risk_score}")
        print(f"   감지된 문제 수: {len(result.detected_issues)}")
        print(f"   사람 검토 필요: {result.requires_human_review}")
        print(f"   모델: {metadata['generated_by']}")
        
        if result.detected_issues:
            print("   감지된 문제 상세:")
            for issue in result.detected_issues:
                print(f"    - {issue}")
        
        return result, metadata
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return None, None


if __name__ == "__main__":
    """직접 실행시 실제 API 테스트 수행"""
    print("🧪 민감성 검증 에이전트 실제 테스트 실행\n")
    
    print("1. 안전한 콘텐츠 테스트:")
    run_real_test_safe()
    print()
    
    print("2. 민감한 콘텐츠 테스트:")
    run_real_test_sensitive()
    print()
    
    print("💡 전체 테스트 스위트 실행: pytest tests/test_sensitivity_validator.py -v")
