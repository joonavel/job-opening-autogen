"""
LangGraph 워크플로우 기본 테스트 스크립트

워크플로우의 기본 동작을 검증하고 테스트합니다.
"""

import sys
import os
from datetime import datetime
import logging
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리를 Python path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# .env 파일 로드 (명시적 경로 지정)
env_path = project_root / ".env"
load_result = load_dotenv(env_path, override=True)
print(f"🔍 .env 파일 로드 - 경로: {env_path}, 성공: {load_result}, 파일 존재: {env_path.exists()}")

from src.workflows.job_posting_workflow import get_workflow, WorkflowState
from src.models.job_posting import (
    UserInput, CompanyData, JobTypeEnum, ExperienceLevel,
    SalaryInfo, SalaryType, WorkLocation, WorkLocationEnum
)
from src.database import init_database, create_tables, test_db_connection

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_user_input() -> UserInput:
    """테스트용 사용자 입력 데이터 생성"""
    
    salary_info = SalaryInfo(
        type=SalaryType.ANNUAL,
        min_amount=4000,
        max_amount=6000,
        currency="KRW",
        is_negotiable=True
    )
    
    work_location = WorkLocation(
        type=WorkLocationEnum.HYBRID,
        city="서울",
        address="강남구 테헤란로 123",
        country="한국"
    )
    
    user_input = UserInput(
        job_title="백엔드 개발자",
        company_name="일일일퍼센트",
        requirements=[
            "Python, FastAPI 프레임워크 경험 3년 이상",
            "데이터베이스 설계 및 최적화 경험",
            "REST API 설계 및 개발 경험",
            "Git을 활용한 협업 경험"
        ],
        preferred_qualifications=[
            "AI/ML 모델 서빙 경험",
            "Docker, Kubernetes 사용 경험",
            "AWS 클라우드 서비스 활용 경험"
        ],
        job_type=JobTypeEnum.FULL_TIME,
        experience_level=ExperienceLevel.MID,
        salary_info=salary_info,
        work_location=work_location,
        additional_info=[
            "4대보험적용", "연차 15일", "교육비 지원", "인원수 5-10명", "Python, FastAPI, PostgreSQL, Redis, Docker 사용 우대"
        ]
    )
    
    return user_input


def create_test_raw_input() -> str:
    """테스트용 자연어 입력 데이터 생성"""
    
    raw_input = """
일일일퍼센트에서 백엔드 개발자를 모집합니다.

- 직무: 백엔드 개발자 (정규직)
- 경력: 3년 이상 중급 개발자
- 급여: 연봉 4000만원~6000만원 (협의 가능)
- 근무지: 서울 강남구 테헤란로 123 (하이브리드 근무)

필수 요구사항:
- Python, FastAPI 프레임워크 경험 3년 이상
- 데이터베이스 설계 및 최적화 경험
- REST API 설계 및 개발 경험  
- Git을 활용한 협업 경험

우대사항:
- AI/ML 모델 서빙 경험
- Docker, Kubernetes 사용 경험
- AWS 클라우드 서비스 활용 경험
- 20 ~ 25 대 남성 지원자 우대
- 미혼자 우대

복리후생:
- 4대보험, 연차 15일, 교육비 지원
- 팀 규모: 5-10명
- 기술 스택: Python, FastAPI, PostgreSQL, Redis, Docker
""".strip()
    
    return raw_input


def test_workflow_basic():
    """기본 워크플로우 실행 테스트"""
    print("=" * 60)
    print("LangGraph 워크플로우 기본 테스트 시작")
    print("=" * 60)
    
    try:
        # 0. 데이터베이스 초기화
        print("0. 데이터베이스 초기화 중...")
        
        # 데이터베이스 연결 초기화
        init_database()
        print("✓ 데이터베이스 연결 초기화 완료")
        
        # 연결 테스트
        if not test_db_connection():
            print("✗ 데이터베이스 연결 테스트 실패")
            print("Docker 컨테이너가 실행 중인지 확인하세요: docker ps")
            exit(1)
        print("✓ 데이터베이스 연결 테스트 완료")
        
        # 테이블 생성
        create_tables()
        print("✓ 데이터베이스 테이블 생성 완료")
        # 1. 워크플로우 인스턴스 생성
        print("\n1. 워크플로우 인스턴스 생성 중...")
        workflow = get_workflow()
        print("✓ 워크플로우 인스턴스 생성 완료")
        
        # 2. 테스트 데이터 준비
        print("\n2. 테스트 데이터 준비 중...")
        user_input = create_test_user_input()
        print(f"✓ 테스트 데이터 준비 완료: {user_input.job_title} at {user_input.company_name}")
        
        # 3. 워크플로우 실행
        print("\n3. 워크플로우 실행 중...")
        workflow_id = f"test_workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        result = workflow.run(raw_input=None, user_input=user_input, workflow_id=workflow_id)
        
        print(f"✓ 워크플로우 실행 완료: {workflow_id}")
        
        # 4. 결과 검증
        print("\n4. 실행 결과 검증...")
        
        if not result:
            print("✗ 실행 결과가 없습니다")
            return False
        
        if 'job_posting_draft' in result:
            final_state = result
        else:
            final_state = None
        
        if not final_state:
            print("✗ 최종 상태를 찾을 수 없습니다")
            print(f"결과 구조: {list(result.keys()) if hasattr(result, 'keys') else type(result)}")
            return False
            
        # 필수 키들이 있는지 확인
        required_keys = ['workflow_id', 'current_step', 'step_count']
        for key in required_keys:
            if key not in final_state:
                print(f"✗ 필수 키 '{key}'가 결과에 없습니다")
                return False
        
        print(f"✓ 워크플로우 ID: {final_state['workflow_id']}")
        print(f"✓ 최종 단계: {final_state['current_step']}")  
        print(f"✓ 실행 단계 수: {final_state['step_count']}")
        
        # 오류 확인
        if 'errors' in final_state and final_state['errors']:
            print(f"⚠ 발생한 오류들:")
            for error in final_state['errors']:
                print(f"  - {error}")
        else:
            print("✓ 오류 없이 실행 완료")
        
        # 채용공고 초안 확인
        if 'job_posting_draft' in final_state and final_state['job_posting_draft']:
            draft = final_state['job_posting_draft']
            print(f"✓ 채용공고 초안 생성 완료:")
            print(f"  - 제목: {draft.title}")
            print(f"  - 회사: {draft.company_name}")
            print(f"  - 설명 길이: {len(draft.job_description)}자")
            print(f"  - 필수 요구사항: {len(draft.requirements)}개")
            print(f"  - 생성 모델: {final_state['draft_metadata']['generated_by']}")
        else:
            print("⚠ 채용공고 초안이 생성되지 않았습니다")
        
        print("\n5. 워크플로우 상태 조회 테스트...")
        state = workflow.get_workflow_state(workflow_id)
        if state:
            print(f"✓ 상태 조회 성공: {len(state)}개 키")
        else:
            print("⚠ 상태 조회 실패 또는 상태 없음")
        
        return True
        
    except Exception as e:
        print(f"✗ 테스트 실행 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_natural_language():
    """자연어 입력 워크플로우 실행 테스트"""
    print("=" * 60)
    print("LangGraph 워크플로우 자연어 입력 테스트 시작")
    print("=" * 60)
    
    try:
        # 0. 데이터베이스 초기화 (기본 테스트와 동일)
        print("0. 데이터베이스 초기화 중...")
        
        # 데이터베이스 연결 초기화
        init_database()
        print("✓ 데이터베이스 연결 초기화 완료")
        
        # 연결 테스트
        if not test_db_connection():
            print("✗ 데이터베이스 연결 테스트 실패")
            print("Docker 컨테이너가 실행 중인지 확인하세요: docker ps")
            exit(1)
        print("✓ 데이터베이스 연결 테스트 완료")
        
        # 테이블 생성
        create_tables()
        print("✓ 데이터베이스 테이블 생성 완료")
        
        # 1. 워크플로우 인스턴스 생성
        print("\n1. 워크플로우 인스턴스 생성 중...")
        workflow = get_workflow()
        print("✓ 워크플로우 인스턴스 생성 완료")
        
        # 2. 자연어 테스트 데이터 준비
        print("\n2. 자연어 테스트 데이터 준비 중...")
        raw_input = create_test_raw_input()
        print(f"✓ 자연어 테스트 데이터 준비 완료 ({len(raw_input)}자)")
        print("자연어 입력 미리보기:")
        print(f"'{raw_input[:100]}...'")
        
        # 3. 자연어 입력으로 워크플로우 실행
        print("\n3. 자연어 입력 워크플로우 실행 중...")
        workflow_id = f"test_natural_language_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        result = workflow.run(raw_input=raw_input, user_input=None, workflow_id=workflow_id)
        
        print(f"✓ 자연어 워크플로우 실행 완료: {workflow_id}")
        
        # 4. 결과 검증
        print("\n4. 자연어 입력 실행 결과 검증...")
        
        if not result:
            print("✗ 실행 결과가 없습니다")
            return False
            
        if 'job_posting_draft' in result:
            final_state = result
        else:
            final_state = None
        
        if not final_state:
            print("✗ 최종 상태를 찾을 수 없습니다")
            print(f"결과 구조: {list(result.keys()) if hasattr(result, 'keys') else type(result)}")
            return False
            
        # 필수 키들이 있는지 확인
        required_keys = ['workflow_id', 'current_step', 'step_count', 'raw_input', 'user_input']
        for key in required_keys:
            if key not in final_state:
                print(f"✗ 필수 키 '{key}'가 결과에 없습니다")
                return False
        
        print(f"✓ 워크플로우 ID: {final_state['workflow_id']}")
        print(f"✓ 최종 단계: {final_state['current_step']}")  
        print(f"✓ 실행 단계 수: {final_state['step_count']}")
        
        # 자연어 처리 결과 확인
        if final_state.get('user_input'):
            structured_input = final_state['user_input']
            print(f"✓ 자연어 구조화 성공:")
            print(f"  - 추출된 직무명: {structured_input.job_title}")
            print(f"  - 추출된 회사명: {structured_input.company_name}")
            print(f"  - 추출된 요구사항 수: {len(structured_input.requirements)}개")
            print(f"  - 추출된 우대사항 수: {len(structured_input.preferred_qualifications or [])}개")
        else:
            print("⚠ 자연어 구조화 결과가 없습니다")
        
        # 기업 데이터 확인
        if final_state.get('company_data'):
            company_data = final_state['company_data']
            print(f"✓ 기업 데이터 검색 완료:")
            print(f"  - 회사명: {company_data.company_name}")
            print(f"  - 분류: {company_data.company_classification or 'N/A'}")
        else:
            print("⚠ 기업 데이터가 없습니다")
            
        # 환각 검증 추적 정보 확인
        if final_state.get('data_source_tracking'):
            tracking = final_state['data_source_tracking']
            print(f"✓ 환각 검증용 추적 정보:")
            print(f"  - 데이터 완성도 점수: {tracking.get('data_completeness_score', 0)}%")
            print(f"  - 검증 플래그: {len(tracking.get('verification_flags', []))}개")
            print(f"  - 검색 시도: {len(tracking.get('search_attempts', []))}회")
        else:
            print("⚠ 환각 검증용 추적 정보가 없습니다")
        
        # 오류 확인
        if 'errors' in final_state and final_state['errors']:
            print(f"⚠ 발생한 오류들:")
            for error in final_state['errors']:
                print(f"  - {error}")
        else:
            print("✓ 오류 없이 실행 완료")
        
        # 채용공고 초안 확인
        if 'job_posting_draft' in final_state and final_state['job_posting_draft']:
            draft = final_state['job_posting_draft']
            print(f"✓ 자연어로부터 채용공고 초안 생성 완료:")
            print(f"  - 제목: {draft.title}")
            print(f"  - 회사: {draft.company_name}")
            print(f"  - 설명 길이: {len(draft.job_description)}자")
            print(f"  - 필수 요구사항: {len(draft.requirements)}개")
            print(f"  - 생성 모델: {final_state['draft_metadata']['generated_by']}")
            
        else:
            print("⚠ 채용공고 초안이 생성되지 않았습니다")
        
        print("\n5. 자연어 워크플로우 상태 조회 테스트...")
        state = workflow.get_workflow_state(workflow_id)
        if state:
            print(f"✓ 상태 조회 성공: {len(state)}개 키")
        else:
            print("⚠ 상태 조회 실패 또는 상태 없음")
        
        return True
        
    except Exception as e:
        print(f"✗ 자연어 테스트 실행 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """메인 테스트 함수"""
    print("LangGraph 채용공고 생성 워크플로우 테스트")
    print(f"테스트 시작 시간: {datetime.now()}")
    
    test_results = []
    
    # # 기본 워크플로우 테스트
    # print("\n📋 테스트 1: 구조화된 입력 워크플로우")
    # basic_test_result = test_workflow_basic()
    # test_results.append(("구조화된 입력 워크플로우", basic_test_result))
    
    # 자연어 입력 워크플로우 테스트  
    print("\n🗣️ 테스트 2: 자연어 입력 워크플로우")
    natural_language_test_result = test_workflow_natural_language()
    test_results.append(("자연어 입력 워크플로우", natural_language_test_result))
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\n총 테스트: {total}개")
    print(f"통과: {passed}개")
    print(f"실패: {total - passed}개")
    
    if passed == total:
        print("\n🎉 모든 테스트가 성공적으로 완료되었습니다!")
        return 0
    else:
        print(f"\n⚠ {total - passed}개 테스트가 실패했습니다.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
