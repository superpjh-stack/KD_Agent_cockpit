from types import SimpleNamespace

from kyungdong_agent import MAX_TOOL_ROUNDS, ManufacturingAgent


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            call = SimpleNamespace(type="function_call", name="get_project_summary", arguments='{"project_id":"KGT-26001"}', call_id="call-1")
            return SimpleNamespace(id="resp-1", output=[call], output_text="")
        return SimpleNamespace(id="resp-2", output=[], output_text="프로젝트 요약")


class FakeRegistry:
    definitions = [{"type": "function", "name": "get_project_summary", "description": "test", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}]

    def execute(self, name, arguments):
        assert name == "get_project_summary"
        return '{"status":"ok"}'


def test_responses_function_call_loop():
    responses = FakeResponses()
    client = SimpleNamespace(responses=responses)
    answer = ManufacturingAgent(client, factory_tools=FakeRegistry()).ask("요약해줘")
    assert answer.text == "프로젝트 요약"
    assert answer.data_tools == ["get_project_summary"]
    assert responses.calls[1]["input"][0]["type"] == "function_call_output"


def test_empty_question_is_rejected():
    client = SimpleNamespace(responses=FakeResponses())
    try:
        ManufacturingAgent(client, factory_tools=FakeRegistry()).ask("   ")
    except ValueError as exc:
        assert "질문" in str(exc)
    else:
        raise AssertionError("ValueError expected")


def _annotation(filename):
    return SimpleNamespace(filename=filename)


def _message(filenames):
    content = SimpleNamespace(annotations=[_annotation(name) for name in filenames])
    return SimpleNamespace(type="message", content=[content])


def _file_search_call(rows):
    results = [SimpleNamespace(filename=name, text=text, score=score) for name, text, score in rows]
    return SimpleNamespace(type="file_search_call", results=results)


def _function_call(name, call_id):
    return SimpleNamespace(type="function_call", name=name, arguments='{"project_id":"KGT-26001"}', call_id=call_id)


class SearchThenToolResponses:
    """1차에서 문서를 검색하고, 2차에서 Data Hub를 조회한 뒤 답한다."""

    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return SimpleNamespace(
                id="resp-1",
                output=[_file_search_call([("sop.md", "입고검사 절차", 0.91)]),
                        _message(["sop.md"]),
                        _function_call("get_project_summary", "call-1")],
                output_text="",
            )
        return SimpleNamespace(id="resp-2", output=[_message(["fat.md"])], output_text="최종 답변")


def test_evidence_from_earlier_rounds_is_kept():
    client = SimpleNamespace(responses=SearchThenToolResponses())
    answer = ManufacturingAgent(client, factory_tools=FakeRegistry()).ask("SOP 기준으로 알려줘", vector_store_id="vs-1")
    assert answer.text == "최종 답변"
    # 1차 라운드의 문서 근거가 최종 응답에서 사라지지 않아야 한다
    assert [row["filename"] for row in answer.evidence] == ["sop.md"]
    assert answer.evidence[0]["score"] == 0.91
    assert answer.sources == ["sop.md", "fat.md"]
    assert answer.searched_documents is True
    assert answer.knowledge_base_connected is True
    assert answer.tool_rounds == 1


class NoSearchResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return SimpleNamespace(id="resp-1", output=[_function_call("get_project_summary", "call-1")], output_text="")
        return SimpleNamespace(id="resp-2", output=[_message([])], output_text="Data Hub만 사용")


def test_searched_documents_false_when_file_search_not_used():
    client = SimpleNamespace(responses=NoSearchResponses())
    answer = ManufacturingAgent(client, factory_tools=FakeRegistry()).ask("납기 알려줘", vector_store_id="vs-1")
    assert answer.searched_documents is False
    assert answer.knowledge_base_connected is True
    assert answer.evidence == []


class EndlessToolResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("tool_choice") == "none":
            return SimpleNamespace(id="resp-final", output=[_message([])], output_text="상한 후 텍스트 답변")
        return SimpleNamespace(id=f"resp-{len(self.calls)}", output=[_function_call("get_project_summary", f"call-{len(self.calls)}")], output_text="")


def test_tool_round_cap_forces_text_answer():
    responses = EndlessToolResponses()
    client = SimpleNamespace(responses=responses)
    answer = ManufacturingAgent(client, factory_tools=FakeRegistry()).ask("무한 조회")
    assert answer.text == "상한 후 텍스트 답변"
    assert answer.tool_rounds == MAX_TOOL_ROUNDS
    assert responses.calls[-1]["tool_choice"] == "none"


def test_local_knowledge_search_keeps_evidence(tmp_path):
    from kyungdong_agent import KyungdongRepository, KyungdongToolRegistry

    class LocalSearchResponses:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                call = SimpleNamespace(type="function_call", name="search_knowledge",
                    arguments='{"query":"자재 부족 대체 승인"}', call_id="local-1")
                return SimpleNamespace(id="local-response", output=[call], output_text="")
            return SimpleNamespace(id="final", output=[], output_text="샘플 문서 기반 답변")

    registry = KyungdongToolRegistry(KyungdongRepository(tmp_path / "demo.db"))
    answer = ManufacturingAgent(SimpleNamespace(responses=LocalSearchResponses()), factory_tools=registry).ask("자재 부족")
    assert answer.searched_documents is True
    assert answer.knowledge_base_connected is True
    assert answer.evidence[0]["document_id"] == "KGT-KB-005"
    assert answer.sources[0] == answer.evidence[0]["filename"]
