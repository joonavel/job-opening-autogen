"""
민감성 검증 에이전트 Human-in-the-Loop 테스트

이 모듈은 analyze_sensitivity_with_agent 함수의 human feedback 기능을 테스트합니다.
"""

import pytest
import logging
import uuid
import json
from dotenv import load_dotenv
from unittest.mock import patch, MagicMock

from src.agents.sensitivity_validator import (
    analyze_sensitivity_with_agent,
    SensitivityValidationRequest,
    get_human_feedback
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


class TestSensitivityHumanFeedback:
    """민감성 검증 에이전트 Human Feedback 테스트 클래스"""
    
    @pytest.fixture
    def sensitive_user_input(self):
        """민감한 내용이 포함된 사용자 입력"""
        return UserInput(
            job_title="마케팅 담당자",
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
    def mock_corrected_user_input(self):
        """첨삭된 사용자 입력 (민감한 내용이 제거됨)"""
        return UserInput(
            job_title="마케팅 담당자",
            company_name="전통 기업",
            requirements=[
                "React 2년 이상 경험",
                "마케팅 관련 업무 경험 우대",
                "창의적 사고와 문제 해결 능력",
                "원활한 커뮤니케이션 능력"
            ],
            preferred_qualifications=[
                "디지털 마케팅 툴 사용 경험",
                "데이터 분석 역량",
                "브랜딩 및 콘텐츠 제작 경험"
            ],
            job_type=JobTypeEnum.FULL_TIME,
            experience_level=ExperienceLevel.JUNIOR,
            additional_info=["성장 지향적인 기업 문화", "지속적인 학습 기회 제공"]
        )
    
    def test_get_human_feedback_tool(self):
        """get_human_feedback 도구 기본 동작 테스트"""
        question = "나이 제한 조건이 발견되었습니다. 어떻게 수정하시겠습니까?"
        
        # get_human_feedback 함수는 Interrupt 객체를 반환해야 함
        result = get_human_feedback(question)
        
        # Interrupt 객체가 반환되는지 확인
        from langgraph.types import Interrupt
        assert isinstance(result, Interrupt)
        assert result.value["question"] == question
        
        logger.info("get_human_feedback 도구 테스트 통과")
    
    @patch('src.agents.sensitivity_validator.create_react_agent')
    @patch('src.agents.sensitivity_validator.init_chat_model')
    def test_human_feedback_workflow_mock(
        self, 
        mock_init_chat_model, 
        mock_create_react_agent,
        sensitive_user_input,
        mock_corrected_user_input
    ):
        """Mock을 사용한 Human Feedback 워크플로우 테스트"""
        
        # Mock 설정
        mock_llm = MagicMock()
        mock_init_chat_model.return_value = mock_llm
        
        # Agent가 첨삭된 UserInput을 반환하도록 설정
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "structured_response": mock_corrected_user_input
        }
        mock_create_react_agent.return_value = mock_agent
        
        # 테스트 실행
        request = SensitivityValidationRequest(user_input=sensitive_user_input)
        result, metadata = analyze_sensitivity_with_agent(request, thread_id=str(uuid.uuid4()))
        
        # Mock 호출 확인
        mock_init_chat_model.assert_called_once()
        mock_create_react_agent.assert_called_once()
        mock_agent.invoke.assert_called_once()
        
        # Agent가 올바른 도구들과 함께 생성되었는지 확인
        create_args = mock_create_react_agent.call_args
        assert len(create_args[1]['tools']) == 1  # get_human_feedback 도구
        assert create_args[1]['response_format'] == UserInput
        
        # 결과 검증 - 첨삭된 UserInput이 반환되어야 함
        assert isinstance(result, UserInput)
        assert result.job_title == "마케팅 담당자"
        
        # 민감한 내용이 제거되었는지 확인
        requirements_text = " ".join(result.requirements)
        assert "25세 이상" not in requirements_text
        assert "남성 개발자" not in requirements_text
        assert "서울 거주자만" not in requirements_text
        
        # 메타데이터 검증
        assert isinstance(metadata, dict)
        assert "thread_id" in metadata
        assert "generated_by" in metadata
        
        logger.info("Mock을 사용한 Human Feedback 워크플로우 테스트 통과")
    
    @patch('src.agents.sensitivity_validator.create_react_agent')
    @patch('src.agents.sensitivity_validator.init_chat_model')
    def test_human_feedback_error_handling(
        self, 
        mock_init_chat_model, 
        mock_create_react_agent,
        sensitive_user_input
    ):
        """Human Feedback 과정에서의 에러 처리 테스트"""
        
        # Mock이 예외를 발생시키도록 설정
        mock_init_chat_model.side_effect = Exception("Human feedback 처리 실패")
        
        # 테스트 실행 및 예외 확인
        request = SensitivityValidationRequest(user_input=sensitive_user_input)
        
        with pytest.raises(ValidationError) as exc_info:
            analyze_sensitivity_with_agent(request, thread_id=str(uuid.uuid4()))
        
        assert "민감성 분석 중 오류 발생" in str(exc_info.value)
        logger.info("Human Feedback 에러 처리 테스트 통과")
    
    @patch('src.agents.sensitivity_validator.create_react_agent')
    @patch('src.agents.sensitivity_validator.init_chat_model')
    def test_no_structured_response_error(
        self, 
        mock_init_chat_model, 
        mock_create_react_agent,
        sensitive_user_input
    ):
        """structured_response가 없을 때의 에러 처리 테스트"""
        
        # Mock 설정 - structured_response가 없는 응답
        mock_llm = MagicMock()
        mock_init_chat_model.return_value = mock_llm
        
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"other_key": "value"}  # 잘못된 응답
        mock_create_react_agent.return_value = mock_agent
        
        # 테스트 실행 및 예외 확인
        request = SensitivityValidationRequest(user_input=sensitive_user_input)
        
        with pytest.raises(ValidationError) as exc_info:
            analyze_sensitivity_with_agent(request, thread_id=str(uuid.uuid4()))
        
        assert "민감성 기반 첨삭 결과를 받지 못했습니다" in str(exc_info.value)
        logger.info("structured_response 없음 에러 처리 테스트 통과")
    
    def test_user_input_serialization(self, sensitive_user_input):
        """UserInput의 JSON 직렬화 테스트 (한글 보존 확인)"""
        
        # 한글이 포함된 UserInput을 JSON으로 변환
        user_input_text = json.dumps(sensitive_user_input.model_dump(), ensure_ascii=False, indent=2)
        
        # 한글이 제대로 보존되었는지 확인
        assert "마케팅 담당자" in user_input_text
        assert "전통 기업" in user_input_text
        assert "\\u" not in user_input_text  # 유니코드 이스케이프가 없어야 함
        
        # JSON이 유효한지 확인
        parsed_data = json.loads(user_input_text)
        assert parsed_data["job_title"] == "마케팅 담당자"
        assert parsed_data["company_name"] == "전통 기업"
        
        logger.info("UserInput JSON 직렬화 테스트 통과 (한글 보존 확인됨)")


# 실제 Human Feedback 시뮬레이션을 위한 헬퍼 함수들
def simulate_human_feedback_session():
    """실제 Human Feedback 세션 시뮬레이션"""
    
    print("🤖 민감성 검증 에이전트 Human Feedback 시뮬레이션")
    print("=" * 60)
    
    # 민감한 내용이 포함된 입력 생성
    sensitive_input = UserInput(
        job_title="개발자",
        company_name="IT 회사",
        requirements=[
            "Python 경험 3년 이상",
            "25세 이상 30세 미만 남성",  # 차별적 표현
            "서울 거주자만 지원 가능"    # 지역 차별
        ],
        preferred_qualifications=[
            "미혼자 우대",              # 결혼 상태 차별
            "주민등록번호 제출 필수"     # 개인정보 과도 요구
        ],
        job_type=JobTypeEnum.FULL_TIME,
        experience_level=ExperienceLevel.MID,
        additional_info=["외모 단정한 분 우대"]
    )
    
    print("📝 원본 입력:")
    print(f"   제목: {sensitive_input.job_title}")
    print(f"   회사: {sensitive_input.company_name}")
    print("   요구사항:")
    for req in sensitive_input.requirements:
        print(f"     - {req}")
    print("   우대사항:")
    for pref in sensitive_input.preferred_qualifications:
        print(f"     - {pref}")
    print(f"   추가정보: {sensitive_input.additional_info}")
    
    print("\n🚨 감지된 민감한 내용:")
    print("   - 나이 제한 (25세 이상 30세 미만)")
    print("   - 성별 차별 (남성)")
    print("   - 지역 차별 (서울 거주자만)")
    print("   - 결혼 상태 차별 (미혼자 우대)")
    print("   - 개인정보 과도 요구 (주민등록번호)")
    print("   - 외모 차별 (외모 단정한 분)")
    
    print("\n🔧 Human Feedback 기반 첨삭 예시:")
    
    corrected_input = UserInput(
        job_title="개발자",
        company_name="IT 회사",
        requirements=[
            "Python 경험 3년 이상",
            "웹 개발 프레임워크 경험",
            "데이터베이스 설계 및 최적화 경험"
        ],
        preferred_qualifications=[
            "오픈소스 기여 경험",
            "클라우드 서비스 활용 경험"
        ],
        job_type=JobTypeEnum.FULL_TIME,
        experience_level=ExperienceLevel.MID,
        additional_info=["성장 지향적인 개발 문화"]
    )
    
    print("✅ 첨삭 완료:")
    print(f"   제목: {corrected_input.job_title}")
    print(f"   회사: {corrected_input.company_name}")
    print("   요구사항:")
    for req in corrected_input.requirements:
        print(f"     - {req}")
    print("   우대사항:")
    for pref in corrected_input.preferred_qualifications:
        print(f"     - {pref}")
    print(f"   추가정보: {corrected_input.additional_info}")
    
    print("\n💡 첨삭 요약:")
    print("   - 차별적 표현 제거됨")
    print("   - 개인정보 요구 제거됨")
    print("   - 전문적이고 포용적인 내용으로 대체됨")
    print("   - 업무 관련 요구사항으로 변경됨")


if __name__ == "__main__":
    """직접 실행시 Human Feedback 시뮬레이션 수행"""
    simulate_human_feedback_session()
    print("\n🧪 테스트 실행 명령어:")
    print("pytest tests/test_sensitivity_human_feedback.py -v")
