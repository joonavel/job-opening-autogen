"""
데이터베이스 모델 정의
Open API 데이터 구조를 기반으로 한 SQLAlchemy ORM 모델
"""

from datetime import datetime, timezone, date
from typing import List, Optional, Any
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date, Float, Boolean, 
    ForeignKey, JSON, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped, mapped_column
import uuid

Base = declarative_base()


class Company(Base):
    """기업 정보 테이블 - dhsOpenEmpHireInfoDetailRoot 기반"""
    __tablename__ = "companies"
    
    # 기본 식별자
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    emp_co_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True, comment="채용기업번호")
    
    # 기본 정보
    company_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True, comment="회사명")
    business_number: Mapped[str] = mapped_column(String(50), comment="사업자등록번호")
    company_classification: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="기업구분명")
    
    # 위치 정보
    map_coord_x: Mapped[float] = mapped_column(Float, comment="좌표:경도")
    map_coord_y: Mapped[float] = mapped_column(Float, comment="좌표:위도")
    
    # 웹 정보
    logo_url: Mapped[str] = mapped_column(Text, comment="로고 URL")
    homepage: Mapped[str] = mapped_column(String(500), comment="홈페이지")
    
    # 기업 소개
    intro_summary: Mapped[str] = mapped_column(Text, comment="기업소개 요약")
    intro_detail: Mapped[str] = mapped_column(Text, comment="기업소개 상세")
    main_business: Mapped[str] = mapped_column(Text, nullable=True, comment="주요사업")
    
    # 메타데이터
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # 관계
    welfare_items: Mapped[List["CompanyWelfare"]] = relationship("CompanyWelfare", back_populates="company", cascade="all, delete-orphan")
    history_items: Mapped[List["CompanyHistory"]] = relationship("CompanyHistory", back_populates="company", cascade="all, delete-orphan")
    talent_criteria: Mapped[List["CompanyTalentCriteria"]] = relationship("CompanyTalentCriteria", back_populates="company", cascade="all, delete-orphan")
    job_postings: Mapped[List["JobPosting"]] = relationship("JobPosting", back_populates="company")
    
    def __repr__(self):
        return f"<Company(emp_co_no='{self.emp_co_no}', name='{self.company_name}')>"


class CompanyWelfare(Base):
    """기업 복리후생 정보 - welfareList.welfareListInfo 기반"""
    __tablename__ = "company_welfare"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    
    category_name: Mapped[str] = mapped_column(String(100), comment="복리후생 카테고리")
    welfare_content: Mapped[str] = mapped_column(Text, comment="복리후생 내용")
    
    # 관계
    company: Mapped["Company"] = relationship("Company", back_populates="welfare_items")


class CompanyHistory(Base):
    """기업 연혁 정보 - historyList.historyListInfo 기반"""
    __tablename__ = "company_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey(column="companies.id", ondelete="CASCADE"), nullable=False)
    
    history_year: Mapped[str] = mapped_column(String(length=4), comment="연혁 년도")
    history_month: Mapped[str] = mapped_column(String(length=2), comment="연혁 월")
    history_content: Mapped[str] = mapped_column(Text, comment="연혁 내용")
    
    # 관계
    company: Mapped["Company"] = relationship(argument="Company", back_populates="history_items")
    
    # 인덱스
    __table_args__ = (
        Index('ix_company_history_date', 'company_id', 'history_year', 'history_month'),
    )


class CompanyTalentCriteria(Base):
    """기업 인재상 정보 - rightPeopleList.rightPeopleListInfo 기반"""
    __tablename__ = "company_talent_criteria"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey(column="companies.id", ondelete="CASCADE"), nullable=False)
    
    keyword: Mapped[str] = mapped_column(String(length=200), nullable=True, comment="인재상 키워드")
    description: Mapped[str] = mapped_column(Text, nullable=True, comment="인재상 설명")
    
    # 관계
    company: Mapped["Company"] = relationship(argument="Company", back_populates="talent_criteria")


class JobPosting(Base):
    """채용공고 정보 - dhsOpenEmpInfoDetailRoot 기반"""
    __tablename__ = "job_postings"
    
    # 기본 식별자
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    emp_seq_no: Mapped[str] = mapped_column(String(length=50), unique=True, nullable=False, index=True, comment="공개채용공고순번")
    
    # 기본 정보
    title: Mapped[str] = mapped_column(Text, nullable=False, comment="채용제목")
    emp_co_no: Mapped[str] = mapped_column(String(length=50), ForeignKey(column="companies.emp_co_no"), nullable=False)
    job_category_id: Mapped[int] = mapped_column(Integer, ForeignKey(column="job_categories.id"))
    
    # 채용 일정
    start_date: Mapped[date] = mapped_column(Date, comment="채용시작일자")
    end_date: Mapped[date] = mapped_column(Date, comment="채용종료일자")
    employment_type: Mapped[str] = mapped_column(String(length=100), comment="고용형태")
    
    # 웹 정보
    company_homepage: Mapped[str] = mapped_column(String(length=500), comment="채용기업 홈페이지")
    detail_url: Mapped[str] = mapped_column(String(length=500), comment="채용사이트 URL")
    mobile_url: Mapped[str] = mapped_column(String(length=500), nullable=True, comment="모바일채용사이트 URL")
    
    # 채용 상세 정보
    summary_content: Mapped[str] = mapped_column(Text, nullable=True, comment="모집부문 전체요약")
    common_content: Mapped[str] = mapped_column(Text, comment="공통사항")
    submit_documents: Mapped[str] = mapped_column(Text, comment="제출서류")
    application_method: Mapped[str] = mapped_column(Text, comment="접수방법")
    announcement_date: Mapped[str] = mapped_column(Text, nullable=True, comment="합격자발표일")
    inquiry_content: Mapped[str] = mapped_column(Text, comment="문의사항")
    other_content: Mapped[str] = mapped_column(Text, comment="기타사항")
    
    # 메타데이터
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # 관계
    company: Mapped["Company"] = relationship("Company", back_populates="job_postings")
    job_category: Mapped[Optional["JobCategory"]] = relationship("JobCategory", back_populates="job_postings")
    selection_steps: Mapped[List["JobPostingStep"]] = relationship("JobPostingStep", back_populates="job_posting", cascade="all, delete-orphan")
    recruitment_positions: Mapped[List["JobPostingPosition"]] = relationship("JobPostingPosition", back_populates="job_posting", cascade="all, delete-orphan")
    self_intro_questions: Mapped[List["JobPostingSelfIntro"]] = relationship("JobPostingSelfIntro", back_populates="job_posting", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<JobPosting(emp_seq_no='{self.emp_seq_no}', title='{self.title[:50]}...')>"


class JobCategory(Base):
    """직종 분류 - empJobsList.empJobsListInfo 기반"""
    __tablename__ = "job_categories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jobs_code: Mapped[str] = mapped_column(String(length=10), unique=True, nullable=False, comment="직종 코드")
    jobs_name: Mapped[str] = mapped_column(String(length=200), nullable=False, comment="직종명")
    
    # 관계
    job_postings: Mapped[List["JobPosting"]] = relationship("JobPosting", back_populates="job_category")


class JobPostingStep(Base):
    """채용 전형 단계 - empSelsList.empSelsListInfo 기반"""
    __tablename__ = "job_posting_steps"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_posting_id: Mapped[int] = mapped_column(Integer, ForeignKey(column="job_postings.id", ondelete="CASCADE"), nullable=False)
    
    step_name: Mapped[str] = mapped_column(String(length=200), comment="전형단계명")
    step_order: Mapped[int] = mapped_column(Integer, comment="전형단계 순서")
    schedule_content: Mapped[str] = mapped_column(Text, nullable=True, comment="전형단계일정내용")
    step_content: Mapped[str] = mapped_column(Text, nullable=True, comment="전형단계내용")
    memo_content: Mapped[str] = mapped_column(Text, nullable=True, comment="전형단계비고")
    
    # 관계
    job_posting: Mapped["JobPosting"] = relationship("JobPosting", back_populates="selection_steps")
    
    # 인덱스
    __table_args__ = (
        Index('ix_job_posting_steps_order', 'job_posting_id', 'step_order'),
    )


class JobPostingPosition(Base):
    """채용 모집 부문 - empRecrList.empRecrListInfo 기반"""
    __tablename__ = "job_posting_positions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_posting_id: Mapped[int] = mapped_column(Integer, ForeignKey(column="job_postings.id", ondelete="CASCADE"), nullable=False)
    
    position_name: Mapped[str] = mapped_column(String(length=200), comment="채용모집명")
    job_description: Mapped[str] = mapped_column(Text, comment="직무설명")
    work_region: Mapped[str] = mapped_column(String(length=200), comment="근무지")
    career_requirement: Mapped[str] = mapped_column(String(length=100), comment="지원자격(경력)")
    education_requirement: Mapped[str] = mapped_column(String(length=100), comment="지원자격(학력)")
    other_requirements: Mapped[str] = mapped_column(Text, comment="지원자격(기타)")
    recruitment_count: Mapped[str] = mapped_column(String(length=20), comment="모집인원수")
    memo_content: Mapped[str] = mapped_column(Text, comment="비고")
    
    # 관계
    job_posting: Mapped["JobPosting"] = relationship("JobPosting", back_populates="recruitment_positions")


class JobPostingSelfIntro(Base):
    """자기소개서 질문 - empSelfintroList.empSelsListInfo 기반"""
    __tablename__ = "job_posting_self_intro"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_posting_id: Mapped[int] = mapped_column(Integer, ForeignKey(column="job_postings.id", ondelete="CASCADE"), nullable=False)
    
    question_content: Mapped[str] = mapped_column(Text, nullable=True, comment="자기소개서 질문내용")
    question_order: Mapped[int] = mapped_column(Integer, comment="질문 순서")
    
    # 관계
    job_posting: Mapped["JobPosting"] = relationship("JobPosting", back_populates="self_intro_questions")


class JobPostingTemplate(Base):
    """생성된 채용공고 템플릿 저장"""
    __tablename__ = "job_posting_templates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[str] = mapped_column(String(50), default=lambda: str(uuid.uuid4()), unique=True, index=True, comment="템플릿 고유 ID")
    
    # 연관 정보
    source_emp_seq_no: Mapped[str] = mapped_column(String(50), ForeignKey("job_postings.emp_seq_no"), nullable=True, comment="참조 채용공고 ID")
    source_emp_co_no: Mapped[str] = mapped_column(String(50), ForeignKey("companies.emp_co_no"), nullable=True, comment="대상 기업 ID")
    
    # 템플릿 내용
    title: Mapped[str] = mapped_column(Text, comment="생성된 채용공고 제목")
    content: Mapped[str] = mapped_column(Text, comment="생성된 채용공고 내용")
    template_data: Mapped[dict] = mapped_column(JSON, comment="구조화된 템플릿 데이터")
    
    # 생성 정보
    generation_status: Mapped[str] = mapped_column(String(50), default="draft", comment="생성 상태 (draft, validated, finalized)")
    generation_metadata: Mapped[dict] = mapped_column(JSON, comment="생성 메타데이터 (사용된 프롬프트, 모델 등)")
    
    # 검증 정보
    validation_metadata: Mapped[dict] = mapped_column(JSON, comment="검증 메타데이터")
    
    # 메타데이터
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # 관계
    # feedback_sessions: Mapped[List["FeedbackSession"]] = relationship("FeedbackSession", cascade="all, delete-orphan", back_populates="template")


class FeedbackSession(Base):
    """Human-in-the-Loop 피드백 세션"""
    __tablename__ = "feedback_sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(50), default=str(uuid.uuid4()), unique=True, index=True, comment="세션 고유 ID")
    
    # 연관 템플릿
    template_id: Mapped[str] = mapped_column(String(50), nullable=False, comment="관련 템플릿 ID")
    
    # 세션 정보
    session_type: Mapped[str] = mapped_column(String(50), comment="피드백 유형 (missing_fields, sensitivity_detected, quality_review)")
    status: Mapped[str] = mapped_column(String(50), default="pending", comment="세션 상태 (pending, completed, cancelled)")
    
    # 피드백 데이터
    feedback_request: Mapped[List[str]] = mapped_column(JSON, comment="피드백 요청 데이터")
    user_feedback: Mapped[List[str]] = mapped_column(JSON, comment="사용자 피드백")
    
    # 메타데이터
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # 관계
    # template: Mapped["JobPostingTemplate"] = relationship("JobPostingTemplate", cascade="all, delete-orphan", back_populates="feedback_sessions")


# 검색 및 추적을 위한 인덱스 생성
Index('ix_companies_name_search', Company.company_name)
Index('ix_job_postings_title_search', JobPosting.title)
Index('ix_job_postings_dates', JobPosting.start_date, JobPosting.end_date)
Index('ix_templates_status_created', JobPostingTemplate.generation_status, JobPostingTemplate.created_at)


def convert_orm_to_dict(orm_obj):
    """SQLAlchemy ORM 객체를 딕셔너리로 변환"""
    if orm_obj is None:
        return None
    
    # 기본 컬럼들을 딕셔너리로 변환
    result = {}
    for column in orm_obj.__table__.columns:
        if column.name == "id" or column.name == "company_id":
            continue
        value = getattr(orm_obj, column.name)
        # datetime 객체는 ISO 문자열로 변환
        if isinstance(value, datetime):
            result[column.name] = value.isoformat()
        else:
            result[column.name] = value
    
    return result

def convert_orm_list_to_dict_list(orm_list) -> list[dict[str, Any] | None]:
    """SQLAlchemy ORM 리스트를 딕셔너리 리스트로 변환"""
    if not orm_list:
        return []
    
    return [convert_orm_to_dict(item) for item in orm_list]