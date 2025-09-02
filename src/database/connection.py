"""
데이터베이스 연결 관리
PostgreSQL 연결, 세션 관리, 테이블 생성 등
"""

import os
from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import URL

from .models import Base, FeedbackSession
from ..exceptions import DatabaseError
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """데이터베이스 연결 및 세션 관리 클래스"""
    
    def __init__(self):
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._scoped_session: Optional[scoped_session] = None
        
    def initialize(self, database_url: Optional[str] = None) -> None:
        """데이터베이스 초기화"""
        try:
            if database_url is None:
                database_url = self._build_database_url()
            
            # 엔진 생성
            self._engine = create_engine(
                database_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,  # 연결 상태 확인
                pool_recycle=3600,   # 1시간마다 연결 재생성
                echo=os.getenv("DB_ECHO", "false").lower() == "true"
            )
            
            # 세션 팩토리 생성
            self._session_factory = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
            
            # Scoped session 생성 (스레드 안전)
            self._scoped_session = scoped_session(self._session_factory)
            
            logger.info("데이터베이스 연결이 성공적으로 초기화되었습니다")
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {e}")
            raise DatabaseError(f"데이터베이스 초기화 실패: {e}")
    
    def _build_database_url(self) -> str:
        """환경변수에서 데이터베이스 URL 구성"""
        # DATABASE_URL이 있으면 우선 사용
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            return database_url
        
        # 개별 환경변수로 구성
        db_config = {
            "drivername": "postgresql+psycopg2",
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "5432")),
            "database": os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "job_openings_db")),
            "username": os.getenv("DB_USER", os.getenv("POSTGRES_USER", "postgres")),
            "password": os.getenv("DB_PASSWORD", os.getenv("POSTGRES_PASSWORD", "postgres123"))
        }
        
        return URL.create(**db_config).__str__()
    
    def create_tables(self) -> None:
        """모든 테이블 생성"""
        if self._engine is None:
            raise DatabaseError("데이터베이스가 초기화되지 않았습니다")
        
        try:
            Base.metadata.create_all(bind=self._engine)
            logger.info("데이터베이스 테이블이 성공적으로 생성되었습니다")
        except Exception as e:
            logger.error(f"테이블 생성 실패: {e}")
            raise DatabaseError(f"테이블 생성 실패: {e}")
    
    def drop_tables(self) -> None:
        """모든 테이블 삭제 (개발/테스트용)"""
        if self._engine is None:
            raise DatabaseError("데이터베이스가 초기화되지 않았습니다")
        
        try:
            Base.metadata.drop_all(bind=self._engine, tables=[FeedbackSession.__table__])
            Base.metadata.drop_all(bind=self._engine)
            logger.info("데이터베이스 테이블이 성공적으로 삭제되었습니다")
        except Exception as e:
            logger.error(f"테이블 삭제 실패: {e}")
            raise DatabaseError(f"테이블 삭제 실패: {e}")
    
    def get_session(self) -> Session:
        """새로운 세션 반환"""
        if self._scoped_session is None:
            raise DatabaseError("데이터베이스가 초기화되지 않았습니다")
        
        return self._scoped_session()
    
    def remove_session(self) -> None:
        """현재 스레드의 세션 제거"""
        if self._scoped_session:
            self._scoped_session.remove()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """자동 트랜잭션 관리를 위한 컨텍스트 매니저"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"데이터베이스 트랜잭션 롤백: {e}")
            raise
        finally:
            session.close()
    
    def test_connection(self) -> bool:
        """데이터베이스 연결 테스트"""
        if self._engine is None:
            return False
        
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("데이터베이스 연결 테스트 성공")
            return True
        except Exception as e:
            logger.error(f"데이터베이스 연결 테스트 실패: {e}")
            return False
    
    def close(self) -> None:
        """연결 종료"""
        if self._scoped_session:
            self._scoped_session.remove()
        if self._engine:
            self._engine.dispose()
        logger.info("데이터베이스 연결이 종료되었습니다")


# 전역 데이터베이스 매니저 인스턴스
db_manager = DatabaseManager()


def init_database(database_url: Optional[str] = None) -> None:
    """데이터베이스 초기화 함수"""
    db_manager.initialize(database_url)


def create_tables() -> None:
    """테이블 생성 함수"""
    db_manager.create_tables()

def drop_tables() -> None:
    """테이블 삭제 함수"""
    db_manager.drop_tables()


def get_db_session() -> Session:
    """데이터베이스 세션 조회 함수"""
    return db_manager.get_session()


@contextmanager
def db_session_scope() -> Generator[Session, None, None]:
    """트랜잭션 관리 컨텍스트 매니저"""
    with db_manager.session_scope() as session:
        yield session


def test_db_connection() -> bool:
    """데이터베이스 연결 테스트 함수"""
    return db_manager.test_connection()


def close_db_connection() -> None:
    """데이터베이스 연결 종료 함수"""
    db_manager.close()
