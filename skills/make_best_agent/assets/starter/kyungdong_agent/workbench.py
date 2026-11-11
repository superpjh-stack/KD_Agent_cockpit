"""Customer task entry point; shares the same rule service as the AI tools."""
from datetime import date

import streamlit as st


def render_workbench(repository):
    with st.container(border=True, key="task_workbench"):
        st.subheader("지금 확인할 일")
        st.caption("프로젝트 선택 → 확인 항목 검토 → 담당자와 다음 조치 확인")
        projects = {p["project_id"]: p for p in repository.projects()}
        left, right = st.columns([3, 1])
        project_id = left.selectbox("업무 대상", [None, *projects],
            format_func=lambda key: "전체 프로젝트" if key is None else f"{key} · {projects[key]['customer']} · {projects[key]['equipment_type']}")
        as_of = right.date_input("평가 기준일", value=date.today())
        report = repository.evaluate_rules(project_id, as_of.isoformat())
        st.caption(f"{report['notice']} 기준일 {report['as_of']} · 조건별 레코드 {report['checked_records']}회 확인")
        owners = sorted({f["owner"] for f in report["findings"]})
        owner = st.selectbox("담당 업무", ["전체", *owners])
        findings = [f for f in report["findings"] if owner == "전체" or f["owner"] == owner]
        if report["unevaluated"]:
            st.warning(f"미평가 {len(report['unevaluated'])}건이 있습니다. 데이터·조건 확인이 필요합니다.")
            with st.expander("미평가 이유"):
                st.dataframe(report["unevaluated"], hide_index=True)
        if not findings:
            st.info("선택한 범위에서 해당 조건이 발견되지 않았습니다. 전체 정상이나 출하 승인을 뜻하지 않습니다.")
        else:
            st.write(f"확인 후보 {len(findings)}건")
            for finding in findings:
                with st.expander(f"{finding['name']} · {finding['record_id']} · {finding['owner']}"):
                    st.write(f"다음 조치: {finding['action']}")
                    st.caption(f"{finding['rule_id']} / {finding['revision']} / {finding['status']}")
                    st.write(f"판정 조건: {finding['condition']}")
                    st.json(finding["record"], expanded=False)
                    document = finding["document"]
                    if document:
                        st.caption(f"절차 근거: {document['filename']} · {document['source']} · {document['status']}")
                        st.text(document["content"] or "보관된 본문이 없습니다.")
                    else:
                        st.warning("연결된 근거 문서가 없습니다. 담당자에게 기준을 확인하세요.")
                    if st.button("이 항목의 대응 절차 질문", key=f"task_{finding['rule_id']}_{finding['record_id']}"):
                        st.session_state.pending_question = (
                            f"{finding['project_id'] or ''} {finding['record_id']}의 {finding['name']}에 대해 "
                            f"{report['as_of']} 기준 룰 {finding['rule_id']}를 평가하고, "
                            f"{finding['source_document']} 문서를 검색해서 담당자와 대응 절차를 알려줘.")
                        st.rerun()
        target = project_id or "전체 프로젝트"
        for col, label, question in zip(st.columns(3),
                ["확인할 일 요약", "자재·입고 확인", "출하 전 검사 확인"],
                [f"{target}의 {report['as_of']} 기준 확인할 일과 담당자를 룰로 평가해줘.",
                 f"{target}의 자재 부족과 입고검사 보류 현황 및 대응 절차를 알려줘.",
                 f"{target}의 출하 전 성능검사 결과와 미해결 항목, 확인 절차를 알려줘."]):
            if col.button(label, use_container_width=True):
                st.session_state.pending_question = question
                st.rerun()
