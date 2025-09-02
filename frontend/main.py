"""
MVP 채용공고 자동생성 Streamlit 프론트엔드

핵심 기능만 포함:
1. 자연어 입력
2. 채용공고 생성 요청
3. Human-in-the-Loop 피드백
4. 결과 표시
"""

import streamlit as st
import requests
import logging
import time
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# 페이지 설정
st.set_page_config(
    page_title="채용공고 자동생성 (MVP)",
    page_icon="📝",
    layout="wide"
)

# API 베이스 URL
API_BASE_URL = "http://localhost:8080/api/v1"

# 세션 상태 초기화
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.user_name = f"User_{st.session_state.session_id[:8]}"
    st.session_state.started = False
    st.session_state.workflow_started = False
    st.session_state.feedback_submitted = False
    st.session_state.feedback_wait_cnt = 0

def call_generate_api(user_input: str, session_id: str) -> Dict[str, Any]:
    """채용공고 생성 API 호출"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/generate/",
            json={
                "user_input": user_input,
                "session_id": session_id  # 세션 ID 포함
            },
            timeout=10
        )
        if response.status_code == 202:
            try:
                result = response.json()
            except requests.JSONDecodeError as e:
                st.error(f"API 응답 파싱 오류: {e}")
                return {"result": response.text}
            return result
        else:
            st.error(f"API 오류 in call_generate_api: {response.status_code} - {response.text}")
            return {}
    except requests.RequestException as e:
        st.error(f"네트워크 오류: {e}")
        return {}

def check_feedback_sessions(session_id: str) -> Dict[str, Any]:
    """현재 사용자의 활성 피드백 세션 확인"""
    try:
        response = requests.get(f"{API_BASE_URL}/feedback/sessions/{session_id}", timeout=10)
        if response.status_code == 200:
            try:
                user_session = response.json()
            except requests.JSONDecodeError as e:
                st.error(f"API 응답 파싱 오류: {e}")
                return {"result": response.text}
            return user_session
        else:
            st.error(f"API 오류 in check_feedback_sessions: {response.status_code} - {response.text}")
            return {"status": "error", "error": f"HTTP {response.status_code}"}
    except requests.RequestException as e:
        st.error(f"네트워크 오류: {e}")
        return {"status": "error", "error": str(e)}

def submit_feedback(session_id: str, feedback_responses: List[str]) -> bool:
    """피드백 제출"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/feedback/sessions/{session_id}/submit",
            json={
                "session_id": session_id,
                "user_feedback": feedback_responses,
                "timestamp": datetime.now().isoformat()
            },
            timeout=60
        )
        return response.status_code == 200
    except:
        return False

def check_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """워크플로우 상태 확인"""
    try:
        response = requests.get(f"{API_BASE_URL}/generate/status/{workflow_id}", timeout=10)
        if response.status_code == 200:
            try:
                result = response.json()
            except requests.JSONDecodeError as e:
                st.error(f"API 응답 파싱 오류: {e}")
                return {"result": response.text}
            return result
        else:
            st.error(f"API 오류 in check_workflow_status: {response.status_code} - {response.text}")
            return {"status": "error", "error": f"HTTP {response.status_code}"}
    except requests.RequestException as e:
        st.error(f"네트워크 오류: {e}")
        return {"status": "error", "error": str(e)}

def wait_for_workflow_completion(workflow_id: str, progress_placeholder, max_wait_time: int = 30) -> Dict[str, Any]:
    """워크플로우 완료까지 대기 (polling with live progress)"""
    start_time = time.time()
    poll_interval = 5  # 2초마다 체크
    
    while time.time() - start_time < max_wait_time:
        status = check_workflow_status(workflow_id)
        current_status = status.get("status", "error")
        current_step = status.get("current_step", "error")
        print(current_status, current_step)
        
        # 진행 상황 실시간 업데이트
        elapsed = int(time.time() - start_time)
        with progress_placeholder.container():
            st.write(f"🔄 현재 단계: {current_step}")
            st.write(f"⏱️ 경과 시간: {elapsed}초")
        
        # 완료 상태 체크
        if current_status == "completed":
            with progress_placeholder.container():
                st.success("✅ 워크플로우 완료!")
            return status
        elif current_status in ["failed", "error"]:
            with progress_placeholder.container():
                st.error(f"❌ 워크플로우 실패: {status.get('error', '알 수 없는 오류')}")
            return status
        
        time.sleep(poll_interval)
    
    # 타임아웃
    with progress_placeholder.container():
        st.info("⏰ 워크플로우 완료 대기 시간 초과, 피드백 요청 여부 확인 진행")
    return {"status": "timeout", "current_step": "check_feedback_sessions"}

def main():
    print("session states: \n", st.session_state)
    st.title("📝 채용공고 자동생성 (MVP)")
    st.markdown("---")
    
    # 사이드바에서 피드백 세션 모니터링
    with st.sidebar:
        st.header("🔄 피드백 요청")
        
        # 세션 정보 표시
        st.info(f"👤 **사용자**: {st.session_state.user_name}")
        st.text(f"🆔 **세션 ID**: {str(st.session_state.session_id)[:12]}...")
        
        # 세션 초기화 버튼
        if st.button("🔄 새 세션 시작", key="reset_session"):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.user_name = f"User_{st.session_state.session_id[:8]}"
            st.session_state.workflow_started = False
            st.session_state.feedback_wait_cnt = 0
            st.session_state.feedback_submitted = False
            st.session_state.started = False
            if 'generation_result' in st.session_state:
                del st.session_state.generation_result
            st.rerun()
        
        st.markdown("---")
        
        # 활성 피드백 세션 확인 (현재 세션만)
        if st.session_state.started and not st.session_state.feedback_submitted:
            session = check_feedback_sessions(st.session_state.session_id)
        else:
            session = None
            if st.session_state.feedback_submitted:
                st.info("피드백이 전달되었습니다.")
        
        if session:
            st.warning(f"⚠️ 피드백 요청이 대기 중입니다!")
            
            if session.get("status") == "error" and st.session_state.feedback_wait_cnt < 10:
                time.sleep(4)
                st.session_state.feedback_wait_cnt += 1
                st.rerun()
                
            if session.get("status") == "expired":
                st.info("피드백 세션이 만료되었습니다.")
            
            if session.get("status") == "pending":
                with st.expander(f"세션 {session['session_id']}", expanded=True):
                    st.write(f"**유형:** {session['session_type']}")
                    st.write(f"**생성시간:** {session['timestamp']}")
                    
                    # 질문 표시
                    questions = session.get("feedback_request", [])
                    
                    if questions:
                        st.write("**검출된 문제점:**")
                        for i, question in enumerate(questions):
                            st.write(f"{i+1}. {question}")
                        
                        # 피드백 입력
                        st.write("**수정사항 입력:**")
                        feedback_responses = []
                        for i, question in enumerate(questions):
                            response = st.text_area(
                                f"질문 {i+1}에 대한 답변:",
                                key=f"feedback_{session['session_id']}_{i}",
                                placeholder="어떻게 수정하시겠습니까?"
                            )
                            feedback_responses.append(response)
                        
                        # 제출 버튼
                        if st.button(f"피드백 제출", key=f"submit_{session['session_id']}"):
                            if all(feedback_responses):
                                if submit_feedback(session['session_id'], feedback_responses):
                                    st.session_state.feedback_submitted = True
                                    st.success("피드백이 제출되었습니다!")
                                    st.rerun()
                                else:
                                    st.error("피드백 제출에 실패했습니다.")
                            else:
                                st.warning("모든 질문에 답변해주세요.")
        else:
            st.info("현재 대기 중인 피드백 요청이 없습니다.")
    
    # 메인 컨텐츠
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("1️⃣ 채용공고 정보 입력")
        
        # 자연어 입력 (간단한 형태)
        company_name = st.text_input("회사명", placeholder="예: ABC 테크놀로지")
        job_title = st.text_input("채용 직무", placeholder="예: 백엔드 개발자")
        
        # 요구사항 입력
        st.subheader("필수 요구사항")
        requirements = []
        for i in range(3):
            req = st.text_input(f"요구사항 {i+1}", key=f"req_{i}", placeholder="예: Python 3년 이상 경험, Agent 개발 경험험")
            if req:
                requirements.append(req)
        
        # 우대사항 입력
        st.subheader("우대사항")
        preferred = []
        for i in range(2):
            pref = st.text_input(f"우대사항 {i+1}", key=f"pref_{i}", placeholder="예: AWS 경험, 협업 능력")
            if pref:
                preferred.append(pref)
                
        # 채용 형태 입력
        job_type = st.selectbox("채용 형태", ["정규직", "계약직", "인턴십", "프리랜서", "임시직"])

        # 경력 사항 입력
        experience_level = st.selectbox("경력 사항", ["신입", "주니어", "중급", "시니어", "리드", "임원"])
        
        # 급여 사항 입력
        salary_info = st.text_input("급여 사항", placeholder="예: 연봉 5000만원 이상, 연봉 협의 가능")
        
        # 근무 위치 입력
        work_location = st.text_input("근무 위치", placeholder="예: 서울, 경기도")
        
        # 추가 정보 입력
        additional_info = st.text_input("추가 정보", placeholder="예: 회사 소개, 채용 프로세스")
        
        # 결과가 아직 없는 상황
        if "generation_result" not in st.session_state:
            # 생성 및 워크 플로우 시작 버튼
            if st.button("🚀 채용공고 생성", type="primary"):
                st.session_state.started = True
                if company_name and job_title and requirements:
                    
                    # UserInput 형태로 구성
                    user_input = f"""
채용 직무명: {job_title}
회사명: {company_name}
필수 요구사항: {requirements}
우대 사항: {preferred}
채용 형태: {job_type}
경력 수준: {experience_level}
급여 정보: {salary_info}
근무 위치: {work_location}
추가 정보: {additional_info}"""
                    
                    # 1단계: 워크플로우 시작
                    result = call_generate_api(user_input, st.session_state.session_id)
                    st.session_state.workflow_started = result.get("success", False)
                    if result and result.get("success"):
                        st.info("워크플로우 시작에 성공했습니다 잠시만 기다려주세요.")
                        time.sleep(10) # 잠시 대기
                    else:
                        st.error("워크플로우 시작에 실패했습니다.")
                        
                else:
                    st.warning("회사명, 직무, 요구사항을 모두 입력해주세요.")        
                    
            if st.session_state.workflow_started:
                workflow_id = st.session_state.session_id
                st.info(f"🚀 워크플로우 ID: {workflow_id}")
                
                # 2단계: 완료까지 대기 (실시간 진행 상황 표시)
                progress_placeholder = st.empty()
                
                with st.spinner("워크플로우 실행 중... (Human-in-the-Loop 포함)"):
                    current_status = wait_for_workflow_completion(workflow_id, progress_placeholder)
                
                # 3단계: 결과 처리
                if current_status.get("status") == "completed":
                    # 최종 결과를 세션에 저장 (임시로 상태 자체를 사용)
                    st.session_state.generation_result = {
                        "success": True,
                        "workflow_id": workflow_id,
                        "final_status": current_status,
                        "template": current_status.get("job_posting_draft", {}),
                        "metadata": current_status.get("metadata", {})
                    }
                    st.success("✅ 채용공고 생성이 완료되었습니다!")
                    progress_placeholder.empty()  # 진행 상황 정리
                    st.rerun()
                elif current_status.get("status") == "failed" or current_status.get("status") == "error":
                    progress_placeholder.empty()  # 진행 상황 정리
                    logger.error(f"워크플로우 실패: {current_status.get('status')}")
                    st.error(f"❌ 워크플로우 실패: {current_status.get('error', '알 수 없는 오류')}")
                    time.sleep(5)
                    st.rerun()
                else:
                    st.info("워크플로우 진행 중...")
                    time.sleep(5)
                    st.rerun()

        # 결과가 있는 상황        
        else:
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🔄 다시 생성", type="secondary"):
                    st.session_state.workflow_started = False
                    st.session_state.feedback_wait_cnt = 0
                    st.session_state.feedback_submitted = False
                    # 기존 결과 삭제하고 새로 생성
                    del st.session_state.generation_result
                    st.rerun()
            with col_btn2:
                st.info("이미 생성된 결과가 있습니다 →")
    
    with col2:
        st.header("2️⃣ 생성 결과")
        
        # 결과 표시
        if "generation_result" in st.session_state:
            result = st.session_state.generation_result
            
            # 성공 여부 확인
            if result.get("success"):
                template = result.get("template", {})
                
                st.subheader("📋 생성된 채용공고 초안")
                
                # 제목
                st.markdown(f"### {template.get('title', '제목 없음')}")
                
                # 회사명
                st.markdown(f"**회사:** {template.get('company_name', '회사명 없음')}")
                
                # 직무 설명
                st.markdown("**직무 설명:**")
                st.markdown(template.get('job_description', '설명 없음'))
                
                # 요구사항
                if template.get('requirements'):
                    st.markdown("**필수 요구사항:**")
                    for req in template['requirements']:
                        st.markdown(f"- {req}")
                
                # 우대사항
                if template.get('preferred_qualifications'):
                    st.markdown("**우대사항:**")
                    for pref in template['preferred_qualifications']:
                        st.markdown(f"- {pref}")
                        
                # 채용 형태
                st.markdown("**채용 형태:**")
                st.markdown(template.get('job_type', '채용 형태 없음'))
                
                # 경력 수준
                st.markdown("**경력 수준:**")
                st.markdown(template.get('experience_level', '경력 수준 없음'))
                
                # 급여 정보
                st.markdown("**급여 정보:**")
                st.markdown(template.get('salary_info', '급여 정보 없음'))
                
                # 근무 위치
                st.markdown("**근무 위치:**")
                st.markdown(template.get('work_location', '근무 위치 없음'))
                
                # 추가 정보
                st.markdown("**복리 후생:**")
                st.markdown(template.get('benefits', '복리 후생 없음'))
                
                # 지원 마감일
                st.markdown("**지원 마감일:**")
                st.markdown(template.get('application_deadline', '지원 마감일 없음'))
                
                # 담당자 연락처
                st.markdown("**담당자 연락처:**")
                st.markdown(template.get('contact_email', '담당자 연락처 없음'))
                
                # 메타데이터
                st.subheader("📊 생성 정보")
                metadata = result.get("metadata", {})
                col_meta1, col_meta2 = st.columns(2)
                sensitivity_validation_metadata = metadata.get("sensitivity_validation_metadata", {})
                structured_input_metadata = metadata.get("structured_input_metadata", {})
                draft_metadata = metadata.get("draft_metadata", {})
                hallucination_validation_metadata = metadata.get("hallucination_validation_metadata", {})
                with col_meta1:
                    st.metric("민감성 검증 시간", f"{sensitivity_validation_metadata.get('generation_time', 0):.1f}초")
                    st.metric("민감성 검증 모델", sensitivity_validation_metadata.get("generated_by", "알 수 없음"))
                    st.metric("환각 검증 시간", f"{hallucination_validation_metadata.get('generation_time', 0):.1f}초")
                    st.metric("환각 검증 모델", hallucination_validation_metadata.get("generated_by", "알 수 없음"))
                    
                
                with col_meta2:
                    st.metric("입력 구조화 시간", f"{structured_input_metadata.get('generation_time', 0):.1f}초")
                    st.metric("입력 구조화 모델", structured_input_metadata.get("generated_by", "알 수 없음"))
                    st.metric("초안 생성 시간", f"{draft_metadata.get('generation_time', 0):.1f}초")
                    st.metric("초안 생성 모델", draft_metadata.get("generated_by", "알 수 없음"))
                
                st.metric("전체 생성 시간", f"{sensitivity_validation_metadata.get('generation_time', 0) + hallucination_validation_metadata.get('generation_time', 0) + structured_input_metadata.get('generation_time', 0) + draft_metadata.get('generation_time', 0):.1f}초")
                    
            else:
                st.error("채용공고 생성에 실패했습니다.")
                st.json(result)
        else:
            st.info("채용공고를 생성하려면 왼쪽에서 정보를 입력하고 '생성' 버튼을 클릭하세요.")
    
    # 하단 상태
    st.markdown("---")
    col_status1, col_status2 = st.columns(2)
    
    with col_status1:
        st.markdown("**🔗 연결 상태**")
        try:
            health_response = requests.get(f"{API_BASE_URL}/status/health", timeout=5)
            if health_response.status_code == 200:
                st.success("백엔드 API 연결됨")
            else:
                st.error("백엔드 API 연결 실패")
        except:
            st.error("백엔드 API에 연결할 수 없습니다")
    
    with col_status2:
        st.markdown("**📊 시스템 정보**")
        st.info("MVP 버전 1.0")

if __name__ == "__main__":
    main()
