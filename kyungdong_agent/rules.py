"""Read-only rule checks. Stored conditions select reviewed code, never SQL/eval.

Unknown conditions remain visible as unevaluated; a rule edit cannot silently
keep running the old rule. This adapter is independent of company/rule IDs.
"""
from __future__ import annotations

from datetime import date
from typing import Any


def _value(row, key):
    value = row[key]
    if value is None or value == "":
        raise ValueError(f"{key} 누락")
    return value


def _late(row, as_of):
    status = _value(row, "status")
    return "지연" in status or (status != "완료" and date.fromisoformat(_value(row, "due_date")) < as_of)


# Source table is part of the key: changing a table never reuses an incompatible check.
CHECKS = {
    ("materials", "stock_status = 부족"): lambda r, d: _value(r, "stock_status") == "부족",
    ("purchase_orders", "expected_date > promised_date"): lambda r, d: date.fromisoformat(_value(r, "expected_date")) > date.fromisoformat(_value(r, "promised_date")),
    ("designs", "change_status에 승인대기 포함"): lambda r, d: "승인대기" in _value(r, "change_status"),
    ("operations", "status에 지연 포함 또는 미완료이고 due_date가 평가일 이전"): _late,
    ("operations", "actual_hours > plan_hours"): lambda r, d: float(_value(r, "actual_hours")) > float(_value(r, "plan_hours")),
    ("fat_tests", "result = 불합격"): lambda r, d: _value(r, "result") == "불합격",
    ("incoming_inspections", "result != 합격 또는 document_attached = 0"): lambda r, d: _value(r, "result") != "합격" or int(_value(r, "document_attached")) == 0,
}
RECORD_KEYS = {"materials": "material_lot", "purchase_orders": "po_no", "designs": "drawing_no",
               "operations": "operation_id", "fat_tests": "test_id", "incoming_inspections": "inspection_id"}


def evaluate_rules(repository: Any, project_id: str | None = None, as_of: str | None = None) -> dict:
    evaluated_on = date.fromisoformat(as_of) if as_of else date.today()
    if project_id and not repository.projects(project_id):
        raise ValueError("프로젝트를 찾을 수 없습니다.")
    findings, unevaluated = [], []
    checked = 0
    cache = {}
    documents = {d["document_id"]: d for d in repository.knowledge_documents()}
    for rule in repository.get_rules():
        table = rule["source_table"]
        check = CHECKS.get((table, rule["condition"]))
        if not check:
            unevaluated.append({"rule_id": rule["rule_id"], "reason": "지원하지 않는 조건입니다. 평가기 등록이 필요합니다."})
            continue
        if table not in cache:
            cache[table] = repository.rule_records(table, project_id)
        for row in cache[table]:
            record_id = row.get(RECORD_KEYS[table])
            try:
                matched = check(row, evaluated_on)
            except (KeyError, ValueError, TypeError, OverflowError):
                unevaluated.append({"rule_id": rule["rule_id"], "record_id": record_id, "reason": "필수 값 누락 또는 형식 오류"})
                continue
            checked += 1
            if matched:
                doc = documents.get(rule["source_document"])
                findings.append({**rule, "record_id": record_id, "project_id": row.get("project_id"),
                                 "record": row, "document": doc, "document_available": bool(doc)})
    return {"demo_data": True, "as_of": evaluated_on.isoformat(), "project_id": project_id,
            "checked_records": checked, "findings": findings, "unevaluated": unevaluated,
            "notice": "검증용 데이터·룰의 확인 후보입니다. 승인·출하 판정이 아닙니다."}
