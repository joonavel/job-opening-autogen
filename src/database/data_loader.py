"""
데이터베이스 초기 데이터 로더
Open API 데이터 구조를 파싱하여 데이터베이스에 저장
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date
from ..utils.logging import get_logger
from .connection import db_session_scope
from .repositories import DataRepositoryManager

logger = get_logger(__name__)


class OpenAPIDataLoader:
    """Open API 데이터를 데이터베이스에 로드하는 클래스"""
    
    @staticmethod
    def parse_date(date_str: Optional[str]) -> Optional[date]:
        """날짜 문자열을 date 객체로 변환 (YYYYMMDD 형식)"""
        if not date_str or len(date_str) != 8:
            return None
        try:
            return datetime.strptime(date_str, '%Y%m%d').date()
        except ValueError:
            logger.warning(f"잘못된 날짜 형식: {date_str}")
            return None
    
    @staticmethod
    def load_company_data(company_detail_data: Dict[str, Any]) -> Optional[str]:
        """기업 상세 데이터를 데이터베이스에 로드"""
        try:
            root_data = company_detail_data.get('dhsOpenEmpHireInfoDetailRoot', {})
            
            company_data = {
                'emp_co_no': root_data.get('empCoNo'),
                'company_name': root_data.get('coNm'),
                'business_number': root_data.get('busino'),
                'company_classification': root_data.get('coClcdNm'),
                'map_coord_x': float(root_data['mapCoorX']) if root_data.get('mapCoorX') else None,
                'map_coord_y': float(root_data['mapCoorY']) if root_data.get('mapCoorY') else None,
                'logo_url': root_data.get('regLogImgNm'),
                'homepage': root_data.get('homepg'),
                'intro_summary': root_data.get('coIntroSummaryCont'),
                'intro_detail': root_data.get('coIntroCont'),
                'main_business': root_data.get('mainBusiCont')
            }
            
            with db_session_scope() as session:
                repo_manager = DataRepositoryManager(session)
                
                # 기업 생성 또는 조회
                existing_company = repo_manager.companies.get_by_emp_co_no(company_data['emp_co_no'])
                if existing_company:
                    logger.info(f"기업이 이미 존재합니다: {company_data['emp_co_no']}")
                    return existing_company.emp_co_no
                
                company = repo_manager.companies.create_company(company_data)
                
                # 복리후생 정보 추가
                welfare_data = root_data.get('welfareList', {}).get('welfareListInfo', [])
                if welfare_data:
                    if not isinstance(welfare_data, list):
                        welfare_data = [welfare_data]
                    repo_manager.companies.add_welfare_items(company.id, welfare_data)
                
                # 연혁 정보 추가
                history_data = root_data.get('historyList', {}).get('historyListInfo', [])
                if history_data:
                    if not isinstance(history_data, list):
                        history_data = [history_data]
                    repo_manager.companies.add_history_items(company.id, history_data)
                
                # 인재상 정보 추가
                talent_data = root_data.get('rightPeopleList', {}).get('rightPeopleListInfo', {})
                if talent_data:
                    if not isinstance(talent_data, list):
                        talent_data = [talent_data]
                    repo_manager.companies.add_talent_criteria(company.id, talent_data)
                
                repo_manager.commit()
                logger.info(f"기업 데이터 로드 완료: {company_data['emp_co_no']}")
                return company.emp_co_no
                
        except Exception as e:
            logger.error(f"기업 데이터 로드 실패: {e}")
            return None
    
    @staticmethod
    def load_job_posting_data(job_posting_detail_data: Dict[str, Any], emp_co_no: Optional[str] = None) -> Optional[int]:
        """채용공고 상세 데이터를 데이터베이스에 로드"""
        try:
            root_data = job_posting_detail_data.get('dhsOpenEmpInfoDetailRoot', {})
            
            # 채용공고 데이터 구성
            posting_data = {
                'emp_seq_no': root_data.get('empSeqno'),
                'title': root_data.get('empWantedTitle'),
                'emp_co_no': emp_co_no,
                'start_date': OpenAPIDataLoader.parse_date(root_data.get('empWantedStdt')),
                'end_date': OpenAPIDataLoader.parse_date(root_data.get('empWantedEndt')),
                'employment_type': root_data.get('empWantedTypeNm'),
                'company_homepage': root_data.get('empWantedHomepg'),
                'detail_url': root_data.get('empWantedHomepgDetail'),
                'mobile_url': root_data.get('empWantedMobileUrl'),
                'summary_content': root_data.get('empnRecrSummaryCont'),
                'common_content': root_data.get('recrCommCont'),
                'submit_documents': root_data.get('empSubmitDocCont'),
                'application_method': root_data.get('empRcptMthdCont'),
                'announcement_date': root_data.get('empAcptPsnAnncCont'),
                'inquiry_content': root_data.get('inqryCont'),
                'other_content': root_data.get('empnEtcCont')
            }
            
            with db_session_scope() as session:
                repo_manager = DataRepositoryManager(session)
                
                # 채용공고 생성 또는 조회
                existing_posting = repo_manager.job_postings.get_by_emp_seq_no(posting_data['emp_seq_no'])
                if existing_posting:
                    logger.info(f"채용공고가 이미 존재합니다: {posting_data['emp_seq_no']}")
                    return existing_posting.id
                
                job_posting = repo_manager.job_postings.create_job_posting(posting_data)
                
                # 직종 정보 추가
                jobs_data = root_data.get('empJobsList', {}).get('empJobsListInfo', [])
                if jobs_data:
                    if not isinstance(jobs_data, list):
                        jobs_data = [jobs_data]
                    repo_manager.job_postings.add_job_category(job_posting.id, jobs_data)
                
                
                # 전형 단계 추가
                selection_steps = root_data.get('empSelsList', {}).get('empSelsListInfo', [])
                if selection_steps:
                    if not isinstance(selection_steps, list):
                        selection_steps = [selection_steps]
                    repo_manager.job_postings.add_selection_steps(job_posting.id, selection_steps)
                
                # 모집 부문 추가
                recruitment_positions = root_data.get('empRecrList', {}).get('empRecrListInfo', [])
                if recruitment_positions:
                    if not isinstance(recruitment_positions, list):
                        recruitment_positions = [recruitment_positions]
                    repo_manager.job_postings.add_recruitment_positions(job_posting.id, recruitment_positions)
                
                # 자기소개서 질문 추가
                self_intro_data = root_data.get('empSelfintroList', {}).get('empSelsListInfo', {})
                if self_intro_data:
                    if not isinstance(self_intro_data, list):
                        self_intro_data = [self_intro_data]
                    repo_manager.job_postings.add_self_intro_questions(job_posting.id, self_intro_data)
                
                repo_manager.commit()
                logger.info(f"채용공고 데이터 로드 완료: {posting_data['emp_seq_no']}")
                return job_posting.id
                
        except Exception as e:
            logger.error(f"채용공고 데이터 로드 실패: {e}")
            return None
    
    @staticmethod
    def load_sample_data():
        """샘플 데이터 로드"""
        logger.info("샘플 데이터 로드를 시작합니다...")
        
        # 샘플 기업 데이터
        sample_company = {
            'dhsOpenEmpHireInfoDetailRoot': {
                'empCoNo': 'E000023944',
                'coNm': '일일일퍼센트',
                'busino': '1368700241',
                'coClcdNm': None,
                'mapCoorX': '127.036508620542',
                'mapCoorY': '37.5000242405515',
                'regLogImgNm': 'http://example.com/logo.png',
                'homepg': 'https://111percent.net/',
                'coIntroSummaryCont': '게임개발 회사',
                'coIntroCont': '111퍼센트는 재미라는 본질에 집중하며, 게임이 아닌 장르를 만듭니다.',
                'mainBusiCont': '게임 개발 및 퍼블리싱',
                'welfareList': {
                    'welfareListInfo': [
                        {'cdKorNm': '휴무/휴가/행사', 'welfareCont': '전사 겨울 방학'},
                        {'cdKorNm': '보장/보상/지원', 'welfareCont': '경조사 지원/명절 선물/생일 선물/종합검진'},
                        {'cdKorNm': '생활편의/사내시설', 'welfareCont': '식대 지원/사내 카페/스낵바/안마의자'},
                        {'cdKorNm': '기타', 'welfareCont': '시차 출퇴근제/웰컴키트/최고급 장비 지원'}
                    ]
                },
                'historyList': {
                    'historyListInfo': [
                        {'histYr': '2024', 'histMm': '12', 'histCont': '[운빨존많겜] 구글 플레이 선정, 올해를 빛낸 캐주얼 게임 최우수상 수상'},
                        {'histYr': '2024', 'histMm': '09', 'histCont': '[운빨존많겜] Apple App Store 매출 1위'},
                        {'histYr': '2023', 'histMm': '12', 'histCont': '[랜덤다이스: GO] 구글플레이 선정 올해를 빛낸 인디 게임 우수상 수상'}
                    ]
                },
                'rightPeopleList': {
                    'rightPeopleListInfo': {
                        'psnrightKeywordNm': '창의성, 도전정신, 팀워크',
                        'psnrightDesc': '새로운 게임 장르를 만들어나가는 창의적인 인재를 찾습니다.'
                    }
                }
            }
        }
        
        # 기업 데이터 로드
        emp_co_no = OpenAPIDataLoader.load_company_data(sample_company)
        
        if emp_co_no:
            # 샘플 채용공고 데이터
            sample_job_posting = {
                'dhsOpenEmpInfoDetailRoot': {
                    'empSeqno': '999999',
                    'empWantedTitle': '게임 개발자 모집 (Unity/C#)',
                    'empWantedStdt': '20250820',
                    'empWantedEndt': '20250920',
                    'empWantedTypeNm': '정규직',
                    'empWantedHomepg': 'https://111percent.net/',
                    'empWantedHomepgDetail': 'https://111percent.net/careers',
                    'empJobsList': {
                        'empJobsListInfo': {
                            'jobsCd': '02A',
                            'jobsCdKorNm': '소프트웨어 개발'
                        }
                    },
                    'empSelsList': {
                        'empSelsListInfo': [
                            {'selsNm': '서류전형', 'selsCont': '포트폴리오 및 이력서 검토'},
                            {'selsNm': '1차면접', 'selsCont': '기술 면접'},
                            {'selsNm': '최종면접', 'selsCont': '임원 면접'},
                            {'selsNm': '합격자발표', 'selsCont': '개별 연락'}
                        ]
                    },
                    'empRecrList': {
                        'empRecrListInfo': {
                            'empRecrNm': 'Unity 게임 개발자',
                            'jobCont': '모바일 게임 개발 및 유지보수\n- Unity를 활용한 게임 클라이언트 개발\n- C# 기반 게임 로직 구현',
                            'workRegionNm': '서울',
                            'empWantedCareerNm': '신입/경력',
                            'empWantedEduNm': '학력무관',
                            'sptCertEtc': '- Unity 엔진 활용 경험\n- C# 프로그래밍 능력\n- 게임 개발에 대한 열정',
                            'recrPsncnt': '2',
                            'empRecrMemoCont': '포트폴리오 필수 제출'
                        }
                    },
                    'empSubmitDocCont': '이력서, 포트폴리오',
                    'empRcptMthdCont': '온라인 지원',
                    'inqryCont': 'hr@111percent.net',
                    'recrCommCont': '적극적이고 창의적인 개발자를 찾습니다.',
                    'empnEtcCont': '지원서류는 반환되지 않으며, 허위 기재시 불이익이 있을 수 있습니다.'
                }
            }
            
            # 채용공고 데이터 로드
            OpenAPIDataLoader.load_job_posting_data(sample_job_posting, emp_co_no)
        
        logger.info("샘플 데이터 로드가 완료되었습니다.")


def initialize_database_with_sample_data():
    """데이터베이스 초기화 및 샘플 데이터 로드"""
    from .connection import init_database, create_tables, test_db_connection, drop_tables
    
    try:
        # 데이터베이스 연결 초기화
        init_database()
        logger.info("데이터베이스 연결이 초기화되었습니다.")
        
        # 연결 테스트
        if not test_db_connection():
            raise Exception("데이터베이스 연결 테스트 실패")
        
        # 기존 테이블 삭제
        drop_tables()
        logger.info("데이터베이스 테이블이 삭제되었습니다.")
        
        # 테이블 생성
        create_tables()
        logger.info("데이터베이스 테이블이 생성되었습니다.")
        
        # 샘플 데이터 로드
        OpenAPIDataLoader.load_sample_data()
        
        logger.info("데이터베이스 초기화가 완료되었습니다.")
        
    except Exception as e:
        logger.error(f"데이터베이스 초기화 실패: {e}")
        raise


if __name__ == "__main__":
    initialize_database_with_sample_data()
