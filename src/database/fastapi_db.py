"""
FastAPI 전용 데이터베이스 연결 관리

FastAPI의 dependency injection 시스템을 위한 데이터베이스 연결을 제공합니다.
기존 connection.py와는 별도로 관리되며, API 엔드포인트에서만 사용됩니다.
"""

import logging
from typing import Generator

from sqlalchemy.orm import Session

from .connection import get_db_session, test_db_connection, db_manager

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 의존성 주입용 데이터베이스 세션
    
    FastAPI 엔드포인트에서 Depends(get_db)로 사용됩니다.
    자동으로 세션을 생성하고 요청 완료 후 정리합니다.
    
    Usage:
        @router.post("/")
        async def create_item(db: Session = Depends(get_db)):
            # db 사용
    """
    db = get_db_session()
    try:
        yield db
    except Exception as e:
        logger.error(f"FastAPI database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def check_database_connection() -> bool:
    """
    FastAPI 헬스체크용 데이터베이스 연결 확인
    
    기존 connection.py의 test_db_connection을 래핑합니다.
    """
    return test_db_connection()


class FastAPIDatabaseManager:
    """
    FastAPI 전용 데이터베이스 관리자
    
    API 서버 관련 데이터베이스 기능만을 담당합니다.
    """
    
    def __init__(self):
        self.session_factory = get_db_session
    
    def get_dependency(self):
        """의존성 주입용 함수 반환"""
        return get_db
    
    def health_check(self) -> bool:
        """API 헬스체크용"""
        return check_database_connection()
    
    def create_manual_session(self) -> Session:
        """
        수동 세션 생성 (API에서 특별한 경우에만 사용)
        
        주의: 반드시 session.close()를 호출해야 함
        """
        return self.session_factory()


# FastAPI 전용 매니저 인스턴스
fastapi_db_manager = FastAPIDatabaseManager()
