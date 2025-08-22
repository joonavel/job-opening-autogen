#!/usr/bin/env python3
"""
데이터베이스 연결 및 기능 테스트 스크립트
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 파이썬 패스에 추가
try:
    from config.settings import PROJECT_ROOT
    project_root = PROJECT_ROOT
except ImportError:
    project_root = Path(__file__).parent.parent.parent

sys.path.insert(0, str(project_root))

from src.database import (
    init_database, create_tables, test_db_connection, 
    db_session_scope, DataRepositoryManager
)
from src.database.data_loader import OpenAPIDataLoader, initialize_database_with_sample_data
from src.utils.logging import get_logger

logger = get_logger(__name__)


def test_database_connection():
    """데이터베이스 연결 테스트"""
    print("=" * 50)
    print("🔍 데이터베이스 연결 테스트")
    print("=" * 50)
    
    try:
        # 데이터베이스 초기화
        init_database()
        print("✅ 데이터베이스 초기화 성공")
        
        # 연결 테스트
        if test_db_connection():
            print("✅ 데이터베이스 연결 테스트 성공")
        else:
            print("❌ 데이터베이스 연결 테스트 실패")
            return False
        
        return True
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        return False


def test_table_creation():
    """테이블 생성 테스트"""
    print("\n" + "=" * 50)
    print("🏗️  테이블 생성 테스트")
    print("=" * 50)
    
    try:
        create_tables()
        print("✅ 테이블 생성 성공")
        return True
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        return False


def test_repository_operations():
    """리포지토리 작업 테스트"""
    print("\n" + "=" * 50)
    print("🗃️  리포지토리 작업 테스트")
    print("=" * 50)
    
    try:
        with db_session_scope() as session:
            repo = DataRepositoryManager(session)
            
            # 1. 직종 분류 테스트
            print("📋 직종 분류 생성 테스트...")
            category = repo.job_categories.create_or_get_category("TEST01", "테스트 직종")
            print(f"✅ 직종 분류 생성: {category.jobs_name} ({category.jobs_code})")
            
            # 2. 기업 생성 테스트
            print("🏢 기업 생성 테스트...")
            company_data = {
                'emp_co_no': 'TEST001',
                'company_name': '테스트 회사',
                'business_number': '1234567890',
                'intro_summary': '테스트용 회사입니다'
            }
            company = repo.companies.create_company(company_data)
            print(f"✅ 기업 생성: {company.company_name} ({company.emp_co_no})")
            
            # 3. 복리후생 정보 추가 테스트
            print("💰 복리후생 정보 추가 테스트...")
            welfare_data = [
                {'cdKorNm': '휴무/휴가', 'welfareCont': '연차/반차/경조휴가'},
                {'cdKorNm': '보상/지원', 'welfareCont': '4대보험/퇴직금'}
            ]
            welfare_items = repo.companies.add_welfare_items(company.id, welfare_data)
            print(f"✅ 복리후생 {len(welfare_items)}개 항목 추가")
            
            # 4. 채용공고 생성 테스트
            print("📢 채용공고 생성 테스트...")
            posting_data = {
                'emp_seq_no': 'TEST001',
                'title': '테스트 채용공고',
                'company_id': company.id,
                'job_category_id': category.id,
                'employment_type': '정규직'
            }
            posting = repo.job_postings.create_job_posting(posting_data)
            print(f"✅ 채용공고 생성: {posting.title} ({posting.emp_seq_no})")
            
            # 5. 전형 단계 추가 테스트
            print("📝 전형 단계 추가 테스트...")
            steps_data = [
                {'selsNm': '서류전형', 'selsCont': '서류 검토'},
                {'selsNm': '면접', 'selsCont': '대면 면접'},
                {'selsNm': '최종합격', 'selsCont': '최종 결과 발표'}
            ]
            steps = repo.job_postings.add_selection_steps(posting.id, steps_data)
            print(f"✅ 전형 단계 {len(steps)}개 추가")
            
            # 6. 검색 기능 테스트
            print("🔍 검색 기능 테스트...")
            companies = repo.companies.search_companies(name_query="테스트")
            print(f"✅ 기업 검색 결과: {len(companies)}개")
            
            postings, count = repo.job_postings.search_job_postings(title_query="테스트")
            print(f"✅ 채용공고 검색 결과: {len(postings)}개 (총 {count}개)")
            
            print("\n🎉 모든 리포지토리 작업 테스트 성공!")
            return True
            
    except Exception as e:
        print(f"❌ 리포지토리 작업 테스트 실패: {e}")
        return False


def test_sample_data_loading():
    """샘플 데이터 로드 테스트"""
    print("\n" + "=" * 50)
    print("📊 샘플 데이터 로드 테스트")
    print("=" * 50)
    
    try:
        OpenAPIDataLoader.load_sample_data()
        print("✅ 샘플 데이터 로드 성공")
        
        # 로드된 데이터 확인
        with db_session_scope() as session:
            repo = DataRepositoryManager(session)
            
            companies = repo.companies.search_companies(limit=10)
            postings, count = repo.job_postings.search_job_postings(limit=10)
            
            print(f"📈 데이터 현황:")
            print(f"   - 기업: {len(companies)}개")
            print(f"   - 채용공고: {count}개")
            
        return True
    except Exception as e:
        print(f"❌ 샘플 데이터 로드 실패: {e}")
        return False


def test_data_retrieval():
    """데이터 조회 테스트"""
    print("\n" + "=" * 50)
    print("📖 데이터 조회 테스트")
    print("=" * 50)
    
    try:
        with db_session_scope() as session:
            repo = DataRepositoryManager(session)
            
            # 기업 상세 조회
            company = repo.companies.get_by_emp_co_no('E000023944')
            if company:
                print(f"✅ 기업 조회: {company.company_name}")
                print(f"   - 복리후생: {len(company.welfare_items)}개")
                print(f"   - 연혁: {len(company.history_items)}개")
                print(f"   - 인재상: {len(company.talent_criteria)}개")
            
            # 채용공고 상세 조회  
            posting = repo.job_postings.get_by_emp_seq_no('999999')
            if posting:
                print(f"✅ 채용공고 조회: {posting.title}")
                print(f"   - 전형단계: {len(posting.selection_steps)}개")
                print(f"   - 모집부문: {len(posting.recruitment_positions)}개")
            
        return True
    except Exception as e:
        print(f"❌ 데이터 조회 테스트 실패: {e}")
        return False


def full_database_test():
    """전체 데이터베이스 테스트 실행"""
    print("🚀 데이터베이스 전체 테스트 시작")
    print("=" * 50)
    
    test_results = []
    
    # 1. 연결 테스트
    test_results.append(("연결 테스트", test_database_connection()))
    
    # 2. 테이블 생성 테스트
    if test_results[-1][1]:  # 이전 테스트가 성공한 경우만
        test_results.append(("테이블 생성 테스트", test_table_creation()))
    
    # 3. 리포지토리 작업 테스트
    if test_results[-1][1]:
        test_results.append(("리포지토리 작업 테스트", test_repository_operations()))
    
    # 4. 샘플 데이터 로드 테스트
    if test_results[-1][1]:
        test_results.append(("샘플 데이터 로드 테스트", test_sample_data_loading()))
    
    # 5. 데이터 조회 테스트
    if test_results[-1][1]:
        test_results.append(("데이터 조회 테스트", test_data_retrieval()))
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    
    success_count = 0
    for test_name, result in test_results:
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{test_name}: {status}")
        if result:
            success_count += 1
    
    print(f"\n총 {len(test_results)}개 테스트 중 {success_count}개 성공")
    
    if success_count == len(test_results):
        print("🎉 모든 테스트가 성공했습니다!")
        return True
    else:
        print("⚠️  일부 테스트가 실패했습니다.")
        return False


if __name__ == "__main__":
    # 환경변수 로드를 위해 .env 파일 확인
    env_file = project_root / ".env"
    if not env_file.exists():
        print("⚠️  .env 파일이 없습니다. environment-template.txt를 참고해서 .env 파일을 생성하세요.")
        print("🐳 Docker Compose를 사용하는 경우 환경변수가 자동 설정됩니다.")
    
    # 전체 테스트 실행
    success = full_database_test()
    sys.exit(0 if success else 1)
