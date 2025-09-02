"""
민감성 검증 에이전트

이 모듈은 사용자 입력을 분석하여 차별적 표현, 개인정보 요구, 부적절한 내용 등
민감하거나 부적절한 정보를 감지하는 LangGraph 기반 에이전트를 구현합니다.
"""

import logging
import uuid
import json
import time
import requests
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
API_BASE_URL = "http://localhost:8080/api/v1"

class SensitivityValidationRequest(BaseModel):
    """민감성 검증 요청 모델"""
    user_input: UserInput = Field(description="검증할 구조화된 사용자 입력 텍스트")

class SensitivityValidationResult(BaseModel):
    """민감성 검증 결과"""
    user_input: Optional[UserInput] = Field(description="민감성 검증 결과를 고려하여 수정된 사용자 입력 텍스트, 개선 사항이 없다면 None 입력")
    reasoning: str = Field(description="수정 결과에 대한 논리적인 이유, 수정 및 개선 사항이 없다면 '문제 없음' 입력")

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
    start_time = time.time()
    try:
        user_input = request.user_input
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
                                            response_format=SensitivityValidationResult,
                                            checkpointer=memory,
                                            name="sensitivity_validation_agent")
        # 한글 유지하면서 JSON 변환 (ensure_ascii=False)
        user_input_text = json.dumps(request.user_input.model_dump(), ensure_ascii=False, indent=2)
        config = {"configurable": {"thread_id": thread_id}}
        
        response = agent_executor.invoke({"messages": [{"role": "user", "content": user_input_text}]},
                                        config=config,
                                        interrupt_after=["tools"],
                                        stream_mode="values")
        if "structured_response" in response:
            structured_response = response["structured_response"]
            metadata = {"thread_id": thread_id, "generated_by": model, "reasoning": structured_response.reasoning, "generation_time": time.time() - start_time}
            validated_user_input = structured_response.user_input
            if validated_user_input is None:
                return user_input, metadata
            
            return validated_user_input, metadata
        logger.info(f"민감성 검증 중간 결과: {response}")
        
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
                raise ValidationError("민감성 기반 첨삭 결과를 받지 못했습니다")
            
            metadata = {"thread_id": thread_id, "generated_by": model, "reasoning": structured_response.reasoning, "generation_time": time.time() - start_time}
            validated_user_input = structured_response.user_input
            if validated_user_input is None:
                return user_input, metadata
            
            return validated_user_input, metadata
        
    except Exception as e:
        logger.error(f"LLM 민감성 분석 실패: {str(e)}")
        raise ValidationError(f"민감성 분석 중 오류 발생: {str(e)}")


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
                "session_type": "sensitivity_detected",
                "template_id": str(uuid.uuid4()),
                "feedback_request": {
                    "questions": questions,  # "question" → "questions"로 수정
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
