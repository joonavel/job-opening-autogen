"""
데이터베이스 패키지 초기화
"""

from .connection import (
    init_database,
    create_tables,
    drop_tables,
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
    FeedbackSession,
    convert_orm_list_to_dict_list,
)

from .repositories import (
    CompanyRepository,
    JobCategoryRepository,
    JobPostingRepository,
    TemplateRepository,
    FeedbackSessionRepository,
    DataRepositoryManager
)

from .fastapi_db import (
    get_db,
)

__all__ = [
    # Connection
    'init_database',
    'create_tables',
    'drop_tables',
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
    'convert_orm_list_to_dict_list',
    
    # Repositories
    'CompanyRepository',
    'JobCategoryRepository',
    'JobPostingRepository',
    'TemplateRepository',
    'FeedbackSessionRepository',
    'DataRepositoryManager',
    
    # FastAPI DB
    'get_db'
]
