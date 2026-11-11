"""Voice-first composer with review before sending and no duplicate transcription."""
import hashlib

import streamlit as st


def transcribe_once(service, recording, state, retry=False):
    if not recording or service is None:
        return
    digest = hashlib.sha256(recording).hexdigest()
    if digest == state.get("voice_digest") and not retry:
        return
    # Mark before calling: failed recordings also need an explicit retry.
    state["voice_digest"] = digest
    state["voice_draft"] = ""
    state["voice_error"] = ""
    try:
        state["voice_draft"] = service.transcribe(recording)
    except ValueError as exc:
        state["voice_error"] = str(exc)
    except Exception:
        state["voice_error"] = "음성을 인식하지 못했습니다. 다시 시도하거나 글로 입력하세요."


def submit_voice_question():
    text = st.session_state.voice_draft.strip()
    if text:
        st.session_state.pending_question = text
        st.session_state.voice_draft = ""
        st.session_state.voice_error = ""
        # Retain digest: the widget still holds this recording after rerun.


def render_voice_panel(service):
    with st.container(border=True, key="voice_panel"):
        st.markdown('<div class="voice-heading"><span>경동글로벌텍 · 음성 업무 도우미</span><h2>현장에서는, 말로 물어보세요.</h2><p>마이크를 누르고 질문한 뒤 정지하세요.</p></div>', unsafe_allow_html=True)
        st.caption("예: ‘자재가 부족한 프로젝트와 구매 담당자가 할 일을 알려줘.’")
        st.caption("녹음을 마치면 음성 인식을 위해 OpenAI로 전송합니다. 질문은 내용을 확인한 뒤 보내세요.")
        recording = st.audio_input("눌러서 말하기 · 다시 누르면 녹음 종료", key="voice_recording", disabled=service is None)
        data = recording.getvalue() if recording else None
        if data and service and hashlib.sha256(data).hexdigest() != st.session_state.voice_digest:
            with st.spinner("말씀하신 내용을 글자로 바꾸고 있습니다…"):
                transcribe_once(service, data, st.session_state)
        if st.session_state.get("voice_error"):
            st.error(st.session_state.voice_error)
            if st.button("이 녹음 다시 인식", disabled=not data or service is None):
                with st.spinner("다시 듣고 있습니다…"):
                    transcribe_once(service, data, st.session_state, retry=True)
                st.rerun()
        if st.session_state.voice_draft:
            st.success("인식 완료 · 프로젝트 번호와 숫자를 확인하세요.")
            st.text_area("인식한 질문 · 수정 가능", key="voice_draft", height=100)
            st.button("확인한 질문 보내기", key="send_voice", type="primary", use_container_width=True,
                      on_click=submit_voice_question, disabled=service is None or not st.session_state.voice_draft.strip())
        st.toggle("답변을 음성으로도 준비", value=True, key="voice_answers", help="답변 생성 후 음성도 준비합니다. 대화의 재생 버튼으로 들을 수 있습니다.")
        if service is None:
            st.info("음성 기능을 사용하려면 왼쪽 위 사이드바를 열어 API 키를 설정하세요.")
        with st.expander("마이크가 작동하지 않나요?"):
            st.write("브라우저의 마이크 권한을 허용하고 HTTPS 주소로 접속하세요. 인식이 어렵다면 아래 글 입력을 사용하세요. 녹음은 DB에 저장하지 않습니다.")
