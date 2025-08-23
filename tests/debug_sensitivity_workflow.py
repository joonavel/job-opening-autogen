"""
민감성 검증 워크플로우 디버깅 및 테스트

실제 워크플로우가 동작하는지 확인하고 문제점을 찾아봅니다.
"""

import logging
import uuid
from dotenv import load_dotenv

from src.agents.sensitivity_validator import (
    analyze_sensitivity_with_agent,
    SensitivityValidationRequest
)
from src.models.job_posting import (
    UserInput, 
    JobTypeEnum, 
    ExperienceLevel
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(override=True)


def create_test_input():
    """테스트용 민감한 내용이 포함된 입력 생성"""
    return UserInput(
        job_title="개발자",
        company_name="테스트 회사",
        requirements=[
            "Python 경험 2년 이상",
            "25세 이상 30세 미만만 지원 가능",  # 나이 차별
            "남성 개발자 우대"  # 성별 차별
        ],
        preferred_qualifications=[
            "미혼자 우대"  # 결혼 상태 차별
        ],
        job_type=JobTypeEnum.FULL_TIME,
        experience_level=ExperienceLevel.MID,
        additional_info=["외모 단정한 분"]
    )


def test_workflow_execution():
    """실제 워크플로우 실행 테스트"""
    print("🧪 민감성 검증 워크플로우 실행 테스트 시작")
    print("=" * 60)
    
    try:
        # 테스트 입력 생성
        test_input = create_test_input()
        request = SensitivityValidationRequest(user_input=test_input)
        thread_id = str(uuid.uuid4())
        
        print("📝 입력 데이터:")
        print(f"   제목: {test_input.job_title}")
        print(f"   회사: {test_input.company_name}")
        print("   요구사항:")
        for req in test_input.requirements:
            print(f"     - {req}")
        print("   우대사항:")
        for pref in test_input.preferred_qualifications:
            print(f"     - {pref}")
        print(f"   추가정보: {test_input.additional_info}")
        
        print(f"\n🚀 워크플로우 실행 (thread_id: {thread_id[:8]}...)")
        
        # 실제 워크플로우 실행
        result, metadata = analyze_sensitivity_with_agent(request, thread_id)
        
        print("\n✅ 워크플로우 실행 성공!")
        print(f"결과 타입: {type(result)}")
        print(f"메타데이터: {metadata}")
        
        if hasattr(result, 'job_title'):
            print(f"첨삭된 제목: {result.job_title}")
            print(f"첨삭된 요구사항: {result.requirements}")
            print(f"전체 결과: {result}")
        else:
            print(f"결과 내용: {result}")
        
        return True, result, metadata
        
    except Exception as e:
        print(f"\n❌ 워크플로우 실행 실패!")
        print(f"에러 타입: {type(e).__name__}")
        print(f"에러 메시지: {str(e)}")
        logger.error(f"워크플로우 실행 실패: {str(e)}", exc_info=True)
        return False, None, None

if __name__ == "__main__":
    print("🔧 민감성 검증 워크플로우 디버깅")
    print("=" * 60)

    
    workflow_ok, result, metadata = test_workflow_execution()
    
    if workflow_ok:
        print("\n🎉 테스트 통과!")
        print("워크플로우가 정상적으로 동작합니다.")
    else:
        print("\n⚠️  워크플로우 실행에 문제가 있습니다.")
        print("Human Feedback 처리 로직을 확인해야 합니다.")

