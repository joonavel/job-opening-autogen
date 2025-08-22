"""
데이터베이스 패키지 초기화
"""

from .connection import (
    init_database,
    create_tables,
    get_db_session,
    db_session_scope,
    test_db_connection,
    close_db_connection,
    db_manager
)

from .models import (
    Base,
    Company,
    CompanyWelfare,
    CompanyHistory,
    CompanyTalentCriteria,
    JobCategory,
    JobPosting,
    JobPostingStep,
    JobPostingPosition,
    JobPostingSelfIntro,
    JobPostingTemplate,
    FeedbackSession
)

from .repositories import (
    CompanyRepository,
    JobCategoryRepository,
    JobPostingRepository,
    TemplateRepository,
    FeedbackSessionRepository,
    DataRepositoryManager
)

__all__ = [
    # Connection
    'init_database',
    'create_tables',
    'get_db_session',
    'db_session_scope',
    'test_db_connection',
    'close_db_connection',
    'db_manager',
    
    # Models
    'Base',
    'Company',
    'CompanyWelfare',
    'CompanyHistory',
    'CompanyTalentCriteria',
    'JobCategory',
    'JobPosting',
    'JobPostingStep',
    'JobPostingPosition',
    'JobPostingSelfIntro',
    'JobPostingTemplate',
    'FeedbackSession',
    
    # Repositories
    'CompanyRepository',
    'JobCategoryRepository',
    'JobPostingRepository',
    'TemplateRepository',
    'FeedbackSessionRepository',
    'DataRepositoryManager',
]
