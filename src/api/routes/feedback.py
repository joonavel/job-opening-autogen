"""
Human-in-the-Loop 피드백 API 라우터

sensitivity_validator.py와 호환되는 Human feedback 시스템을 구현합니다.
LangGraph의 interrupt 기능과 연동하여 사용자 피드백을 처리합니다.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Dict, Any, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from ...database.fastapi_db import get_db
from ...database.connection import get_db_session
from ...database.models import FeedbackSession as FeedbackSessionDB, JobPostingTemplate as JobPostingTemplateDB
from ...agents.sensitivity_validator import analyze_sensitivity_with_agent, SensitivityValidationRequest
from ...models.job_posting import UserInput
from ..schemas.requests import (
    FeedbackSessionRequest,
    FeedbackSubmissionRequest
)
from ..schemas.responses import (
    FeedbackSessionResponse,
    FeedbackSubmissionResponse,
    BaseResponse,
    FeedbackSessionListResponse,
    SensitivityValidationStartResponse
)
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

@contextmanager
def get_new_session():
    """새로운 세션 반환"""
    session = get_db_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.exception(f"Failed to get new session: {e}")
        session.rollback()
        raise
    finally:
        session.close()

# 활성 피드백 세션을 관리하는 인메모리 저장소
# 프로덕션 환경에서는 Redis 등을 사용해야 함
active_sessions: Dict[str, Dict[str, Any]] = {}


@router.post("/sessions", response_model=FeedbackSessionResponse)
async def create_feedback_session(
    request: FeedbackSessionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> FeedbackSessionResponse:
    """
    피드백 세션 생성
    
    민감성 검증 과정에서 interrupt가 발생했을 때 호출됩니다.
    """
    try:
        session_id = str(request.feedback_request["thread_id"])
        template_id = str(request.template_id)
        feedback_request = request.feedback_request['questions']
        
        expires_at = datetime.now() + timedelta(seconds=settings.human_loop.session_timeout)
        # 데이터베이스에 세션 저장
        session_db = FeedbackSessionDB(
            session_id=session_id,
            template_id=template_id,
            session_type=request.session_type,
            status="pending",
            feedback_request=feedback_request,
            user_feedback=[],
            created_at=datetime.now()
        )
        
        db.add(session_db)
        db.commit()
        db.refresh(session_db)
        
        # 활성 세션 메모리에 저장
        active_sessions[str(session_id)] = {
            "session_id": session_id,
            "session_type": request.session_type,
            "status": "pending",
            "feedback_request": feedback_request,
            "created_at": datetime.now(),
            "expires_at": expires_at,
            "template_id": request.template_id
        }
        
        # 백그라운드에서 세션 만료 처리 등록
        background_tasks.add_task(
            cleanup_expired_session,
            str(session_id),
            settings.human_loop.session_timeout
        )
        
        logger.info(f"Created feedback session: {session_id}")
        
        return FeedbackSessionResponse(
            success=True,
            message="피드백 세션이 생성되었습니다",
            session_id=session_id,
            session_type=request.session_type,
            status="pending",
            feedback_request=feedback_request,
            user_feedback=None,
            expires_at=expires_at
        )
        
    except Exception as e:
        logger.exception("Failed to create feedback session")
        raise HTTPException(
            status_code=500,
            detail="피드백 세션 생성에 실패했습니다"
        )


@router.post("/sessions/{session_id}/submit", response_model=BaseResponse)
async def submit_feedback(
    session_id: str,
    request: FeedbackSubmissionRequest,
    db: Session = Depends(get_db)
) -> BaseResponse:
    """
    피드백 제출
    
    사용자가 피드백을 제출하여 워크플로우를 재개합니다.
    """
    try:
        session_str = str(session_id)
        
        # 활성 세션 확인
        if session_str not in active_sessions:
            raise HTTPException(
                status_code=404,
                detail="세션을 찾을 수 없거나 만료되었습니다"
            )
        
        session_info = active_sessions[session_str]
        
        if session_info["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail="이미 처리된 세션입니다"
            )
        
        # 데이터베이스에서 세션 조회 및 업데이트
        session_db = db.query(FeedbackSessionDB).filter(
            FeedbackSessionDB.session_id == session_str
        ).first()
        
        if not session_db:
            raise HTTPException(
                status_code=404,
                detail="데이터베이스에서 세션을 찾을 수 없습니다"
            )
        
        # 세션 상태 업데이트
        session_db.status = "completed"
        session_db.user_feedback = request.user_feedback
        session_db.completed_at = datetime.now()
        
        # 활성 세션 정보 업데이트 (메모리에도 저장)
        session_info["status"] = "completed"
        session_info["user_feedback"] = request.user_feedback
        session_info["completed_at"] = datetime.now()
        
        db.commit()
        
        logger.info(f"Feedback submitted for session: {session_id}")
        
        # TODO: 여기서 LangGraph 워크플로우 재개 로직 구현
        # 현재는 mock response 반환
        
        return BaseResponse(
            success=True,
            message="피드백이 성공적으로 제출되었습니다",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to submit feedback for session {session_str}")
        raise HTTPException(
            status_code=500,
            detail="피드백 제출에 실패했습니다"
        )


@router.get("/sessions/{session_id}", response_model=FeedbackSessionResponse)
async def get_feedback_session(
    session_id: str,
    db: Session = Depends(get_db)
) -> FeedbackSessionResponse:
    """
    피드백 세션 조회
    
    특정 세션의 상태와 정보를 조회합니다.
    """
    try:
        session_str = str(session_id)
        
        # 먼저 활성 세션에서 확인
        if session_str in active_sessions:
            session_info = active_sessions[session_str]
            return FeedbackSessionResponse(
                success=True,
                message="피드백 세션 조회 성공",
                session_id=session_info["session_id"],
                session_type=session_info["session_type"],
                status=session_info["status"],
                feedback_request=session_info["feedback_request"],
                user_feedback=session_info.get("user_feedback", None),
                expires_at=session_info["expires_at"]
            )
        
        # 데이터베이스에서 조회
        session_db = db.query(FeedbackSessionDB).filter(
            FeedbackSessionDB.session_id == session_str
        ).first()
        
        if not session_db:
            raise HTTPException(
                status_code=404,
                detail="세션을 찾을 수 없습니다"
            )
        
        expires_at = session_db.created_at + timedelta(seconds=settings.human_loop.session_timeout)
        
        return FeedbackSessionResponse(
            success=True,
            message="피드백 세션 조회 성공",
            session_id=session_db.session_id,
            session_type=session_db.session_type,
            status=session_db.status,
            feedback_request=session_db.feedback_request,
            user_feedback=session_db.user_feedback or None,
            expires_at=expires_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get feedback session {session_str}")
        raise HTTPException(
            status_code=500,
            detail="세션 정보 조회에 실패했습니다"
        )


# @router.post("/validate", response_model=SensitivityValidationStartResponse)
# async def start_sensitivity_validation(
#     user_input: UserInput,
#     background_tasks: BackgroundTasks
# ) -> SensitivityValidationStartResponse:
#     """
#     민감성 검증 시작
    
#     sensitivity_validator.py와 연동하여 민감성 검증을 시작합니다.
#     interrupt가 발생하면 자동으로 피드백 세션이 생성됩니다.
#     """
#     try:
#         thread_id = f"validation_{str(uuid.uuid4())}"
        
#         # 백그라운드에서 민감성 검증 실행
#         background_tasks.add_task(
#             run_sensitivity_validation,
#             user_input,
#             thread_id
#         )
        
#         return SensitivityValidationStartResponse(
#             success=True,
#             message="민감성 검증이 시작되었습니다",
#             thread_id=thread_id
#         )
        
#     except Exception as e:
#         logger.exception("Failed to start sensitivity validation")
#         raise HTTPException(
#             status_code=500,
#             detail="민감성 검증 시작에 실패했습니다"
#         )


# async def run_sensitivity_validation(user_input: UserInput, thread_id: str):
#     """
#     백그라운드에서 민감성 검증 실행
    
#     sensitivity_validator.py의 analyze_sensitivity_with_agent 함수를 사용합니다.
#     """
#     try:
#         logger.info(f"Starting sensitivity validation for thread: {thread_id}")
        
#         request = SensitivityValidationRequest(user_input=user_input)
        
#         # sensitivity_validator.py의 함수 호출
#         validated_input, metadata = analyze_sensitivity_with_agent(request, thread_id)
        
#         logger.info(f"Sensitivity validation completed for thread: {thread_id}")
        
#         # TODO: 결과를 적절한 곳에 저장하거나 알림 처리
        
#     except Exception as e:
#         logger.exception(f"Sensitivity validation failed for thread: {thread_id}")


async def cleanup_expired_session(session_id: str, timeout_seconds: int):
    """
    만료된 세션 정리
    
    지정된 시간 후에 세션을 정리합니다.
    """
    try:
        await asyncio.sleep(timeout_seconds)
        
        if session_id in active_sessions:
            session_info = active_sessions[session_id]
            if session_info["status"] == "pending":
                # 만료된 세션 처리
                session_info["status"] = "expired"
                logger.info(f"Session {session_id} expired")
            
            # 메모리에서 제거
            del active_sessions[session_id]
            
        session_str = str(session_id)
        with get_new_session() as db:
            # 데이터베이스에서 상태 업데이트
            session_db = db.query(FeedbackSessionDB).filter(
                FeedbackSessionDB.session_id == session_str
            ).first()
            
            if session_db:
                session_db.status = "expired"
                session_db.completed_at = datetime.now()
                db.commit()
            
    except Exception as e:
        logger.exception(f"Failed to cleanup session {session_id}")


# @router.delete("/sessions/{session_id}", response_model=BaseResponse)
# async def cancel_feedback_session(
#     session_id: str,
#     db: Session = Depends(get_db)
# ) -> BaseResponse:
#     """
#     피드백 세션 취소
    
#     사용자가 세션을 취소합니다.
#     """
#     try:
#         session_str = str(session_id)
        
#         # 활성 세션에서 제거
#         if session_str in active_sessions:
#             del active_sessions[session_str]
        
#         # 데이터베이스에서 상태 업데이트
#         session_db = db.query(FeedbackSessionDB).filter(
#             FeedbackSessionDB.session_id == session_str
#         ).first()
        
#         if session_db:
#             session_db.status = "cancelled"
#             session_db.completed_at = datetime.now()
#             db.commit()
        
#         return BaseResponse(
#             success=True,
#             message="피드백 세션이 취소되었습니다"
#         )
        
#     except Exception as e:
#         logger.exception(f"Failed to cancel session {session_str}")
#         raise HTTPException(
#             status_code=500,
#             detail="세션 취소에 실패했습니다"
#         )


# @router.get("/sessions", response_model=FeedbackSessionListResponse)
# async def list_active_sessions() -> FeedbackSessionListResponse:
#     """
#     활성 피드백 세션 목록 조회
    
#     현재 활성화된 모든 피드백 세션을 조회합니다.
#     """
#     try:
#         sessions_list = []
        
#         for session_id, session_info in active_sessions.items():
#             sessions_list.append({
#                 "session_id": session_info["session_id"],
#                 "session_type": session_info["session_type"],
#                 "status": session_info["status"],
#                 "created_at": session_info["created_at"],
#                 "expires_at": session_info["expires_at"]
#             })
        
#         return FeedbackSessionListResponse(
#             success=True,
#             message=f"{len(sessions_list)}개의 활성 세션을 조회했습니다",
#             sessions=sessions_list
#         )
        
#     except Exception as e:
#         logger.exception("Failed to list active sessions")
#         raise HTTPException(
#             status_code=500,
#             detail="활성 세션 목록 조회에 실패했습니다"
#         )
