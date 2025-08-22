"""
데이터 액세스 리포지토리
기업 정보, 채용공고 데이터의 저장, 조회, 검색 기능
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, date
from sqlalchemy import and_, or_, text, func, desc
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from .models import (
    Company, CompanyWelfare, CompanyHistory, CompanyTalentCriteria,
    JobPosting, JobPostingStep, JobPostingPosition, JobPostingSelfIntro,
    JobCategory, JobPostingTemplate, FeedbackSession
)
from ..exceptions import DatabaseError
from ..utils.logging import get_logger

logger = get_logger(__name__)


class BaseRepository(ABC):
    """기본 리포지토리 추상 클래스"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def _handle_database_error(self, operation: str, error: Exception) -> None:
        """데이터베이스 오류 처리"""
        logger.error(f"{operation} 실패: {error}")
        self.session.rollback()
        raise DatabaseError(f"{operation} 실패: {str(error)}")


class CompanyRepository(BaseRepository):
    """기업 정보 리포지토리"""
    
    def create_company(self, company_data: Dict[str, Any]) -> Company:
        """기업 정보 생성"""
        try:
            company = Company(**company_data)
            self.session.add(company)
            self.session.flush()  # ID 할당을 위해
            logger.info(f"기업 생성: {company.emp_co_no}")
            return company
        except SQLAlchemyError as e:
            self._handle_database_error("기업 생성", e)
    
    def get_by_emp_co_no(self, emp_co_no: str) -> Optional[Company]:
        """채용기업번호로 기업 조회"""
        try:
            return self.session.query(Company).filter(
                Company.emp_co_no == emp_co_no
            ).options(
                joinedload(Company.welfare_items),
                joinedload(Company.history_items),
                joinedload(Company.talent_criteria)
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"기업 조회 실패: {e}")
            return None
    
    def get_by_id(self, company_id: int) -> Optional[Company]:
        """ID로 기업 조회"""
        try:
            return self.session.query(Company).filter(
                Company.id == company_id
            ).options(
                joinedload(Company.welfare_items),
                joinedload(Company.history_items),
                joinedload(Company.talent_criteria)
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"기업 조회 실패: {e}")
            return None
    
    def search_companies(
        self, 
        name_query: Optional[str] = None,
        business_number: Optional[str] = None,
        classification: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Company]:
        """기업 검색"""
        try:
            query = self.session.query(Company)
            
            if name_query:
                query = query.filter(
                    Company.company_name.ilike(f"%{name_query}%")
                )
            
            if business_number:
                query = query.filter(
                    Company.business_number == business_number
                )
            
            if classification:
                query = query.filter(
                    Company.company_classification == classification
                )
            
            return query.order_by(Company.company_name).limit(limit).offset(offset).all()
        
        except SQLAlchemyError as e:
            logger.error(f"기업 검색 실패: {e}")
            return []
    
    def add_welfare_items(self, company_id: int, welfare_items: List[Dict[str, str]]) -> List[CompanyWelfare]:
        """복리후생 정보 추가"""
        try:
            welfare_objects = []
            for item in welfare_items:
                welfare = CompanyWelfare(
                    company_id=company_id,
                    category_name=item.get('cdKorNm'),
                    welfare_content=item.get('welfareCont')
                )
                welfare_objects.append(welfare)
                self.session.add(welfare)
            
            self.session.flush()
            return welfare_objects
        except SQLAlchemyError as e:
            self._handle_database_error("복리후생 정보 추가", e)
    
    def add_history_items(self, company_id: int, history_items: List[Dict[str, str]]) -> List[CompanyHistory]:
        """연혁 정보 추가"""
        try:
            history_objects = []
            for item in history_items:
                history = CompanyHistory(
                    company_id=company_id,
                    history_year=item.get('histYr'),
                    history_month=item.get('histMm'),
                    history_content=item.get('histCont')
                )
                history_objects.append(history)
                self.session.add(history)
            
            self.session.flush()
            return history_objects
        except SQLAlchemyError as e:
            self._handle_database_error("연혁 정보 추가", e)
    
    def update_company(self, company_id: int, update_data: Dict[str, Any]) -> Optional[Company]:
        """기업 정보 업데이트"""
        try:
            company = self.session.query(Company).filter(Company.id == company_id).first()
            if not company:
                return None
            
            for key, value in update_data.items():
                if hasattr(company, key):
                    setattr(company, key, value)
            
            company.updated_at = datetime.now(timezone.utc)
            self.session.flush()
            return company
        except SQLAlchemyError as e:
            self._handle_database_error("기업 정보 업데이트", e)


class JobCategoryRepository(BaseRepository):
    """직종 분류 리포지토리"""
    
    def create_or_get_category(self, jobs_code: str, jobs_name: str) -> JobCategory:
        """직종 분류 생성 또는 조회"""
        try:
            category = self.session.query(JobCategory).filter(
                JobCategory.jobs_code == jobs_code
            ).first()
            
            if not category:
                category = JobCategory(jobs_code=jobs_code, jobs_name=jobs_name)
                self.session.add(category)
                self.session.flush()
            
            return category
        except SQLAlchemyError as e:
            self._handle_database_error("직종 분류 생성/조회", e)


class JobPostingRepository(BaseRepository):
    """채용공고 리포지토리"""
    
    def create_job_posting(self, posting_data: Dict[str, Any]) -> JobPosting:
        """채용공고 생성"""
        try:
            job_posting = JobPosting(**posting_data)
            self.session.add(job_posting)
            self.session.flush()
            logger.info(f"채용공고 생성: {job_posting.emp_seq_no}")
            return job_posting
        except SQLAlchemyError as e:
            self._handle_database_error("채용공고 생성", e)
    
    def get_by_emp_seq_no(self, emp_seq_no: str) -> Optional[JobPosting]:
        """채용공고순번으로 조회"""
        try:
            return self.session.query(JobPosting).filter(
                JobPosting.emp_seq_no == emp_seq_no
            ).options(
                joinedload(JobPosting.company),
                joinedload(JobPosting.job_category),
                joinedload(JobPosting.selection_steps),
                joinedload(JobPosting.recruitment_positions),
                joinedload(JobPosting.self_intro_questions)
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"채용공고 조회 실패: {e}")
            return None
    
    def get_by_id(self, posting_id: int) -> Optional[JobPosting]:
        """ID로 채용공고 조회"""
        try:
            return self.session.query(JobPosting).filter(
                JobPosting.id == posting_id
            ).options(
                joinedload(JobPosting.company),
                joinedload(JobPosting.job_category),
                joinedload(JobPosting.selection_steps),
                joinedload(JobPosting.recruitment_positions)
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"채용공고 조회 실패: {e}")
            return None
    
    def search_job_postings(
        self,
        title_query: Optional[str] = None,
        company_name: Optional[str] = None,
        employment_type: Optional[str] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None,
        end_date_from: Optional[date] = None,
        end_date_to: Optional[date] = None,
        job_category_code: Optional[str] = None,
        active_only: bool = True,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[JobPosting], int]:
        """채용공고 검색 (결과와 총 개수 반환)"""
        try:
            base_query = self.session.query(JobPosting).join(Company)
            
            # 검색 필터 적용
            filters = []
            
            if title_query:
                filters.append(JobPosting.title.ilike(f"%{title_query}%"))
            
            if company_name:
                filters.append(Company.company_name.ilike(f"%{company_name}%"))
            
            if employment_type:
                filters.append(JobPosting.employment_type.ilike(f"%{employment_type}%"))
            
            if start_date_from:
                filters.append(JobPosting.start_date >= start_date_from)
            
            if start_date_to:
                filters.append(JobPosting.start_date <= start_date_to)
            
            if end_date_from:
                filters.append(JobPosting.end_date >= end_date_from)
            
            if end_date_to:
                filters.append(JobPosting.end_date <= end_date_to)
            
            if job_category_code:
                base_query = base_query.join(JobCategory)
                filters.append(JobCategory.jobs_code == job_category_code)
            
            if active_only:
                today = date.today()
                filters.append(
                    or_(
                        JobPosting.end_date.is_(None),
                        JobPosting.end_date >= today
                    )
                )
            
            if filters:
                base_query = base_query.filter(and_(*filters))
            
            # 총 개수 조회
            total_count = base_query.count()
            
            # 결과 조회
            results = base_query.options(
                joinedload(JobPosting.company),
                joinedload(JobPosting.job_category)
            ).order_by(
                desc(JobPosting.created_at)
            ).limit(limit).offset(offset).all()
            
            return results, total_count
        
        except SQLAlchemyError as e:
            logger.error(f"채용공고 검색 실패: {e}")
            return [], 0
    
    def add_selection_steps(self, posting_id: int, steps: List[Dict[str, Any]]) -> List[JobPostingStep]:
        """전형 단계 추가"""
        try:
            step_objects = []
            for idx, step in enumerate(steps):
                step_obj = JobPostingStep(
                    job_posting_id=posting_id,
                    step_name=step.get('selsNm'),
                    step_order=idx + 1,
                    schedule_content=step.get('selsSchdCont'),
                    step_content=step.get('selsCont'),
                    memo_content=step.get('selsMemoCont')
                )
                step_objects.append(step_obj)
                self.session.add(step_obj)
            
            self.session.flush()
            return step_objects
        except SQLAlchemyError as e:
            self._handle_database_error("전형 단계 추가", e)
    
    def add_recruitment_positions(self, posting_id: int, positions: List[Dict[str, Any]]) -> List[JobPostingPosition]:
        """모집 부문 추가"""
        try:
            position_objects = []
            for position in positions:
                pos_obj = JobPostingPosition(
                    job_posting_id=posting_id,
                    position_name=position.get('empRecrNm'),
                    job_description=position.get('jobCont'),
                    work_region=position.get('workRegionNm'),
                    career_requirement=position.get('empWantedCareerNm'),
                    education_requirement=position.get('empWantedEduNm'),
                    other_requirements=position.get('sptCertEtc'),
                    recruitment_count=position.get('recrPsncnt'),
                    memo_content=position.get('empRecrMemoCont')
                )
                position_objects.append(pos_obj)
                self.session.add(pos_obj)
            
            self.session.flush()
            return position_objects
        except SQLAlchemyError as e:
            self._handle_database_error("모집 부문 추가", e)


class TemplateRepository(BaseRepository):
    """템플릿 리포지토리"""
    
    def create_template(self, template_data: Dict[str, Any]) -> JobPostingTemplate:
        """템플릿 생성"""
        try:
            template = JobPostingTemplate(**template_data)
            self.session.add(template)
            self.session.flush()
            logger.info(f"템플릿 생성: {template.template_id}")
            return template
        except SQLAlchemyError as e:
            self._handle_database_error("템플릿 생성", e)
    
    def get_by_template_id(self, template_id: str) -> Optional[JobPostingTemplate]:
        """템플릿 ID로 조회"""
        try:
            return self.session.query(JobPostingTemplate).filter(
                JobPostingTemplate.template_id == template_id
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"템플릿 조회 실패: {e}")
            return None
    
    def update_template_status(
        self, 
        template_id: str, 
        status: str, 
        validation_results: Optional[Dict] = None
    ) -> Optional[JobPostingTemplate]:
        """템플릿 상태 업데이트"""
        try:
            template = self.get_by_template_id(template_id)
            if not template:
                return None
            
            template.generation_status = status
            template.updated_at = datetime.now(timezone.utc)
            
            if validation_results:
                template.validation_results = validation_results
            
            self.session.flush()
            return template
        except SQLAlchemyError as e:
            self._handle_database_error("템플릿 상태 업데이트", e)


class FeedbackSessionRepository(BaseRepository):
    """피드백 세션 리포지토리"""
    
    def create_feedback_session(self, session_data: Dict[str, Any]) -> FeedbackSession:
        """피드백 세션 생성"""
        try:
            session_obj = FeedbackSession(**session_data)
            self.session.add(session_obj)
            self.session.flush()
            return session_obj
        except SQLAlchemyError as e:
            self._handle_database_error("피드백 세션 생성", e)
    
    def get_by_session_id(self, session_id: str) -> Optional[FeedbackSession]:
        """세션 ID로 조회"""
        try:
            return self.session.query(FeedbackSession).filter(
                FeedbackSession.session_id == session_id
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"피드백 세션 조회 실패: {e}")
            return None
    
    def complete_feedback_session(
        self, 
        session_id: str, 
        user_feedback: Dict[str, Any]
    ) -> Optional[FeedbackSession]:
        """피드백 세션 완료"""
        try:
            session_obj = self.get_by_session_id(session_id)
            if not session_obj:
                return None
            
            session_obj.status = "completed"
            session_obj.user_feedback = user_feedback
            session_obj.completed_at = datetime.now(timezone.utc)
            
            self.session.flush()
            return session_obj
        except SQLAlchemyError as e:
            self._handle_database_error("피드백 세션 완료", e)


class DataRepositoryManager:
    """리포지토리 통합 관리 클래스"""
    
    def __init__(self, session: Session):
        self.session = session
        self.companies = CompanyRepository(session)
        self.job_categories = JobCategoryRepository(session)
        self.job_postings = JobPostingRepository(session)
        self.templates = TemplateRepository(session)
        self.feedback_sessions = FeedbackSessionRepository(session)
    
    def commit(self) -> None:
        """트랜잭션 커밋"""
        try:
            self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            raise DatabaseError(f"트랜잭션 커밋 실패: {e}")
    
    def rollback(self) -> None:
        """트랜잭션 롤백"""
        self.session.rollback()
    
    def close(self) -> None:
        """세션 종료"""
        self.session.close()
