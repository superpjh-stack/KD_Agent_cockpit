from __future__ import annotations

from datetime import datetime
from typing import Any


QUESTION_GROUPS = {
    "지식베이스": [
        "수주부터 출하까지 전체 제조공정 순서를 알려줘.",
        "견적 원가를 계산할 때 어떤 비용을 확인해야 해?",
        "도면이 변경되면 무엇부터 확인해야 해?",
        "자재 입고검사에서 확인해야 할 항목은 뭐야?",
        "자재가 부족할 때 대체자재 승인은 어떻게 받아?",
        "레이저 절단 작업 전에 무엇을 확인해야 해?",
        "절곡·포밍에서 불량이 생기면 어떻게 처리해?",
        "용접·조립 검사에는 어떤 기록이 필요해?",
        "FAT 불합격 후 재시험과 출하는 어떻게 진행해?",
        "납기가 늦어질 때 어떤 순서로 대응해야 해?",
    ],
    "DB": [
        "등록된 프로젝트의 고객, 장비, 납기를 보여줘.",
        "프로젝트별 도면 Revision과 변경 승인 상태를 보여줘.",
        "자재별 재고 수량과 부족·보류 상태를 보여줘.",
        "입고검사에서 보류된 자재와 측정값을 보여줘.",
        "공정별 계획 공수와 실제 공수, 진행 상태를 비교해줘.",
        "설비 측정값과 주의 상태인 항목을 보여줘.",
        "프로젝트별 예상 원가와 이익률을 비교해줘.",
        "발주별 입고예정일과 예상 지연일을 보여줘.",
        "FAT 시험 결과와 불합격 원인, 조치 내용을 보여줘.",
        "등록된 클레임의 원인과 개선 조치를 보여줘.",
    ],
    "룰": [
        "등록된 판정 룰과 각 담당자를 한눈에 보여줘.",
        "자재 부족 룰의 조건과 필요한 조치는 뭐야?",
        "입고 지연 예상 룰은 어떤 날짜를 비교해?",
        "설계 변경 승인 대기 룰의 조건과 담당자는 누구야?",
        "공정 지연 룰은 어떤 조건에서 해당돼?",
        "계획 공수 초과 룰과 실제 원가 초과는 어떻게 달라?",
        "FAT 불합격 룰에 따르면 어떤 조치가 필요해?",
        "입고검사 보류 룰은 문서 누락도 확인해?",
        "각 판정 룰의 근거 문서와 개정번호를 보여줘.",
        "등록된 룰 중 구매·설계·품질 담당자가 확인할 일을 정리해줘.",
    ],
}


WELCOME_MESSAGE = {
    "role": "assistant",
    "content": (
        "안녕하세요. 경동글로벌텍 제조 Agent입니다.  \n"
        "수주·견적, 설계 변경, 자재·구매, 제작 진척, FAT·클레임을 연결해 근거와 함께 답변합니다. "
        "지식·데이터 현황을 확인하거나 추천질문을 선택해 시작하세요."
    ),
    "sources": [],
    "evidence": [],
    "data_tools": [],
    "created_at": "시작",
}


def timestamp() -> str:
    return datetime.now().strftime("%H:%M")


def user_question_history(messages: list[dict[str, Any]], limit: int = 8) -> list[dict[str, str]]:
    result = []
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        result.append({"content": str(message.get("content", "")), "created_at": str(message.get("created_at", ""))})
        if len(result) >= limit:
            break
    return result


def project_snapshot(repository: Any, project_id: str) -> dict[str, Any]:
    project = repository.projects(project_id)
    material_issues = repository.material_status(project_id, True)
    inspection_issues = repository.inspection_issues(project_id)
    procurement = repository.procurement_risks(project_id)
    fat = repository.fat_quality(project_id)
    lead = repository.lead_time_status(project_id)
    quote = repository.quote_analysis(project_id)
    return {
        "project": project[0] if project else {},
        "material_issue_count": len(material_issues) + len(inspection_issues),
        "procurement_risk_count": len([row for row in procurement if row.get("risk") == "높음"]),
        "fat_failure_count": len([row for row in fat if row.get("result") == "불합격"]),
        "lead": lead[0] if lead else {},
        "quote": quote[0] if quote else {},
        "materials": material_issues,
        "procurement": procurement,
        "fat": fat,
    }


def risk_label(snapshot: dict[str, Any]) -> tuple[str, str]:
    score = snapshot["material_issue_count"] + snapshot["procurement_risk_count"] * 2 + snapshot["fat_failure_count"] * 2
    if score >= 4:
        return "높음", "🔴"
    if score >= 1:
        return "주의", "🟠"
    return "안정", "🟢"
