"""
환각 검증 에이전트

이 모듈은 LLM이 생성한 채용공고 초안에서 환각 현상(hallucination)을 검증하는
LangGraph 기반 에이전트를 구현합니다.

검증 유형:
1. Intrinsic 검증: 생성된 내용 내부의 논리적 일관성 검사
2. Extrinsic 검증: 기업 데이터와의 일치성 검사
"""

import logging
import json
from typing import Dict, Any, List, Literal, Optional, Tuple
from datetime import datetime
import time

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.types import Command, interrupt
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain.chat_models import init_chat_model

from ..models.job_posting import JobPostingDraft
from ..exceptions import ValidationError
from config.settings import settings

logger = logging.getLogger(__name__)


class HallucinationValidationRequest(BaseModel):
    """환각 검증 요청 모델"""
    job_posting_draft: JobPostingDraft = Field(..., description="검증할 채용공고 초안")
    structured_input: Dict[str, Any] = Field(..., description="구조화된 입력 데이터")

class IntrinsicAnalysisResult(BaseModel):
    """내재적 일관성 분석 결과"""
    job_posting_draft: Optional[JobPostingDraft] = Field(description="검증 기준에 따라서 수정된 채용공고 초안, 개선 사항이 없다면 None 입력")
    reasoning: str = Field(description="수정 결과에 대한 논리적인 이유")
# class IntrinsicAnalysisResult(BaseModel):
#     """내재적 일관성 분석 결과"""
#     logical_contradictions: Optional[List[str]] = Field(description="논리적 모순들, 없다면 빈 리스트 입력")
#     factual_inconsistencies: Optional[List[str]] = Field(description="사실 불일치들, 없다면 빈 리스트 입력")
#     unsupported_claims: Optional[List[str]] = Field(description="근거 없는 주장들, 없다면 빈 리스트 입력")
#     suggestions: Optional[List[str]] = Field(description="수정 제안, 없다면 빈 리스트 입력")
#     requires_regeneration: bool = Field(description="재생성 필요 여부, 문제가 없다면 False, 재생성 필요하다면 True")


def create_intrinsic_validation_prompt(job_posting: JobPostingDraft, user_input: Dict[str, Any]) -> Tuple[str, str]:
    """내재적 검증을 위한 프롬프트 생성"""
    
    system_prompt = f"""당신은 채용공고의 내재적 일관성을 검증한 뒤, 올바른 채용 공고로 첨삭하는 전문가입니다.
사용자가 제시할 참조 정보 내용을 기반으로 채용공고 내용을 분석하여 논리적 모순, 사실 불일치, 근거 없는 주장이 있는지 검사하고 채용 공고를 수정해주세요.
사용자가 제시한 참조 정보에는 채용 정보와 기업 정보가 포함되어 있습니다.

**검증 대상 채용공고**:
    
제목: {job_posting.title}
회사명: {job_posting.company_name}
직무 설명: {job_posting.job_description}
필수 요구사항: {', '.join(job_posting.requirements or [])}
우대 사항: {', '.join(job_posting.preferred_qualifications or [])}
채용 형태: {job_posting.job_type}
경력 수준: {job_posting.experience_level}
급여 정보: {job_posting.salary_info.model_dump() if job_posting.salary_info else 'N/A'}
근무 위치: {job_posting.work_location.model_dump() if job_posting.work_location else 'N/A'}
복리후생: {', '.join(job_posting.benefits or [])}
지원 마감일: {job_posting.application_deadline}
담당자 연락처: {job_posting.contact_email}

**검증 기준**:
1. **논리적 모순**: 채용공고 내에서 상충하는 정보나 논리적으로 맞지 않는 내용
2. **사실 불일치**: 사용자가 제시한 참조 정보와 내용이 다르거나 현실적이지 않은 내용
3. **근거 없는 주장**: 구체적 근거나 설명 없이 과장된 표현이나 주장

**ReAct Guideline**:
- 전체 후보들: 채용 공고 중 검증 기준에 어긋나는 텍스트들
- 분석: 각 후보들이 검증 기준에 어긋나는지 아닌 지 그 이유
- 대안: 각 후보별로 이들을 대체할 수 있는 대안, 검증 기준에 어긋나지 않는다면 생략, 적절한 대안이 없다면 '대안 없음' 명시
- 대안 제시 이유: 각 대안 별로 해당 대안이 제시된 이유

**참고사항**:
- generate_structured_response 단계에서 사용하여 채용 공고를 수정해주세요.
- 채용 공고를 수정할 때 '대안 없음'이 명시되어 있다면, 해당 필드는 비워도 됩니다.
"""

    user_prompt = f"""**참조 정보**:
{json.dumps(user_input, ensure_ascii=False, indent=2)}
"""
    
    return system_prompt, user_prompt


def analyze_intrinsic_consistency_with_agent(request: HallucinationValidationRequest, thread_id: str) -> Tuple[JobPostingDraft, Dict[str, Any]]:
    """내재적 일관성 분석"""
    start_time = time.time()
    job_posting = request.job_posting_draft
    user_input = request.structured_input
    try:
        model = "gpt-4o-mini"  # 테스트용으로 더 안정적인 모델 사용
        llm = init_chat_model(
                model=model,
                model_provider="openai",
                temperature=1 if model == "o3" or model == "o4-mini" or "gpt-5" in model else 0.0,
            )
        system_prompt, user_prompt = create_intrinsic_validation_prompt(job_posting, user_input)
        
        memory = MemorySaver()
        agent_executor = create_react_agent(model=llm,
                                            prompt=system_prompt,
                                            tools=[],
                                            response_format=IntrinsicAnalysisResult,
                                            checkpointer=memory,
                                            name="hallucination_validation_agent")
        config = {"configurable": {"thread_id": thread_id}}
        
        response = agent_executor.invoke({"messages": [{"role": "user", "content": user_prompt}]},
                                        config=config,
                                        stream_mode="values")
        structured_response = response.get("structured_response", None)
        metadata = {"thread_id": thread_id, "generated_by": model, "generation_time": time.time() - start_time, "reasoning": structured_response.reasoning}
        
        if structured_response is None:
            raise ValidationError("환각 검증 결과를 받지 못했습니다")
        job_posting_draft = structured_response.job_posting_draft
        if job_posting_draft is None:
            return job_posting, metadata
        
        logger.info(f"환각 검증 완료")
        return job_posting_draft, metadata
        
    except Exception as e:
        logger.error(f"내재적 분석 실패: {str(e)}")
        metadata = {"error": str(e), "generation_time": time.time() - start_time, "reasoning": "환각 검증 실패"}
        # 입력된 JobPostingDraft 반환 (보수적 접근)
        return job_posting, metadata

# def call_hallucination_validation_agent(state: ValidationAgentState) -> Command[Literal["route_decision", "__end__"]]:
#     """
#     환각 검증 에이전트 노드
    
#     채용공고 초안을 분석하여 환각 현상을 감지하고,
#     결과에 따라 다음 액션을 결정합니다.
#     """
#     logger.info(f"환각 검증 에이전트 시작: {state.workflow_id}")
    
#     try:
#         # 검증 시도 횟수 증가
#         state.increment_attempts()
        
#         # 필요 데이터 확인
#         if not state.job_posting_draft or not state.company_data:
#             error_msg = "환각 검증을 위한 채용공고 초안 또는 기업 데이터가 없습니다"
#             logger.error(error_msg)
#             return Command(
#                 goto=END,
#                 update={
#                     "agent_decision": ValidationAgentDecision.FAIL,
#                     "feedback_for_user": [error_msg]
#                 }
#             )
        
#         # 기업 데이터 보강 시도
#         tracking_info = state.metadata.get("data_source_tracking", {})
#         enriched_company_data, updated_tracking = enrich_company_data_if_needed(
#             state.company_data, tracking_info
#         )
        
#         # 환각 검증 요청 생성
#         validation_request = HallucinationValidationRequest(
#             job_posting_draft=state.job_posting_draft,
#             company_data=enriched_company_data,
#             data_source_tracking=updated_tracking,
#             validation_scope=["intrinsic", "extrinsic"]
#         )
        
#         # 내재적 일관성 분석
#         logger.info("내재적 일관성 분석 시작")
#         intrinsic_result = analyze_intrinsic_consistency(state.job_posting_draft)
        
#         # 외재적 일치성 분석
#         logger.info("외재적 일치성 분석 시작")
#         extrinsic_result = analyze_extrinsic_alignment(
#             state.job_posting_draft, 
#             enriched_company_data, 
#             updated_tracking
#         )
        
#         # 분석 결과 통합
#         hallucination_result = process_hallucination_analysis(
#             intrinsic_result, extrinsic_result, validation_request
#         )
        
#         # 결정 로직
#         if hallucination_result.has_hallucination:
#             if hallucination_result.requires_regeneration:
#                 # 심각한 환각 문제 - 재생성 필요
#                 decision = ValidationAgentDecision.REGENERATE
#                 feedback = [
#                     f"심각한 환각 문제가 감지되었습니다 (내재적: {hallucination_result.intrinsic_score:.2f}, 외재적: {hallucination_result.extrinsic_score:.2f})",
#                     "채용공고 재생성이 필요합니다."
#                 ]
                
#             elif len(hallucination_result.detected_hallucinations) > 5 or state.is_max_attempts_reached():
#                 # 다수의 환각 문제 또는 최대 시도 횟수 도달
#                 decision = ValidationAgentDecision.HUMAN_REVIEW
#                 feedback = ["다수의 환각 문제로 인해 사람의 검토가 필요합니다."]
                
#             else:
#                 # 수정 가능한 환각 문제
#                 decision = ValidationAgentDecision.RETRY_WITH_FEEDBACK
#                 feedback = []
#                 for hallucination in hallucination_result.detected_hallucinations[:3]:  # 상위 3개만
#                     feedback.append(f"환각 문제: {hallucination.explanation}")
#                     feedback.append(f"수정 제안: {hallucination.correction_suggestion}")
                    
#         else:
#             # 환각 문제 없음 - 다음 단계로 진행
#             decision = ValidationAgentDecision.PROCEED
#             feedback = ["환각 검증 통과"]
        
#         logger.info(f"환각 검증 완료: {decision}, 내재적 점수: {hallucination_result.intrinsic_score:.2f}, 외재적 점수: {hallucination_result.extrinsic_score:.2f}")
        
#         return Command(
#             goto="route_decision",
#             update={
#                 "validation_step": "hallucination_completed",
#                 "hallucination_result": hallucination_result,
#                 "agent_decision": decision,
#                 "feedback_for_user": feedback,
#                 "metadata": {**state.metadata, "data_source_tracking": updated_tracking},
#                 "updated_at": datetime.now()
#             }
#         )
        
#     except Exception as e:
#         error_msg = f"환각 검증 중 오류 발생: {str(e)}"
#         logger.error(error_msg, exc_info=True)
        
#         return Command(
#             goto=END,
#             update={
#                 "agent_decision": ValidationAgentDecision.FAIL,
#                 "feedback_for_user": [error_msg],
#                 "updated_at": datetime.now()
#             }
#         )


# def route_hallucination_decision(state: ValidationAgentState) -> Literal["hallucination_validation_agent", "human_review_required", "regenerate_required", "proceed_to_next", "__end__"]:
#     """
#     환각 검증 결과에 따른 라우팅 결정
#     """
#     decision = state.agent_decision
    
#     logger.info(f"환각 검증 라우팅 결정: {decision}")
    
#     if decision == ValidationAgentDecision.PROCEED:
#         return "proceed_to_next"
#     elif decision == ValidationAgentDecision.RETRY_WITH_FEEDBACK:
#         return "human_review_required"  # Human-in-the-Loop으로 이동
#     elif decision == ValidationAgentDecision.REGENERATE:
#         return "regenerate_required"    # 재생성 필요
#     elif decision == ValidationAgentDecision.HUMAN_REVIEW:
#         return "human_review_required"
#     elif decision == ValidationAgentDecision.FAIL:
#         return END
#     else:
#         logger.warning(f"알 수 없는 결정: {decision}, 기본값으로 진행")
#         return "proceed_to_next"


# class HallucinationValidatorWorkflow:
#     """환각 검증 에이전트 워크플로우 관리 클래스"""
    
#     def __init__(self):
#         self.graph = None
#         self.compiled_workflow = None
#         self._build_graph()
    
#     def _build_graph(self):
#         """워크플로우 그래프 구성"""
#         logger.info("환각 검증 워크플로우 구성 시작")
        
#         self.graph = StateGraph(ValidationAgentState)
        
#         # 노드 추가
#         self.graph.add_node("hallucination_validation_agent", hallucination_validation_agent)
#         self.graph.add_node("route_decision", lambda state: state)  # 라우팅 전용 노드
        
#         # 엣지 및 조건부 엣지 추가
#         self.graph.add_edge(START, "hallucination_validation_agent")
#         self.graph.add_conditional_edges(
#             "route_decision",
#             route_hallucination_decision,
#             {
#                 "hallucination_validation_agent": "hallucination_validation_agent",  # 재시도
#                 "human_review_required": END,     # Human-in-the-Loop으로 이동
#                 "regenerate_required": END,       # 재생성 필요
#                 "proceed_to_next": END,           # 다음 검증 단계로
#                 END: END                          # 종료
#             }
#         )
        
#         logger.info("환각 검증 워크플로우 구성 완료")
    
#     def compile(self):
#         """워크플로우 컴파일"""
#         if not self.graph:
#             raise ValidationError("그래프가 구성되지 않았습니다")
        
#         logger.info("환각 검증 워크플로우 컴파일 시작")
#         self.compiled_workflow = self.graph.compile(debug=False)
#         logger.info("환각 검증 워크플로우 컴파일 완료")
    
#     def run(self, job_posting: JobPostingDraft, company_data: CompanyData, 
#             data_tracking: Dict[str, Any], workflow_id: str = None) -> ValidationAgentState:
#         """환각 검증 실행"""
#         if not self.compiled_workflow:
#             self.compile()
        
#         if not workflow_id:
#             workflow_id = f"hallucination_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
#         # 초기 상태 설정
#         initial_state = ValidationAgentState(
#             agent_type="hallucination",
#             workflow_id=workflow_id,
#             validation_step="hallucination_validation",
#             job_posting_draft=job_posting,
#             company_data=company_data,
#             metadata={"data_source_tracking": data_tracking},
#             created_at=datetime.now()
#         )
        
#         logger.info(f"환각 검증 실행 시작: {workflow_id}")
        
#         try:
#             # 워크플로우 실행
#             final_state = None
#             for state in self.compiled_workflow.stream(initial_state):
#                 final_state = list(state.values())[0] if state else None
            
#             if not final_state:
#                 raise ValidationError("워크플로우 실행 결과를 받지 못했습니다")
            
#             logger.info(f"환각 검증 완료: {workflow_id}, 결정: {final_state.agent_decision}")
#             return final_state
            
#         except Exception as e:
#             logger.error(f"환각 검증 실행 실패: {str(e)}")
#             raise ValidationError(f"환각 검증 실행 실패: {str(e)}")


# # 전역 워크플로우 인스턴스 (싱글톤 패턴)
# _hallucination_workflow_instance = None

# def get_hallucination_validator() -> HallucinationValidatorWorkflow:
#     """환각 검증 워크플로우 인스턴스 반환 (싱글톤)"""
#     global _hallucination_workflow_instance
#     if _hallucination_workflow_instance is None:
#         _hallucination_workflow_instance = HallucinationValidatorWorkflow()
#         _hallucination_workflow_instance.compile()
#     return _hallucination_workflow_instance
