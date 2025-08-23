"""
민감성 검증 에이전트

이 모듈은 사용자 입력을 분석하여 차별적 표현, 개인정보 요구, 부적절한 내용 등
민감하거나 부적절한 정보를 감지하는 LangGraph 기반 에이전트를 구현합니다.
"""

import logging
import uuid
import json
from typing import Dict, Any, List, Literal, Optional, Annotated
from datetime import datetime

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.types import Command, interrupt
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain.chat_models import init_chat_model

from ..models.job_posting import UserInput
from ..components.llm_client import get_llm_manager
from ..exceptions import ValidationError
from config.settings import settings

logger = logging.getLogger(__name__)


class SensitivityValidationRequest(BaseModel):
    """민감성 검증 요청 모델"""
    user_input: UserInput = Field(description="검증할 구조화된 사용자 입력 텍스트")

def create_sensitivity_validation_prompt() -> str:
    """민감성 검증을 위한 프롬프트 생성"""
    
    prompt = f"""당신은 채용공고 생성을 위한 사용자 입력을 검증하는 전문가입니다.
사용자의 입력에서 민감하거나 부적절한 내용을 감지하고 분석한 뒤 human feedback에 기반하여 수정 해주세요.

**tools**:
- get_human_feedback: 민감하거나 부적절한 내용이 있는 경우 해당 내용을 어떻게 할지 human feedback을 얻기 위한 도구

**검증 기준**:
1. **차별적 표현**: 성별, 나이, 종교, 인종, 출신지역, 외모 등에 대한 차별적 언급
2. **개인정보 요구**: 불필요한 개인정보 요구 (주민등록번호, 가족사항 등)
3. **부적절한 내용**: 성적, 폭력적, 혐오적 표현
4. **편향적 요구사항**: 특정 집단을 배제하는 조건들
5. **사생활 침해**: 사적 정보나 개인적 상황에 대한 부적절한 질문
6. **불법적 요구**: 법적으로 문제가 될 수 있는 조건이나 요구사항

**ReAct 가이드라인**:
- 전체 후보들: 사용자의 입력 중 문제가 될 수도 있는 텍스트
- 현재 관찰 중인 후보: 전체 후보들 중 현재 관찰 중인 후보
- 분석: 현재 관찰 중인 후보가 문제인지 아닌 지 그 이유
- Thought: you should always think about what to do
- Action: the action to take
- Action Input: the input to the action (write in korean)
- Observation: the result of the action
- ... (this Thought/Action/Action Input/Observation can repeat N times)

**주의사항**:
- Do not call tool parallelly.
"""

    return prompt

@tool(response_format="content")
def get_human_feedback(question: List[str]) -> str:
    """민감하거나 부적절한 내용이 있는 경우 이후 어떻게 할지 human feedback을 얻기 위한 도구 입니다.
    각 내용에 대해서 설명하고 수정 예시를 제시해주세요.

    Args:
        question (List[str]): 민감하거나 부적절한 내용에 대한 설명과 수정 제안

    Returns:
        str: 해당 내용을 어떻게 할지에 대한 human feedback
    """
    value = interrupt({"question": question})  # 중단하고 인간 입력 기다림
    return {"human_feedback": value}

def analyze_sensitivity_with_agent(request: SensitivityValidationRequest, thread_id: str) -> tuple[UserInput, dict]:
    """Agent을 사용하여 민감성 분석 후 human feedback에 기반하여 첨삭"""
    try:
        model = "gpt-4o-mini"  # 테스트용으로 더 안정적인 모델 사용
        llm = init_chat_model(
                model=model,
                model_provider="openai",
                temperature=1 if model == "o3" or model == "o4-mini" or "gpt-5" in model else 0.0,
            )
        system_prompt = SystemMessage(content=create_sensitivity_validation_prompt())
        memory = MemorySaver()
        agent_executor = create_react_agent(model=llm,
                                            prompt=system_prompt,
                                            tools=[get_human_feedback],
                                            response_format=UserInput,
                                            checkpointer=memory,
                                            name="sensitivity_validation_agent")
        metadata = {"thread_id": thread_id, "generated_by": model}
        # 한글 유지하면서 JSON 변환 (ensure_ascii=False)
        user_input_text = json.dumps(request.user_input.model_dump(), ensure_ascii=False, indent=2)
        config = {"configurable": {"thread_id": thread_id}}
        
        response = agent_executor.invoke({"messages": [{"role": "user", "content": user_input_text}]},
                                        config=config,
                                        interrupt_after=["tools"],
                                        stream_mode="values")
        cnt = 0
        while "structured_response" not in response:
            cnt += 1
            questions = response['__interrupt__'][0].value['question']
            human_feedbacks = []
            for question in questions:
                human_feedbacks.append(input(f"민감성 오류 발생!\n{question}\n\n 피드백: "))
            qa_pairs = [f"Q.{q}\nA.{hf}" for q, hf in zip(questions, human_feedbacks)]
            response = agent_executor.invoke(Command(resume='\n\n'.join(qa_pairs)), config=config)
            if cnt > 5:
                break
            
            structured_response = response.get("structured_response", None)
            if structured_response is None:
                raise ValidationError("민감성 기반 첨삭 결과를 받지 못했습니다")
            
            return structured_response, metadata
        
    except Exception as e:
        logger.error(f"LLM 민감성 분석 실패: {str(e)}")
        raise ValidationError(f"민감성 분석 중 오류 발생: {str(e)}")

# def call_sensitivity_validation_agent(state: ValidationAgentState) -> Command[Literal["route_decision", "__end__"]]:
#     """
#     민감성 검증 에이전트 노드
    
#     사용자 입력을 분석하여 민감하거나 부적절한 내용을 감지하고,
#     결과에 따라 다음 액션을 결정합니다.
#     """
#     logger.info(f"민감성 검증 에이전트 시작: {state.workflow_id}")
    
#     try:
#         # 검증 시도 횟수 증가
#         state.increment_attempts()
        
#         # 사용자 입력 확인
#         if not state.original_input:
#             error_msg = "민감성 검증을 위한 사용자 입력이 없습니다"
#             logger.error(error_msg)
#             return Command(
#                 goto=END,
#                 update={
#                     "agent_decision": ValidationAgentDecision.FAIL,
#                     "feedback_for_user": [error_msg]
#                 }
#             )
        
#         # 민감성 검증 요청 생성
#         validation_request = SensitivityValidationRequest(
#             user_input=state.original_input,
#             context_metadata=state.metadata,
#             validation_level="standard"  # 기본값, 설정에서 변경 가능
#         )
        
#         # LLM을 통한 민감성 분석
#         logger.info("LLM 기반 민감성 분석 시작")
#         analysis_result = analyze_sensitivity_with_llm(validation_request)
        
#         # 분석 결과 처리
#         sensitivity_result = process_llm_analysis(analysis_result, validation_request)
        
#         # 결정 로직
#         if sensitivity_result.is_sensitive:
#             if sensitivity_result.overall_risk_score >= 7.0:
#                 # 심각한 민감성 문제 - 사람의 검토 필요
#                 decision = ValidationAgentDecision.HUMAN_REVIEW
#                 feedback = [
#                     f"심각한 민감성 문제가 감지되었습니다 (위험도: {sensitivity_result.overall_risk_score:.1f}/10)",
#                     "사람의 검토가 필요합니다."
#                 ]
                
#             elif sensitivity_result.requires_human_review or state.is_max_attempts_reached():
#                 # 사람의 검토 필요하거나 최대 시도 횟수 도달
#                 decision = ValidationAgentDecision.HUMAN_REVIEW
#                 feedback = ["민감성 문제로 인해 사람의 검토가 필요합니다."]
                
#             else:
#                 # 재시도 가능한 민감성 문제
#                 decision = ValidationAgentDecision.RETRY_WITH_FEEDBACK
#                 feedback = []
#                 for issue in sensitivity_result.detected_issues:
#                     feedback.append(f"문제: {issue.explanation}")
#                     feedback.append(f"제안: {issue.suggestion}")
                    
#         else:
#             # 민감성 문제 없음 - 다음 단계로 진행
#             decision = ValidationAgentDecision.PROCEED
#             feedback = ["민감성 검증 통과"]
        
#         logger.info(f"민감성 검증 완료: {decision}, 위험도 {sensitivity_result.overall_risk_score}")
        
#         return Command(
#             goto="route_decision",
#             update={
#                 "validation_step": "sensitivity_completed",
#                 "sensitivity_result": sensitivity_result,
#                 "agent_decision": decision,
#                 "feedback_for_user": feedback,
#                 "updated_at": datetime.now()
#             }
#         )
        
#     except Exception as e:
#         error_msg = f"민감성 검증 중 오류 발생: {str(e)}"
#         logger.error(error_msg, exc_info=True)
        
#         return Command(
#             goto=END,
#             update={
#                 "agent_decision": ValidationAgentDecision.FAIL,
#                 "feedback_for_user": [error_msg],
#                 "updated_at": datetime.now()
#             }
#         )


# def route_sensitivity_decision(state: ValidationAgentState) -> Literal["sensitivity_validation_agent", "human_review_required", "proceed_to_next", "__end__"]:
#     """
#     민감성 검증 결과에 따른 라우팅 결정
    
#     에이전트의 결정에 따라 다음 노드로 라우팅합니다:
#     - PROCEED: 다음 검증 단계로 진행
#     - RETRY_WITH_FEEDBACK: 피드백과 함께 재시도 (Human-in-the-Loop)
#     - HUMAN_REVIEW: 사람의 검토 필요
#     - FAIL: 검증 실패로 종료
#     """
#     decision = state.agent_decision
    
#     logger.info(f"민감성 검증 라우팅 결정: {decision}")
    
#     if decision == ValidationAgentDecision.PROCEED:
#         return "proceed_to_next"
#     elif decision == ValidationAgentDecision.RETRY_WITH_FEEDBACK:
#         return "human_review_required"  # Human-in-the-Loop으로 이동
#     elif decision == ValidationAgentDecision.HUMAN_REVIEW:
#         return "human_review_required"
#     elif decision == ValidationAgentDecision.FAIL:
#         return END
#     else:
#         logger.warning(f"알 수 없는 결정: {decision}, 기본값으로 진행")
#         return "proceed_to_next"


# class SensitivityValidatorWorkflow:
#     """민감성 검증 에이전트 워크플로우 관리 클래스"""
    
#     def __init__(self):
#         self.graph = None
#         self.compiled_workflow = None
#         self._build_graph()
    
#     def _build_graph(self):
#         """워크플로우 그래프 구성"""
#         logger.info("민감성 검증 워크플로우 구성 시작")
        
#         self.graph = StateGraph(ValidationAgentState)
        
#         # 노드 추가
#         self.graph.add_node("sensitivity_validation_agent", sensitivity_validation_agent)
#         self.graph.add_node("route_decision", lambda state: state)  # 라우팅 전용 노드
        
#         # 엣지 및 조건부 엣지 추가
#         self.graph.add_edge(START, "sensitivity_validation_agent")
#         self.graph.add_conditional_edges(
#             "route_decision",
#             route_sensitivity_decision,
#             {
#                 "sensitivity_validation_agent": "sensitivity_validation_agent",  # 재시도
#                 "human_review_required": END,  # Human-in-the-Loop으로 이동 (다른 워크플로우에서 처리)
#                 "proceed_to_next": END,        # 다음 검증 단계로 (다른 워크플로우에서 처리)
#                 END: END                       # 종료
#             }
#         )
        
#         logger.info("민감성 검증 워크플로우 구성 완료")
    
#     def compile(self):
#         """워크플로우 컴파일"""
#         if not self.graph:
#             raise ValidationError("그래프가 구성되지 않았습니다")
        
#         logger.info("민감성 검증 워크플로우 컴파일 시작")
#         self.compiled_workflow = self.graph.compile(debug=False)
#         logger.info("민감성 검증 워크플로우 컴파일 완료")
    
#     def run(self, user_input: str, workflow_id: str = None) -> ValidationAgentState:
#         """민감성 검증 실행"""
#         if not self.compiled_workflow:
#             self.compile()
        
#         if not workflow_id:
#             workflow_id = f"sensitivity_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
#         # 초기 상태 설정
#         initial_state = ValidationAgentState(
#             agent_type="sensitivity",
#             workflow_id=workflow_id,
#             validation_step="sensitivity_validation",
#             original_input=user_input,
#             created_at=datetime.now()
#         )
        
#         logger.info(f"민감성 검증 실행 시작: {workflow_id}")
        
#         try:
#             # 워크플로우 실행
#             final_state = None
#             for state in self.compiled_workflow.stream(initial_state):
#                 final_state = list(state.values())[0] if state else None
            
#             if not final_state:
#                 raise ValidationError("워크플로우 실행 결과를 받지 못했습니다")
            
#             logger.info(f"민감성 검증 완료: {workflow_id}, 결정: {final_state.agent_decision}")
#             return final_state
            
#         except Exception as e:
#             logger.error(f"민감성 검증 실행 실패: {str(e)}")
#             raise ValidationError(f"민감성 검증 실행 실패: {str(e)}")


# # 전역 워크플로우 인스턴스 (싱글톤 패턴)
# _sensitivity_workflow_instance = None

# def get_sensitivity_validator() -> SensitivityValidatorWorkflow:
#     """민감성 검증 워크플로우 인스턴스 반환 (싱글톤)"""
#     global _sensitivity_workflow_instance
#     if _sensitivity_workflow_instance is None:
#         _sensitivity_workflow_instance = SensitivityValidatorWorkflow()
#         _sensitivity_workflow_instance.compile()
#     return _sensitivity_workflow_instance
