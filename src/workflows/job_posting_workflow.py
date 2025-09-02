"""
LangGraph를 활용한 채용공고 생성 워크플로우

이 모듈은 채용공고 자동생성을 위한 핵심 워크플로우를 정의합니다.
- 기업 데이터 검색 및 조회
- 사용자 입력 구조화 및 검증
- LLM을 통한 채용공고 초안 생성
- 단계별 상태 관리 및 체크포인트
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from typing_extensions import NotRequired
from datetime import datetime
import logging

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages

from ..models.job_posting import (
    JobPostingDraft, UserInput, CompanyData, ValidationResult, ValidationStatus
)
from ..database.repositories import CompanyRepository, DataRepositoryManager
from ..database.connection import db_session_scope
from ..exceptions import WorkflowError, DatabaseError
from ..components.natural_language_processor import (
    get_natural_language_processor, ProcessingContext
)
from ..components.generator import get_job_posting_generator, GenerationContext
from ..agents.sensitivity_validator import SensitivityValidationRequest, analyze_sensitivity_with_agent
from ..agents.hallucination_validator import HallucinationValidationRequest, analyze_intrinsic_consistency_with_agent
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)


@contextmanager
def get_repositories() -> Generator[DataRepositoryManager, None, None]:
    """리포지토리 매니저 컨텍스트 매니저"""
    with db_session_scope() as session:
        repo_manager = DataRepositoryManager(session)
        try:
            yield repo_manager
        except Exception as e:
            repo_manager.rollback()
            raise DatabaseError(f"트랜잭션 오류: {str(e)}")
        else:
            repo_manager.commit()


class WorkflowState(TypedDict):
    """
    LangGraph 워크플로우 상태 정의
    
    채용공고 생성 과정에서 사용되는 모든 상태 정보를 관리합니다.
    """
    # === 원시 입력 데이터 ===
    raw_input: Annotated[Optional[str], "사용자의 자연어 입력"]
    user_input: Annotated[Optional[UserInput], "구조화된 사용자 입력 데이터"] 
    # === 민감성 검증 결과 ===
    sensitivity_validation_metadata: Annotated[Optional[Dict[str, Any]], "민감성 검증 메타데이터"]
    
    # === 검색된 데이터 ===
    company_query: Annotated[Optional[str], "기업 검색 쿼리"]
    company_data: Annotated[Optional[CompanyData], "검색된 기업 정보"]
    
    # === 환각 검증을 위한 추적 정보 ===
    data_source_tracking: Annotated[Optional[Dict[str, Any]], "데이터 출처 및 신뢰성 정보"]
    verification_metadata: Annotated[Optional[Dict[str, Any]], "검증을 위한 메타데이터"]
    
    # === 구조화된 입력 ===
    structured_input: Annotated[Optional[Dict[str, Any]], "구조화된 입력 데이터"]
    validation_results: Annotated[List[ValidationResult], "검증 결과"]
    structured_input_metadata: Annotated[Optional[Dict[str, Any]], "구조화된 입력 메타데이터"]
    
    # === 생성된 결과 ===
    job_posting_draft: Annotated[Optional[JobPostingDraft], "생성된 채용공고 초안"]
    draft_metadata: Annotated[Optional[Dict[str, Any]], "생성된 채용공고 초안 메타데이터"]
    
    # === 환각 검증 결과 ===
    hallucination_validation_metadata: Annotated[Optional[Dict[str, Any]], "환각 검증 메타데이터"]
    
    # === 워크플로우 메타데이터 ===
    workflow_id: Annotated[str, "워크플로우 고유 ID"]
    current_step: Annotated[str, "현재 단계"]
    status: Annotated[str, "현재 상태"]
    errors: Annotated[List[str], "발생한 오류들"]
    warnings: Annotated[List[str], "경고 메시지들"]
    
    # === 실행 정보 ===
    step_count: Annotated[int, "실행된 단계 수"]
    start_time: Annotated[datetime, "시작 시간"]
    last_updated: Annotated[datetime, "마지막 업데이트 시간"]
      
    # === 선택적 필드 ===
    debug_info: Annotated[Optional[Dict[str, Any]], "디버깅 정보"]


def structure_natural_language_input(state: WorkflowState) -> WorkflowState:
    """
    0단계: 자연어 입력을 구조화된 UserInput으로 변환
    
    사용자의 자연어 입력을 분석하여 구조화된 UserInput 모델로 변환합니다.
    이 단계는 기업 데이터 검색 전에 수행되어 명확한 검색 조건을 설정합니다.
    """
    logger.info(f"워크플로우 {state['workflow_id']}: 자연어 입력 구조화 시작")
    if state.get("user_input", None):
        logger.info(f"이미 구조화된 입력 데이터가 있습니다: {state['user_input']}")
        return state
    
    try:
        # 현재 단계 업데이트
        state["current_step"] = "structure_natural_language_input"
        state["status"] = "running"
        state["step_count"] = state.get("step_count", 0) + 1
        state["last_updated"] = datetime.now()
        
        # 자연어 입력 확인
        raw_input = state.get("raw_input")
        if not raw_input:
            raise WorkflowError("자연어 입력 데이터가 없습니다")
        
        # 자연어 처리기를 통한 구조화
        processor = get_natural_language_processor()
        
        processing_context = ProcessingContext(
            raw_input=raw_input,
            processing_metadata={
                "workflow_id": state["workflow_id"],
                "timestamp": datetime.now(),
                "processing_method": "llm_based"
            }
        )
        
        structured_user_input, metadata = processor.process_natural_language_input(processing_context)
        
        # 상태에 구조화된 입력 저장
        state["user_input"] = structured_user_input
        state["structured_input_metadata"] = metadata
        logger.info(f"자연어 입력 구조화 완료: {structured_user_input.job_title} @ {structured_user_input.company_name}")
        
    except Exception as e:
        error_msg = f"자연어 입력 구조화 중 예상치 못한 오류: {str(e)}"
        logger.error(error_msg)
        
        state.setdefault("errors", []).append(error_msg)
        state["current_step"] = "error"
        state["status"] = "error"
        
    return state

def call_sensitivity_validation_agent(state: WorkflowState) -> WorkflowState:
    """
    1단계: 민감성 검증 에이전트 호출
    
    사용자 입력을 바탕으로 민감성 검증 에이전트를 호출하여 검증 결과를 반환합니다.
    """
    logger.info(f"워크플로우 {state['workflow_id']}: 민감성 검증 에이전트 호출 시작")
    
    try:
        # 현재 단계 업데이트
        state["current_step"] = "call_sensitivity_validation_agent"
        state["status"] = "running"
        state["step_count"] = state.get("step_count", 0) + 1
        state["last_updated"] = datetime.now()
        
        # 구조화된 사용자 입력 확인
        user_input = state.get("user_input")
        if not user_input:
            raise WorkflowError("구조화된 사용자 입력 데이터가 없습니다")

        thread_id = state["workflow_id"]
        
        result = analyze_sensitivity_with_agent(SensitivityValidationRequest(user_input=user_input), thread_id)
        if not result or not isinstance(result, tuple) or len(result) != 2:
            raise WorkflowError(f"민감성 검증 에이전트 호출 결과 형식이 tuple이 아닙니다: {type(result)}")
        
        validated_user_input, metadata = result
        # 상태에 구조화된 입력 저장
        state["user_input"] = validated_user_input
        state["sensitivity_validation_metadata"] = metadata
        logger.info(f"구조화된 사용자 입력 검증 및 첨삭 완료:\n{metadata['generated_by']}:\n{metadata['reasoning']}")
        
    except Exception as e:
        error_msg = f"민감성 검증 에이전트 호출 중 예상치 못한 오류: {str(e)}"
        logger.error(error_msg)
        
        state.setdefault("errors", []).append(error_msg)
        state["current_step"] = "error"
        state["status"] = "error"
        
    return state

def retrieve_company_data(state: WorkflowState) -> WorkflowState:
    """
    2단계: 기업 데이터 검색 및 조회 (환각 검증용 추적 정보 포함)
    
    사용자 입력의 기업 정보를 바탕으로 데이터베이스에서
    상세한 기업 정보를 검색하고 조회합니다.
    환각 검증 에이전트가 추적할 수 있도록 상세한 메타데이터를 포함합니다.
    """
    logger.info(f"워크플로우 {state['workflow_id']}: 기업 데이터 검색 시작")
    
    try:
        # 현재 단계 업데이트
        state["current_step"] = "retrieve_company_data"
        state["status"] = "running"
        state["step_count"] = state.get("step_count", 0) + 1
        state["last_updated"] = datetime.now()
        
        # 사용자 입력에서 기업 정보 추출
        user_input = state.get("user_input")
        if not user_input:
            raise WorkflowError("사용자 입력 데이터가 없습니다")
        
        # CompanyRepository를 사용하여 데이터베이스에서 기업 정보 검색
        company_name = user_input.company_name
        search_timestamp = datetime.now()
        
        # 환각 검증을 위한 추적 정보 초기화
        data_source_tracking = {
            "original_company_name": company_name,
            "search_timestamp": search_timestamp,
            "search_attempts": [],
            "data_completeness_score": 0.0,
            "reliability_indicators": {},
            "verification_flags": []
        }
        
        with get_repositories() as repos:
            try:
                # 1. 기업명으로 검색 시도
                search_attempt = {
                    "method": "exact_name_search",
                    "query": company_name,
                    "timestamp": datetime.now()
                }
                
                companies = repos.companies.search_companies(
                    name_query=company_name,
                    limit=3  # 여러 결과를 가져와서 추적
                )
                
                search_attempt["results_count"] = len(companies)
                data_source_tracking["search_attempts"].append(search_attempt)
                
                if companies:
                    # DB에서 기업 정보를 찾은 경우
                    db_company = companies[0]  # 첫 번째 결과 사용
                    
                    # 추가 기업 정보도 추적 (환각 검증용)
                    alternative_companies = companies[1:] if len(companies) > 1 else []
                    
                    company_data = CompanyData(
                        company_name=db_company.company_name or company_name,
                        company_classification=db_company.company_classification,
                        homepage=db_company.homepage,
                        logo_url=db_company.logo_url,
                        intro_summary=db_company.intro_summary,
                        intro_detail=db_company.intro_detail,
                        main_business=db_company.main_business,
                    )
                    
                    data_source = "database"
                    
                    # 환각 검증용 신뢰성 정보 수집
                    data_source_tracking.update({
                        "db_record_emp_co_no": db_company.emp_co_no,
                        "db_record_created": db_company.created_at if hasattr(db_company, 'created_at') else None,
                        "db_record_updated": db_company.updated_at if hasattr(db_company, 'updated_at') else None,
                        "exact_name_match": db_company.company_name == company_name,
                        "alternative_matches": len(alternative_companies),
                    })
                    
                    # 데이터 완성도 점수 계산
                    completeness_fields = [
                        'company_classification', 'homepage', 'logo_url',
                        'intro_summary', 'intro_detail', 'main_business'
                    ]
                    filled_fields = sum(1 for field in completeness_fields 
                                      if getattr(company_data, field) is not None)
                    data_source_tracking["data_completeness_score"] = (filled_fields / len(completeness_fields)) * 100
                              
                    logger.info(f"DB에서 기업 정보 발견: {company_name} (ID: {db_company.id})")
                    
                else:
                    # DB에서 찾지 못한 경우
                    company_data = CompanyData(
                        company_name=company_name,
                        company_classification=None,
                        homepage=None,
                        logo_url=None,
                        intro_summary=None,
                        intro_detail=None,
                        main_business=None,
                    )
                    
                    data_source = "user_input"
                    
                    # 검색 실패 추적 정보
                    data_source_tracking.update({
                        "db_record_found": False,
                        "data_completeness_score": 10.0,  # 회사명만 있음
                        "reliability_indicators": {
                            "database_source": False,
                            "user_provided_only": True,
                            "verification_needed": True,
                            "potential_hallucination_risk": True
                        }
                    })
                    
                    data_source_tracking["verification_flags"].extend([
                        "no_database_match",
                        "company_name_only",
                        "high_hallucination_risk"
                    ])

                    logger.info(f"DB에 기업 정보 없음: {company_name}")
                    
            except DatabaseError as e:
                # DB 오류 시 사용자 입력으로 폴백
                logger.warning(f"DB 검색 실패: {e}")
                
                company_data = CompanyData(
                    company_name=company_name,
                    company_classification=None,
                    homepage=None,
                    logo_url=None,
                    intro_summary=None,
                    intro_detail=None,
                    main_business=None,
                )
                
                data_source = "user_input_fallback"
                
                # DB 오류 추적 정보
                data_source_tracking.update({
                    "database_error": str(e),
                    "fallback_used": True,
                    "data_completeness_score": 5.0,
                    "reliability_indicators": {
                        "database_source": False,
                        "database_error": True,
                        "fallback_mode": True,
                        "high_uncertainty": True
                    }
                })
                
                data_source_tracking["verification_flags"].extend([
                    "database_error",
                    "fallback_data_only",
                    "critical_verification_needed"
                ])
        
        # 상태에 기업 데이터와 추적 정보 저장
        state["company_data"] = company_data
        state["data_source_tracking"] = data_source_tracking
    
        
        logger.info(f"기업 데이터 검색 완료 (추적 정보 포함): {company_name}")
        
    except Exception as e:
        error_msg = f"기업 데이터 검색 실패: {str(e)}"
        logger.error(error_msg)
        
        state.setdefault("errors", []).append(error_msg)
        state["current_step"] = "error"
        state["status"] = "error"
        # 에러 상황도 추적
        state["data_source_tracking"] = {
            "error": str(e),
            "reliability_indicators": {"critical_error": True},
            "verification_flags": ["critical_error", "no_data_available"]
        }
        
    return state


def structure_input(state: WorkflowState) -> WorkflowState:
    """
    3단계: 입력 데이터 구조화 및 검증
    
    사용자 입력과 검색된 기업 데이터를 결합하여
    LLM 생성에 최적화된 구조화된 형태로 변환합니다.
    """
    logger.info(f"워크플로우 {state['workflow_id']}: 입력 구조화 시작")
    
    try:
        # 현재 단계 업데이트
        state["current_step"] = "structure_input"
        state["status"] = "running"
        state["step_count"] = state.get("step_count", 0) + 1
        state["last_updated"] = datetime.now()
        
        user_input = state.get("user_input")
        company_data = state.get("company_data")
        
        if not user_input or not company_data:
            raise WorkflowError("사용자 입력 또는 기업 데이터가 없습니다")
        
        # 구조화된 입력 데이터 생성
        structured_data = {
            "job_title": user_input.job_title,
            "company_info": {
                "company_name": company_data.company_name,
                "company_classification": company_data.company_classification,
                "homepage": company_data.homepage,
                "logo_url": company_data.logo_url,
                "intro_summary": company_data.intro_summary,
                "intro_detail": company_data.intro_detail,
                "main_business": company_data.main_business,
            },
            "requirements": {
                "essential": user_input.requirements,
                "preferred": user_input.preferred_qualifications,
            },
            "job_details": {
                "type": user_input.job_type.value,
                "experience_level": user_input.experience_level.value,
                "salary": user_input.salary_info.model_dump() if user_input.salary_info else None,
                "location": user_input.work_location.model_dump() if user_input.work_location else None,
            },
            "additional_info": user_input.additional_info,
        }
        
        state["structured_input"] = structured_data
        
        # 기본 검증 수행
        validation_results = []
        
        # 필수 필드 검증
        if not user_input.job_title.strip():
            validation_results.append(ValidationResult(
                status=ValidationStatus.FAILED,
                score=0,
                issues=["채용 직무명이 비어있습니다"],
                suggestions=["구체적인 직무명을 입력해주세요"],
                validator_type="required_field_validator"
            ))
        
        if not user_input.requirements:
            validation_results.append(ValidationResult(
                status=ValidationStatus.FAILED, 
                score=0,
                issues=["필수 요구사항이 없습니다"],
                suggestions=["최소 1개 이상의 요구사항을 입력해주세요"],
                validator_type="required_field_validator"
            ))
            
        if not validation_results:
            validation_results.append(ValidationResult(
                status=ValidationStatus.PASSED,
                score=100,
                issues=[],
                suggestions=[],
                validator_type="basic_validator"
            ))
            
        state["validation_results"] = validation_results
        
        logger.info("입력 데이터 구조화 완료")
        
    except Exception as e:
        error_msg = f"입력 구조화 실패: {str(e)}"
        logger.error(error_msg)
        
        state.setdefault("errors", []).append(error_msg)
        state["current_step"] = "error"
        state["status"] = "error"
    return state


def generate_draft(state: WorkflowState) -> WorkflowState:
    """
    4단계: LLM을 통한 채용공고 초안 생성
    
    구조화된 입력 데이터를 바탕으로 LLM을 호출하여
    완성된 채용공고 초안을 생성합니다.
    """
    logger.info(f"워크플로우 {state['workflow_id']}: 채용공고 초안 생성 시작")
    
    try:
        # 현재 단계 업데이트
        state["current_step"] = "generate_draft"
        state["status"] = "running"
        state["step_count"] = state.get("step_count", 0) + 1
        state["last_updated"] = datetime.now()
        
        # 필요한 데이터 확인
        structured_input = state.get("structured_input")
        validation_results = state.get("validation_results", [])
        
        if not structured_input:
            raise WorkflowError("구조화된 입력이 없습니다")
            
        # 검증 실패시 처리
        failed_validations = [v for v in validation_results if v.status == ValidationStatus.FAILED]
        if failed_validations:
            logger.warning(f"입력 검증 경고: {', '.join([validation.issues for validation in failed_validations])}")
            # 경고만 하고 계속 진행 (완전 실패가 아닌 경우)
        
        # 채용공고 생성기를 사용한 실제 LLM 생성
        generator = get_job_posting_generator()
        
        generation_context = GenerationContext(
            structured_input=structured_input or {},
            generation_metadata={
                "workflow_id": state["workflow_id"],
                "generation_step": "generate_draft",
                "timestamp": datetime.now(),
                "data_source_tracking": state.get("data_source_tracking", {}),
            }
        )
        
        # LLM을 통한 채용공고 생성
        result = generator.generate_job_posting(generation_context)
        if not result or not isinstance(result, tuple) or len(result) != 2:
            raise WorkflowError(f"채용공고 생성 에이전트 호출 결과 형식이 tuple이 아닙니다: {type(result)}")
        
        job_posting, metadata = result
        
        state["job_posting_draft"] = job_posting
        state["draft_metadata"] = metadata
        
        logger.info("LLM 기반 채용공고 초안 생성 완료")
        
    
    except Exception as e:
        error_msg = f"채용공고 생성 실패: {str(e)}"
        logger.error(error_msg)
        
        state.setdefault("errors", []).append(error_msg)
        state["current_step"] = "error"
        state["status"] = "error"
    return state

def call_hallucination_validation_agent(state: WorkflowState) -> WorkflowState:
    """
    5단계: 환각 검증 에이전트 호출
    
    생성된 채용공고 초안을 바탕으로 환각 검증 에이전트를 호출하여 검증 결과를 반환합니다.
    """
    logger.info(f"워크플로우 {state['workflow_id']}: 환각 검증 에이전트 호출 시작")

    try:
        # 현재 단계 업데이트
        state["current_step"] = "call_hallucination_validation_agent"
        state["status"] = "running"
        state["step_count"] = state.get("step_count", 0) + 1
        state["last_updated"] = datetime.now()

        # 생성된 채용공고 초안 확인
        job_posting_draft = state.get("job_posting_draft")
        structured_input = state.get("structured_input")
        if not job_posting_draft:
            raise WorkflowError("생성된 채용공고 초안이 없습니다")

        thread_id = state["workflow_id"] + "_HV"

        result = analyze_intrinsic_consistency_with_agent(
            HallucinationValidationRequest(job_posting_draft=job_posting_draft,
                                           structured_input=structured_input),
            thread_id
            )
        if not result or not isinstance(result, tuple) or len(result) != 2:
            raise WorkflowError(f"환각 검증 에이전트 호출 결과 형식이 tuple이 아닙니다: {type(result)}")
        
        validated_job_posting, metadata = result
        

        # 상태에 검증된 채용공고 초안 저장
        state["job_posting_draft"] = validated_job_posting
        state["hallucination_validation_metadata"] = metadata
        state["status"] = "completed"
        
    except Exception as e:
        error_msg = f"환각 검증 에이전트 호출 중 예상치 못한 오류: {str(e)}"
        logger.error(error_msg)
        
        state.setdefault("errors", []).append(error_msg)
        state["current_step"] = "error"
        state["status"] = "error"
    return state

class JobPostingWorkflow:
    """
    채용공고 생성 LangGraph 워크플로우 관리 클래스
    
    워크플로우 생성, 컴파일, 실행을 담당합니다.
    """
    
    def __init__(self, checkpointer: MemorySaver = None):
        """워크플로우 초기화"""
        self.graph = None
        self.compiled_workflow = None
        self.checkpointer = checkpointer if checkpointer else MemorySaver()
        self._build_graph()
        
    def _build_graph(self) -> None:
        """워크플로우 그래프 구성 (검증 에이전트 포함)"""
        logger.info("LangGraph 워크플로우 구성 시작")
        
        # StateGraph 생성
        self.graph = StateGraph(WorkflowState)
        
        # 기본 노드들 추가
        self.graph.add_node("structure_natural_language_input", structure_natural_language_input)
        self.graph.add_node("retrieve_company_data", retrieve_company_data)
        self.graph.add_node("structure_input", structure_input)
        self.graph.add_node("generate_draft", generate_draft)
        
        # 검증 에이전트 노드 추가
        self.graph.add_node("call_sensitivity_validation_agent", call_sensitivity_validation_agent)
        self.graph.add_node("call_hallucination_validation_agent", call_hallucination_validation_agent)
        
        # 기본 선형 엣지 연결
        self.graph.add_edge(START, "structure_natural_language_input")
        self.graph.add_edge("structure_natural_language_input", "call_sensitivity_validation_agent")
        self.graph.add_edge("call_sensitivity_validation_agent", "retrieve_company_data")
        self.graph.add_edge("retrieve_company_data", "structure_input")
        self.graph.add_edge("structure_input", "generate_draft")
        self.graph.add_edge("generate_draft", "call_hallucination_validation_agent")
        self.graph.add_edge("call_hallucination_validation_agent", END)
        
        logger.info("LangGraph 워크플로우 구성 완료 (6단계: 자연어 구조화 -> 민감성 검증 -> 기업 검색 -> 입력 구조화 -> 채용공고 생성 -> 환각 검증)")
    
    def compile(self) -> None:
        """워크플로우 컴파일"""
        if not self.graph:
            raise WorkflowError("그래프가 구성되지 않았습니다")
            
        logger.info("워크플로우 컴파일 시작")
        
        # 체크포인터 없이 컴파일 (Pydantic 모델 직렬화 문제 회피)
        self.compiled_workflow = self.graph.compile(
            debug=False, # True 시 노드마다 상태값 출력
            checkpointer=self.checkpointer, # 체크포인터 설정 (메모리 기반)
        )
        
        logger.info("워크플로우 컴파일 완료")
    
    def run(self, 
           raw_input: str = None, 
           user_input: UserInput = None, 
           workflow_id: str = None) -> Dict[str, Any]:
        """
        워크플로우 실행 (자연어 입력 또는 구조화된 입력 지원)
        
        Args:
            raw_input: 자연어 입력 (우선순위 높음)
            user_input: 구조화된 사용자 입력 (raw_input이 없을 때 사용)
            workflow_id: 워크플로우 고유 ID (선택사항)
            
        Returns:
            실행 결과 상태
            
        Note:
            raw_input과 user_input 중 하나는 반드시 제공해야 함
        """
        if not raw_input and not user_input:
            raise WorkflowError("자연어 입력 또는 구조화된 사용자 입력 중 하나는 반드시 제공해야 합니다")
            
        if not self.compiled_workflow:
            self.compile()
            
        if not workflow_id:
            workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        logger.info(f"워크플로우 실행 시작: {workflow_id}")
        
        # 초기 상태 설정
        initial_state: WorkflowState = {
            "raw_input": raw_input,
            "user_input": user_input,
            "workflow_id": workflow_id,
            "current_step": "initialized",
            "step_count": 0,
            "start_time": datetime.now(),
            "last_updated": datetime.now(),
            "errors": [],
            "warnings": [],
            "validation_results": [],
        }
        
        try:
            # 워크플로우 실행
            logger.info(f"입력 타입: {'자연어' if raw_input else '구조화된 데이터'}")
            
            # 스트리밍 실행으로 단계별 진행 상황 추적
            final_state = None
            for state in self.compiled_workflow.stream(initial_state, config={"configurable": {"thread_id": workflow_id}}):
                current_step = list(state.keys())[0]
                logger.info(f"단계 완료: {current_step}")
                final_state = state.get(current_step, None)
                
            if not final_state:
                raise WorkflowError("워크플로우 실행 결과를 받지 못했습니다")
            logger.info(f"워크플로우 실행 결과: {final_state}")
            # 실행 결과 요약 로깅
            if final_state.get("job_posting_draft"):
                draft = final_state["job_posting_draft"]
                logger.info(f"워크플로우 실행 완료: {workflow_id}")
                logger.info(f"생성된 채용공고: {draft.title}")
                logger.info(f"회사명: {draft.company_name}")
                logger.info(f"생성 방법: {final_state['draft_metadata']['generated_by']}")
            else:
                logger.warning(f"워크플로우 실행 완료되었지만 채용공고가 생성되지 않음: {workflow_id}")
                
            return final_state
            
        except Exception as e:
            error_msg = f"워크플로우 실행 실패: {str(e)}"
            logger.error(error_msg)
            raise WorkflowError(error_msg)
        
    def get_workflow_state(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """워크플로우 상태 조회 """
        saved_state = self.checkpointer.get(config={"configurable": {"thread_id": workflow_id}})
        if saved_state:
            return saved_state
        
            
class CompanyRetrievalWorkflow(JobPostingWorkflow):
    """기업의 데이터 검색 단계까지 진행하는 워크플로우 입니다.
    """
    def __init__(self):
        super().__init__()
        self.graph = None
        self.compiled_workflow = None
        self.checkpointer = MemorySaver()
        self._build_graph()
        
    def _build_graph(self) -> None:
        """워크플로우 그래프 구성 (기업 데이터 검색 단계까지 진행)"""
        logger.info("LangGraph 워크플로우 구성 시작")
        
        # StateGraph 생성
        self.graph = StateGraph(WorkflowState)
        
        # 기본 노드들 추가
        self.graph.add_node("structure_natural_language_input", structure_natural_language_input)
        self.graph.add_node("retrieve_company_data", retrieve_company_data)
        
        # 기본 선형 엣지 연결
        self.graph.add_edge(START, "structure_natural_language_input")
        self.graph.add_edge("structure_natural_language_input", "retrieve_company_data")
        self.graph.add_edge("retrieve_company_data", END)
  
    def run(self,  
           user_input: UserInput = None, 
           workflow_id: str = None) -> Dict[str, Any]:
        """
        워크플로우 실행 (구조화된 입력만만 지원)
        """
        if not user_input:
            raise WorkflowError("구조화된 사용자 입력 중 하나는 반드시 제공해야 합니다")
            
        if not self.compiled_workflow:
            self.compile()
            
        if not workflow_id:
            workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        logger.info(f"워크플로우 실행 시작: {workflow_id}")
        
        # 초기 상태 설정
        initial_state: WorkflowState = {
            "user_input": user_input,
            "workflow_id": workflow_id,
            "current_step": "initialized",
            "step_count": 0,
            "start_time": datetime.now(),
            "last_updated": datetime.now(),
            "errors": [],
            "warnings": [],
            "validation_results": [],
        }
        
        try:
            # 워크플로우 실행
            logger.info(f"입력 타입: {'구조화된 데이터'}")
            
            # 스트리밍 실행으로 단계별 진행 상황 추적
            final_state = None
            for state in self.compiled_workflow.stream(initial_state, config={"configurable": {"thread_id": workflow_id}}):
                current_step = list(state.keys())[0]
                logger.info(f"단계 완료: {current_step}")
                final_state = state.get(current_step, None)
                
            if not final_state:
                raise WorkflowError("워크플로우 실행 결과를 받지 못했습니다")
            logger.info(f"워크플로우 실행 결과: {final_state}")
            # 실행 결과 요약 로깅
            if final_state.get("company_data"):
                company_data = final_state["company_data"]
                return company_data
            else:
                raise WorkflowError("기업 데이터를 검색하지 못했습니다")
            
        except Exception as e:
            error_msg = f"워크플로우 실행 실패: {str(e)}"
            logger.error(error_msg)
            raise WorkflowError(error_msg)
        

# 전역 워크플로우 인스턴스 (싱글톤 패턴)
_workflow_instance = None

def get_workflow(checkpointer: MemorySaver = None) -> JobPostingWorkflow:
    """워크플로우 인스턴스 반환 (싱글톤)"""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = JobPostingWorkflow(checkpointer)
        _workflow_instance.compile()
    return _workflow_instance

_company_retrieval_workflow_instance = None

def get_company_retrieval_workflow() -> CompanyRetrievalWorkflow:
    """기업 데이터 검색 워크플로우 인스턴스 반환 (싱글톤)"""
    global _company_retrieval_workflow_instance
    if _company_retrieval_workflow_instance is None:
        _company_retrieval_workflow_instance = CompanyRetrievalWorkflow()
        _company_retrieval_workflow_instance.compile()
    return _company_retrieval_workflow_instance