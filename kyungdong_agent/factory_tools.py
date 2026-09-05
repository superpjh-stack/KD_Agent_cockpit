from __future__ import annotations

import json
from typing import Any, Callable

from .data_hub import KyungdongRepository


def _nullable_string(description: str) -> dict[str, Any]:
    return {"type": ["string", "null"], "description": description}


class KyungdongToolRegistry:
    """허용된 읽기 전용 제조 조회만 공개한다."""

    def __init__(self, repository: KyungdongRepository) -> None:
        self.repository = repository
        self._handlers: dict[str, Callable[..., Any]] = {
            "search_knowledge": repository.search_knowledge,
            "get_rules": repository.get_rules,
            "get_db_records": repository.table_records,
            "get_project_summary": repository.project_summary,
            "get_material_status": repository.material_status,
            "get_incoming_inspection_issues": repository.inspection_issues,
            "get_quote_analysis": repository.quote_analysis,
            "get_procurement_risks": repository.procurement_risks,
            "get_fat_quality": repository.fat_quality,
            "get_lead_time_status": repository.lead_time_status,
            "get_claim_trace": repository.claim_trace,
        }
        self.definitions = [
            self._tool("get_db_records", "업무 DB 테이블의 실제 저장 레코드를 조회한다. 설비 측정과 전체 클레임 목록 등 원본 데이터 조회에 사용한다.",
                       {"table": {"type": "string", "enum": list(repository.TABLE_LABELS),
                                  "description": "조회할 업무 테이블 이름"}}, ["table"]),
            self._tool("search_knowledge", "저장된 제조 지식문서를 로컬 키워드 검색한다. 승인 절차·검사기준·작업표준 질문에 사용한다.",
                       {"query": {"type": "string", "description": "문서 검색어 또는 질문"}}, ["query"]),
            self._tool("get_rules", "등록된 검증용 판정 룰의 조건·담당자·조치·근거 문서를 조회한다. 자동 실행 엔진이 아니다.", {}, []),
            self._tool("get_project_summary", "프로젝트·설계 리비전·공정 진행 현황을 조회한다.",
                       {"project_id": _nullable_string("프로젝트 ID. 전체이면 null")}, ["project_id"]),
            self._tool("get_material_status", "바코드 자재 LOT, MTC, 위치, 부족·보류 상태를 조회한다.",
                       {"project_id": _nullable_string("프로젝트 ID. 전체이면 null"), "issues_only": {"type": "boolean", "description": "이슈만 조회할지 여부"}}, ["project_id", "issues_only"]),
            self._tool("get_incoming_inspection_issues", "입고검사 보류·불합격과 스캔문서 누락을 조회한다.",
                       {"project_id": _nullable_string("프로젝트 ID. 전체이면 null")}, ["project_id"]),
            self._tool("get_quote_analysis", "견적 원가·납기·수익성·위험 예측 데모를 조회한다.",
                       {"project_id": _nullable_string("프로젝트 ID"), "equipment_type": _nullable_string("교반기·반응기·진공건조기 등")}, ["project_id", "equipment_type"]),
            self._tool("get_procurement_risks", "공급사 납기 위험과 대체 후보를 조회한다. 발주·대체는 승인 대상이다.",
                       {"project_id": _nullable_string("프로젝트 ID"), "supplier": _nullable_string("공급사명")}, ["project_id", "supplier"]),
            self._tool("get_fat_quality", "FAT 시험 결과와 반복 고장 패턴을 조회한다.",
                       {"project_id": _nullable_string("프로젝트 ID. 전체이면 null")}, ["project_id"]),
            self._tool("get_lead_time_status", "프로젝트별 계획·실적 공수와 지연 공정을 조회한다.",
                       {"project_id": _nullable_string("프로젝트 ID. 전체이면 null")}, ["project_id"]),
            self._tool("get_claim_trace", "클레임과 프로젝트·FAT 이력을 연결해 조회한다.",
                       {"claim_id": {"type": "string", "description": "클레임 ID"}}, ["claim_id"]),
        ]

    @staticmethod
    def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
        return {
            "type": "function",
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            "strict": True,
        }

    def execute(self, name: str, arguments: str | dict[str, Any]) -> str:
        if name not in self._handlers:
            return json.dumps({"error": "허용되지 않은 도구입니다.", "tool": name}, ensure_ascii=False)
        try:
            payload = json.loads(arguments) if isinstance(arguments, str) else arguments
            result = self._handlers[name](**payload)
            return json.dumps({"status": "ok", "demo_data": True, "result": result}, ensure_ascii=False, default=str)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return json.dumps({"error": str(exc), "tool": name}, ensure_ascii=False)
