"""
환각 검증 에이전트

이 모듈은 LLM이 생성한 채용공고 초안에서 환각 현상(hallucination)을 검증하는
LangGraph 기반 에이전트를 구현합니다.

검증 유형:
1. Intrinsic 검증: 생성된 내용 내부의 논리적 일관성 검사
2. Extrinsic 검증: 기업 데이터와의 일치성 검사
"""

import logging
import uuid
import requests
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
API_BASE_URL = f"http://{settings.api.host}:{settings.api.port}/api/v1" # 요청 엔드포인트가 컨테이너 내부에 있으므로 localhost가 들어가도 된다.

class HallucinationValidationRequest(BaseModel):
    """환각 검증 요청 모델"""
    job_posting_draft: JobPostingDraft = Field(..., description="검증할 채용공고 초안")
    structured_input: Dict[str, Any] = Field(..., description="구조화된 입력 데이터")

class ProcessedResult(BaseModel):
    """채용 공고내 환각 현상 탐지 및 제거 결과"""
    job_posting_draft: Optional[JobPostingDraft] = Field(description="가이드라인에 따라서 수정된 채용공고 초안, 개선 사항이 없다면 None 입력")
    reasoning: str = Field(description="수정 결과에 대한 근거")


def create_intrinsic_validation_prompt(job_posting: JobPostingDraft, user_input: Dict[str, Any]) -> Tuple[str, str]:
    """내재적 검증을 위한 프롬프트 생성"""
    
    system_prompt = f"""당신은 채용공고내 환각 현상을 탐지하고 제거하는 전문가입니다. 오직 환각 현상과 관련된 부분들만 첨삭하시오.
환각 현상에는 내재적 환각, 외재적 환각 두 종류가 있습니다.
내재적 환각은 채용 정보 및 기업 정보와 논리적으로 모순이 있거나 사실 불일치가 있는 환각을 의미합니다. 이 경우 채용공고를 바로 수정해주세요.
외재적 환각은 채용 정보 및 기업 정보로 모순이나 사실 불일치를 확인할 수 없는 환각을 의미합니다. 이 경우 주어진 tool을 사용하세요.
사용자가 제시한 참조 정보에는 채용 정보와 기업 정보가 포함되어 있습니다.

**tools**:
- get_human_feedback:  외재적 환각이 있는 경우에만 사용하며, 한번에 여러 외재적 환각에 대한 human feedback들을 얻기 위한 도구

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

**내재적 환각 검증 기준**:
1. **논리적 모순**: 채용공고 내에서 상충하는 정보나 논리적으로 맞지 않는 내용
2. **사실 불일치**: 사용자가 제시한 참조 정보와 내용이 다르거나 현실적이지 않은 내용
3. **근거 없는 주장**: 구체적 근거나 설명 없이 과장된 표현이나 주장
**외재적 환각 검증 기준**:
- 채용 정보 및 기업 정보로 모순이나 사실 불일치를 확인할 수 없는 내용

**ReAct Guideline**:
내재적 환각:
- 내재적 환각 후보들: 채용 공고 내에서 검증 기준에 어긋나는 텍스트들
- 분석: 각 내재적 환각 후보들이 어떤 기준에 속하는지 분류
- 대안: 각 내재적 환각 후보별로 이들을 대체할 수 있는 대안 제시, 검증 기준에 어긋나지 않는다면 생략, 적절한 대안이 없다면 '대안 없음' 명시
- 대안 제시 이유: 각 내재적 환각 후보별로 해당 대안이 제시된 이유를 간단히 작성
외재적 환각:
- 외재적 환각 후보들: 채용 정보 및 기업 정보로 모순이나 사실 불일치를 확인할 수 없는 모든 텍스트들
- Action: get_human_feedback tool을 사용하여 human feedback 얻기 

**참고사항**:
- Do not call tool parallelly.
- 외재적 환각의 경우 한번에 여러 후보들에 대해서 get_human_feedback tool을 사용하여 human feedback을 얻어주세요.
- generate_structured_response 단계에서 사용하여 채용 공고를 수정해주세요.
- 채용 공고를 수정할 때 '대안 없음'이 명시되어 있다면, 해당 필드는 비워도 됩니다.
"""

    user_prompt = f"""**참조 정보**:
{json.dumps(user_input, ensure_ascii=False, indent=2)}
"""
    
    return system_prompt, user_prompt


@tool(response_format="content")
def get_human_feedback(question: List[str]) -> Dict[str, Any]:
    """외재적 환각이 있는 경우 이후 어떻게 할지 human feedback을 얻기 위한 도구 입니다.
    각 내용에 대한 설명과 적용 여부에 대한 질문을 제시하면 사용자는 해당 내용을 어떻게 할지에 대한 답변을 제시합니다.

    Args:
        question (List[str]): 외재적 환각이 있는 내용에 대한 간단한 설명과 적용 여부에 대한 질문들

    Returns:
        Dict[str, Any]: 해당 내용을 어떻게 할지에 대한 human feedback
    """
    value = interrupt({"question": question})  # 중단하고 인간 입력 기다림
    return {"human_feedback": value}

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
                                            tools=[get_human_feedback],
                                            response_format=ProcessedResult,
                                            checkpointer=memory,
                                            name="hallucination_validation_agent")
        config = {"configurable": {"thread_id": thread_id}}
        
        response = agent_executor.invoke({"messages": [{"role": "user", "content": user_prompt}]},
                                        config=config,
                                        interrupt_after=["tools"],
                                        stream_mode="values")
        
        if "structured_response" in response:
            structured_response = response["structured_response"]
            metadata = {"thread_id": thread_id, "generated_by": model, "generation_time": time.time() - start_time, "reasoning": structured_response.reasoning}
        
            if structured_response is None:
                raise ValidationError("환각 검증 결과를 받지 못했습니다")
            job_posting_draft = structured_response.job_posting_draft
            if job_posting_draft is None:
                return job_posting, metadata
        
            logger.info(f"환각 검증 완료")
            return job_posting_draft, metadata
        logger.info(f"환각 검증 중간 결과: {response}")
        
        cnt = 0
        while "structured_response" not in response:
            cnt += 1
            questions = response['__interrupt__'][0].value['question']
            
            # API를 통한 Human-in-the-Loop 피드백 처리
            human_feedbacks = get_human_feedback_via_api(questions, thread_id)
            
            qa_pairs = [f"Q.{q}\nA.{hf}" for q, hf in zip(questions, human_feedbacks)]
            response = agent_executor.invoke(Command(resume='\n\n'.join(qa_pairs)), config=config)
            if cnt > 5:
                break
            
            structured_response = response.get("structured_response", None)
            if structured_response is None:
                raise ValidationError("환각 검증 결과를 받지 못했습니다")
            
            metadata = {"thread_id": thread_id, "generated_by": model, "generation_time": time.time() - start_time, "reasoning": structured_response.reasoning}
            validated_job_posting = structured_response.job_posting_draft
            if validated_job_posting is None:
                return job_posting, metadata
            
            return validated_job_posting, metadata
        
    except Exception as e:
        logger.error(f"내재적 분석 실패: {str(e)}")
        metadata = {"error": str(e), "generation_time": time.time() - start_time, "reasoning": "환각 검증 실패"}
        # 입력된 JobPostingDraft 반환 (보수적 접근)
        return job_posting, metadata
    
def get_human_feedback_via_api(questions: List[str], thread_id: str) -> List[str]:
    """
    API를 통한 Human-in-the-Loop 피드백 처리
    
    Args:
        questions: 사용자에게 물어볼 질문들
        thread_id: 워크플로우 thread ID
        
    Returns:
        사용자가 제공한 답변들
    """
    try:
        # 1. 피드백 세션 생성
        logger.info(f"Creating feedback session for thread: {thread_id}")
        logger.info(f"API_BASE_URL: {API_BASE_URL}")
        
        session_response = requests.post(
            f"{API_BASE_URL}/feedback/sessions",
            json={
                "session_type": "hallucination_detected",
                "template_id": str(uuid.uuid4()),
                "feedback_request": {
                    "questions": questions,
                    "thread_id": thread_id,
                }
            },
            timeout=30
        )
        
        if session_response.status_code != 200:
            raise ValidationError(f"피드백 세션 생성 실패: {session_response.text}")
        
        session_data = session_response.json()
        session_id = session_data["session_id"]
        
        logger.info(f"Feedback session created: {session_id}")
        
        # 2. 사용자 응답 대기 (polling)
        max_wait_time = settings.human_loop.session_timeout
        poll_interval = 2  # 2초마다 체크
        waited_time = 0
        
        while waited_time < max_wait_time:
            logger.info(f"Waiting for user feedback... ({waited_time}s/{max_wait_time}s)")
            
            status_response = requests.get(
                f"{API_BASE_URL}/feedback/sessions/{session_id}",
                timeout=10
            )
            
            if status_response.status_code != 200:
                raise ValidationError(f"피드백 세션 조회 실패: {status_response.text}")
            
            session_status = status_response.json()
            
            if session_status["status"] == "completed":
                # 사용자 피드백 받음
                user_feedback = session_status.get("user_feedback", [])
                

                if not user_feedback:
                    # 구체적인 응답이 없으면 기본 응답 처리
                    user_feedback = ["삭제해주세요"] * len(questions)
                
                logger.info(f"User feedback received: {len(user_feedback)} responses")
                return user_feedback
                
            elif session_status["status"] == "expired":
                raise ValidationError("피드백 세션이 만료되었습니다")
            elif session_status["status"] == "cancelled":
                raise ValidationError("사용자가 피드백 세션을 취소했습니다")
            
            # 계속 대기
            time.sleep(poll_interval)
            waited_time += poll_interval
        
        # 타임아웃 발생
        raise ValidationError(f"피드백 대기 시간 초과 ({max_wait_time}초)")
        
    except requests.RequestException as e:
        logger.error(f"API 요청 실패: {e}")
        # 네트워크 오류 시 기본 응답으로 폴백
        logger.warning("네트워크 오류로 인해 기본 응답으로 진행합니다")
        return ["문제를 수정했습니다"] * len(questions)
        
    except Exception as e:
        logger.error(f"피드백 처리 중 오류: {e}")
        # 기본 응답으로 폴백
        return ["문제를 수정했습니다"] * len(questions)

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
