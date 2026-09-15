import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("langgraph")


async def test_graph_preserves_evidence_and_calls_fetch_once():
    spec = importlib.util.spec_from_file_location(
        "agent_example", Path(__file__).parents[1] / "examples/langgraph_agent.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seen = []

    async def fetch(query):
        seen.append(query)
        return [{"id": "HW-001", "name": "Laptop"}]

    async def report(records):
        assert records == [{"id": "HW-001", "name": "Laptop"}]
        return "Source: HW-001"

    result = await module.build_graph(fetch, report).ainvoke({"query": "Laptop"})
    assert result["answer"] == "Source: HW-001"
    assert seen == ["Laptop"]
