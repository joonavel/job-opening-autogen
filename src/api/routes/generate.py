"""
채용공고 생성 API 라우터

사용자 입력을 받아 LangGraph 워크플로우를 통해 채용공고를 생성합니다.
job_posting.py의 모델들과 연동되며 전체 생성 파이프라인을 관리합니다.
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session, sessionmaker
from contextlib import contextmanager

from ...database.fastapi_db import get_db
from ...database.models import (
    JobPostingTemplate as JobPostingTemplateDB,
    Company,
    FeedbackSession as FeedbackSessionDB
)
from ...database.connection import get_db_session

from ...models.job_posting import (
    UserInput,
    JobPostingTemplate,
    JobPostingDraft,
    ValidationResult,
    ValidationStatus
)
from ..schemas.requests import (
    GenerateJobPostingRequest,
    ValidationRequest,
    TemplateUpdateRequest
)
from ..schemas.responses import (
    JobPostingResponse,
    GenerationStatusResponse,
    ValidationSummaryResponse,
    BaseResponse,
    StreamingResponse as StreamingResponseSchema
)
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# LangGraph MemorySaver를 통한 통합 상태 관리
from langgraph.checkpoint.memory import MemorySaver

# 전역 MemorySaver 인스턴스 (싱글톤)
_global_checkpointer = MemorySaver()

def get_global_checkpointer():
    """전역 MemorySaver 체크포인터 반환"""
    return _global_checkpointer

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

@router.post("/", status_code=202, response_model=BaseResponse)
async def generate_job_posting(
    request: GenerateJobPostingRequest,
) -> BaseResponse:
    """
    채용공고 생성
    
    사용자 입력을 바탕으로 LangGraph 워크플로우를 실행하여 채용공고를 생성합니다.
    민감성 검증, 품질 검증 등의 단계를 거치며 필요시 Human-in-the-Loop이 실행됩니다.
    """
    try:
        # 세션 ID를 워크플로우 ID로 사용 (stateful 세션 관리)
        workflow_id = request.session_id
        
        logger.info(f"Starting job posting generation: {workflow_id} (session-based: {bool(request.session_id)})")
        asyncio.create_task(run_generation_workflow(workflow_id, request.user_input))
        
        return BaseResponse(
            success=True,
            message="채용공고 워크 플로우가 시작 되었습니다",
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.exception("Failed to generate job posting")
        raise HTTPException(
            status_code=500,
            detail="채용공고 생성 중 오류가 발생했습니다"
        )


async def run_generation_workflow(
    workflow_id: str,
    user_input: str,  # 자연어 텍스트 입력
):
    """
    백그라운드에서 MVP 채용공고 생성 워크플로우 실행
    
    JobPostingWorkflow.run 패턴을 참고하여 LangGraph 워크플로우를 직접 실행합니다.
    모든 상태는 LangGraph MemorySaver에서 자동 관리됩니다.
    """
    try:
        logger.info(f"Starting job posting workflow execution: {workflow_id}")
        
        # MVP 워크플로우 가져오기 (싱글톤 패턴)
        from ...workflows.job_posting_workflow import get_workflow
        checkpointer = get_global_checkpointer()
        job_posting_workflow = get_workflow(checkpointer)
        
        def _run_blocking():
            return job_posting_workflow.run(
                raw_input=user_input,
                workflow_id=workflow_id
            )
        
        result = await asyncio.to_thread(_run_blocking)
        
        # JobPostingWorkflow.run과 동일한 패턴으로 실행
        # LangGraph가 자동으로 상태를 MemorySaver에 관리
        # result = job_posting_workflow.run(
        #     raw_input=user_input,  # 자연어 입력
        #     workflow_id=workflow_id
        # )
        
        logger.info(f"Job Posting Workflow {workflow_id} completed successfully")
        
        # 결과를 DB에 저장 (선택사항)
        if result and result.get("status") == "completed":
            try:
                await asyncio.to_thread(save_workflow_result_to_db, workflow_id, result)
                logger.info(f"Workflow result saved to database: {workflow_id}")
            except Exception as db_error:
                logger.warning(f"Failed to save result to DB: {db_error}")
        else:
            logger.warning(f"Workflow result is not completed: {workflow_id}")
    except Exception as e:
        logger.exception(f"Job Posting Workflow {workflow_id} failed: {e}")                                                                                                                                                                     
        # LangGraph가 오류 상태도 자동으로 MemorySaver에 저장함

# 워크플로우 결과를 데이터베이스에 저장
def save_workflow_result_to_db(workflow_id: str, result: Dict[str, Any]):                    
    """워크플로우 결과를 데이터베이스에 저장"""                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     
    job_posting_draft = result.get("job_posting_draft")
    if not job_posting_draft:
        return
    
    safe_result = jsonable_encoder(result)
    status = safe_result.get("status", "error")
    safe_draft = job_posting_draft.model_dump(mode="json")
    
    data_source_tracking = safe_result.get("data_source_tracking", {})
    source_emp_co_no = data_source_tracking.get("db_record_emp_co_no", None)
    source_emp_seq_no = data_source_tracking.get("db_record_emp_seq_no", None)
    
    meta = {
        "workflow_id": workflow_id,
        "generated_by": "mvp_workflow",
        "completed_at": datetime.now().isoformat()
    }
    
    validation_metadata = {
            "sensitivity_validation_metadata": safe_result.get("sensitivity_validation_metadata", {}),
            "structured_input_metadata": safe_result.get("structured_input_metadata", {}),
            "draft_metadata": safe_result.get("draft_metadata", {}),
            "hallucination_validation_metadata": safe_result.get("hallucination_validation_metadata", {}),
    }
    
    with get_new_session() as s:
        try:
            # JobPostingTemplate DB 저장
            template_db = JobPostingTemplateDB(
                template_id=workflow_id,
                source_emp_seq_no=source_emp_seq_no,
                source_emp_co_no=source_emp_co_no,
                title=job_posting_draft.title,
                content=job_posting_draft.job_description,
                template_data=safe_draft,
                generation_status=status,
                generation_metadata=meta,
                validation_metadata=validation_metadata
            )
        
            s.add(template_db)
            s.commit()
    
        except Exception as e:
            logger.exception(f"Failed to save workflow result: {workflow_id}")
            s.rollback()
            raise


# def create_mock_template(user_input: UserInput, workflow_id: str) -> JobPostingTemplate:
#     """Mock 템플릿 생성 (개발용)"""
#     from ...models.job_posting import JobPostingMetadata
    
#     metadata = JobPostingMetadata()
    
#     return JobPostingTemplate(
#         title=f"{user_input.job_title} 채용",
#         company_name=user_input.company_name,
#         job_description=f"{user_input.company_name}에서 {user_input.job_title}를 모집합니다. "
#                        f"저희와 함께 성장할 인재를 찾고 있습니다.",
#         requirements=user_input.requirements,
#         preferred_qualifications=user_input.preferred_qualifications,
#         job_type=user_input.job_type,
#         experience_level=user_input.experience_level,
#         salary_info=user_input.salary_info,
#         work_location=user_input.work_location,
#         metadata=metadata,
#         generated_by="mock_generator"
#     )
    
    
@router.get("/status/{workflow_id}", response_model=GenerationStatusResponse)
async def get_generation_status(
    workflow_id: str
) -> GenerationStatusResponse:
    """
    생성 상태 조회
    
    특정 워크플로우의 생성 진행 상황을 조회합니다.
    """
    try:
        # MemorySaver에서 워크플로우 상태 조회
        checkpointer = get_global_checkpointer()
        config = {"configurable": {"thread_id": workflow_id}}
        
        try:
            # JobPostingWorkflow의 get_workflow_state 사용
            saved_state = checkpointer.get(config)
            if not saved_state:
                return GenerationStatusResponse(
                    workflow_id=workflow_id,
                    status="not_found",
                    current_step="unknown",
                    job_posting_draft=None,
                    metadata={}
                )
            
            # 상태값 추출
            state_values = saved_state.get("channel_values")
            status = state_values.get("status", "not_found")
            current_step = state_values.get("current_step", "error")
            # 결과 데이터
            job_posting_draft = state_values.get("job_posting_draft", None)
            metadata = {
                "sensitivity_validation_metadata": state_values.get("sensitivity_validation_metadata", {}),
                "structured_input_metadata": state_values.get("structured_input_metadata", {}),
                "draft_metadata": state_values.get("draft_metadata", {}),
                "hallucination_validation_metadata": state_values.get("hallucination_validation_metadata", {}),
            }
            
            return GenerationStatusResponse(
                workflow_id=workflow_id,
                status=status,
                current_step=current_step,
                job_posting_draft=job_posting_draft,
                metadata=metadata
            )
            
        except Exception as e:
            logger.warning(f"워크플로우 상태 조회 실패: {e}")
            return GenerationStatusResponse(
                workflow_id=workflow_id,
                status="error",
                current_step="error",
                job_posting_draft=None,
                metadata={}
            )
        
    except Exception as e:
        logger.exception(f"Failed to get status for workflow {workflow_id}")
        raise HTTPException(
            status_code=500,
            detail="상태 조회 중 오류가 발생했습니다"
        )


# @router.get("/stream/{workflow_id}")
# async def stream_generation_progress(workflow_id: str):
#     """
#     생성 진행 상황 스트리밍
    
#     Server-Sent Events를 통해 실시간으로 생성 진행 상황을 전송합니다.
#     """
#     # MemorySaver에서 워크플로우 존재 확인
#     checkpointer = get_global_checkpointer()
#     config = {"configurable": {"thread_id": workflow_id}}
    
#     try:
#         checkpoint = checkpointer.get(config)
#         if not checkpoint:
#             raise HTTPException(
#                 status_code=404,
#                 detail="워크플로우를 찾을 수 없습니다"
#             )
#     except Exception:
#         raise HTTPException(
#             status_code=404,
#             detail="워크플로우를 찾을 수 없습니다"
#         )
    
#     async def event_stream():
#         """SSE 이벤트 스트림 생성기"""
#         sequence = 0
#         last_status = None
        
#         try:
#             while True:
#                 # MemorySaver에서 현재 상태 조회
#                 try:
#                     checkpoint = checkpointer.get(config)
#                     if not checkpoint:
#                         break  # 워크플로우가 삭제됨
#                     workflow_state = checkpoint.channel_values
#                     current_status = workflow_state["status"]
#                 except Exception:
#                     break  # 오류 시 스트림 종료
                
#                 # 상태가 변경된 경우만 전송
#                 if current_status != last_status:
#                     event_data = StreamingResponseSchema(
#                         event_type="status_update",
#                         data={
#                             "workflow_id": workflow_id,
#                             "status": current_status,
#                             "progress": workflow_state["progress"],
#                             "current_step": workflow_state["current_step"],
#                             "updated_at": workflow_state["updated_at"].isoformat()
#                         },
#                         sequence=sequence
#                     )
                    
#                     yield f"data: {event_data.model_dump_json()}\n\n"
#                     sequence += 1
#                     last_status = current_status
                
#                 # 완료된 경우 스트림 종료
#                 if current_status in ["completed", "failed", "cancelled"]:
#                     break
                
#                 await asyncio.sleep(1)  # 1초마다 상태 확인
            
#         except Exception as e:
#             logger.exception(f"Error in event stream for workflow {workflow_id}")
#             error_event = StreamingResponseSchema(
#                 event_type="error",
#                 data={"error": "Stream error occurred"},
#                 sequence=sequence
#             )
#             yield f"data: {error_event.model_dump_json()}\n\n"
    
#     return StreamingResponse(
#         event_stream(),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "Connection": "keep-alive",
#             "Access-Control-Allow-Origin": "*",
#             "Access-Control-Allow-Headers": "Cache-Control"
#         }
#     )


# @router.post("/validate", response_model=ValidationSummaryResponse)
# async def validate_user_input(
#     request: ValidationRequest,
#     db: Session = Depends(get_db)
# ) -> ValidationSummaryResponse:
#     """
#     사용자 입력 검증
    
#     채용공고 생성 전에 사용자 입력을 미리 검증합니다.
#     """
#     try:
#         validation_results = []
        
#         # 각 검증 유형별로 검증 수행
#         for validation_type in request.validation_types:
#             if validation_type == "sensitivity":
#                 result = perform_sensitivity_validation(request.user_input)
#             elif validation_type == "completeness":
#                 result = perform_completeness_validation(request.user_input)
#             elif validation_type == "quality":
#                 result = perform_quality_validation(request.user_input)
#             else:
#                 continue
            
#             validation_results.append(result)
        
#         # 전체 상태 및 점수 계산
#         overall_scores = [r.score for r in validation_results]
#         overall_score = sum(overall_scores) / len(overall_scores) if overall_scores else 0
        
#         # 전체 상태 결정
#         failed_validations = [r for r in validation_results if r.status == ValidationStatus.FAILED]
#         if failed_validations:
#             overall_status = ValidationStatus.FAILED
#         elif any(r.status == ValidationStatus.REQUIRES_REVIEW for r in validation_results):
#             overall_status = ValidationStatus.REQUIRES_REVIEW
#         else:
#             overall_status = ValidationStatus.PASSED
        
#         # 추천사항 수집
#         recommendations = []
#         for result in validation_results:
#             recommendations.extend(result.suggestions)
        
#         return ValidationSummaryResponse(
#             success=True,
#             message=f"{len(request.validation_types)}개 항목에 대한 검증을 완료했습니다",
#             validation_results=validation_results,
#             overall_status=overall_status,
#             overall_score=overall_score,
#             recommendations=list(set(recommendations))  # 중복 제거
#         )
        
#     except Exception as e:
#         logger.exception("Failed to validate user input")
#         raise HTTPException(
#             status_code=500,
#             detail="입력 검증 중 오류가 발생했습니다"
#         )


# @router.put("/templates/{template_id}", response_model=BaseResponse)
# async def update_template(
#     template_id: str,
#     request: TemplateUpdateRequest,
#     db: Session = Depends(get_db)
# ) -> BaseResponse:
#     """
#     템플릿 수정
    
#     생성된 템플릿을 사용자 피드백에 따라 수정합니다.
#     """
#     try:
#         # 데이터베이스에서 템플릿 조회
#         template_db = db.query(JobPostingTemplateDB).filter(
#             JobPostingTemplateDB.template_id == template_id
#         ).first()
        
#         if not template_db:
#             raise HTTPException(
#                 status_code=404,
#                 detail="템플릿을 찾을 수 없습니다"
#             )
        
#         # 기존 템플릿 데이터 업데이트
#         current_data = template_db.template_data or {}
#         current_data.update(request.updates)
        
#         template_db.template_data = current_data
#         template_db.updated_at = datetime.now()
        
#         # 수정 이력 기록 (메타데이터에 추가)
#         generation_metadata = template_db.generation_metadata or {}
#         if "update_history" not in generation_metadata:
#             generation_metadata["update_history"] = []
        
#         generation_metadata["update_history"].append({
#             "timestamp": datetime.now().isoformat(),
#             "updates": request.updates,
#             "reason": request.update_reason
#         })
        
#         template_db.generation_metadata = generation_metadata
        
#         db.commit()
        
#         logger.info(f"Template {template_id} updated: {request.update_reason}")
        
#         return BaseResponse(
#             success=True,
#             message="템플릿이 성공적으로 수정되었습니다"
#         )
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.exception(f"Failed to update template {template_id}")
#         raise HTTPException(
#             status_code=500,
#             detail="템플릿 수정 중 오류가 발생했습니다"
#         )





# def perform_sensitivity_validation(user_input: UserInput) -> ValidationResult:
#     """민감성 검증 수행"""
#     # Mock implementation
#     return ValidationResult(
#         status=ValidationStatus.PASSED,
#         score=95.0,
#         issues=[],
#         suggestions=[],
#         validator_type="sensitivity_validator"
#     )


# def perform_completeness_validation(user_input: UserInput) -> ValidationResult:
#     """완성도 검증 수행"""
#     score = 80.0
#     issues = []
#     suggestions = []
    
#     if not user_input.requirements:
#         score -= 20
#         issues.append("필수 요구사항이 없습니다")
#         suggestions.append("최소 1개 이상의 필수 요구사항을 추가해주세요")
    
#     if len(user_input.requirements) < 3:
#         score -= 10
#         suggestions.append("더 구체적인 요구사항을 추가하는 것을 권장합니다")
    
#     status = ValidationStatus.PASSED if score >= 70 else ValidationStatus.REQUIRES_REVIEW
    
#     return ValidationResult(
#         status=status,
#         score=score,
#         issues=issues,
#         suggestions=suggestions,
#         validator_type="completeness_validator"
#     )


# def perform_quality_validation(user_input: UserInput) -> ValidationResult:
#     """품질 검증 수행"""
#     # Mock implementation
#     return ValidationResult(
#         status=ValidationStatus.PASSED,
#         score=85.0,
#         issues=[],
#         suggestions=["더 구체적인 업무 설명을 추가하면 좋겠습니다"],
#         validator_type="quality_validator"
#     )


# def save_template_to_db(
#     workflow_id: str,
#     user_input: UserInput,
#     company_data: Optional[Dict[str, Any]],
#     template_options: Dict[str, Any],
#     db: Session
# ):
#     """생성된 템플릿을 데이터베이스에 저장"""
#     try:
#         template = create_mock_template(user_input, workflow_id)
        
#         template_db = JobPostingTemplateDB(
#             template_id=template.metadata.id,
#             title=template.title,
#             content=template.job_description,
#             template_data=template.model_dump(),
#             generation_status="completed",
#             generation_metadata={
#                 "workflow_id": workflow_id,
#                 "generated_by": "mock_generator",
#                 "template_options": template_options
#             }
#         )
        
#         db.add(template_db)
#         db.commit()
        
#         logger.info(f"Template saved to database: {template.metadata.id}")
        
#     except Exception as e:
#         logger.exception(f"Failed to save template for workflow {workflow_id}")
#         db.rollback()
