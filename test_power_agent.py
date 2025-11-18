# import asyncio
# import pytest
# from deepeval import assert_test
# from deepeval.metrics import GEval
# from deepeval.test_case import LLMTestCase, LLMTestCaseParams
# from agents.mcp import MCPServerStdio
# from power_agents_variant1 import AgenticPowerSystem as AgenticPowerSystemVariant1

# import csv
# qa_data = []
# # Open and read the CSV file
# with open("qa_results.csv", newline='', encoding='utf-8') as csvfile:
#     reader = csv.DictReader(csvfile)
#     qa_data = list(reader)

# # On va ouvrir mon fichier csv json avec question/reponses

# mcp_server = MCPServerStdio(
#         name="Pandapower MCP Server",
#         params={"command": ".venv/bin/python3.12",
#                 "args": ["/Users/philippebergeron/Documents/Agent_Psse/PowerMCP/pandapower/panda_mcp.py"]
#                 },
#         cache_tools_list=True,
#         client_session_timeout_seconds=30
#     )

# asyncio.run(mcp_server.connect())

# system = AgenticPowerSystemVariant1(session=None, mcp_server=mcp_server)

# def test_case():
#     correctness_metric = GEval(
#         name="Correctness",
#         criteria="Determine if the 'actual output' is correct based on the 'expected output'.",
#         evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
#         threshold=0.01
#     )

#     for qa in qa_data:
#         question = qa["question"]
#         answer = qa["answer"]
#         test_case = LLMTestCase(
#             input=question,
#             actual_output=asyncio.run(system.run(question)).final_output,
#             expected_output=answer,
#         )
#         assert_test(test_case, [correctness_metric])


# asyncio.run(mcp_server.cleanup())

import asyncio
import pytest
import re
import csv
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from agents.mcp import MCPServerStdio
from power_agents_variant1 import AgenticPowerSystem as AgenticPowerSystemVariant1

# === Load QA data ===
with open("qa_results-3.csv", newline='', encoding='utf-8') as csvfile:
    qa_data = list(csv.DictReader(csvfile))

# === Prepare MCP server and system ===
mcp_server = MCPServerStdio(
    name="Pandapower MCP Server",
    params={
        "command": ".venv/bin/python3.12",
        "args": ["/Users/philippebergeron/Documents/Agent_Psse/PowerMCP/pandapower/panda_mcp.py"],
    },
    cache_tools_list=True,
    client_session_timeout_seconds=30,
)

asyncio.run(mcp_server.connect())
system = AgenticPowerSystemVariant1(session=None, mcp_server=mcp_server)

# === Define metric once ===
correctness_metric = GEval(
    name="Correctness",
    criteria="Determine if the 'actual output' is correct based on the 'expected output'.",
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    threshold=0.5,
)


# === Dynamically create one test per question ===
for i, qa in enumerate(qa_data):
    question = qa["question"]
    answer = qa["answer"]

    # Sanitize question text into a valid function name
    safe_name = re.sub(r"[^0-9a-zA-Z_]+", "_", question.lower())
    safe_name = safe_name.strip("_")[:50]  # limit length

    async def _run_test(q=question, a=answer):
        result = await system.run(q)
        test_case = LLMTestCase(
            input=q,
            actual_output=result.final_output,
            expected_output=a,
        )
        assert_test(test_case, [correctness_metric])

    # Wrap async in a pytest-compatible sync function
    def make_sync_test(async_func):
        def sync_test():
            asyncio.run(async_func())
        return sync_test

    globals()[f"test_{safe_name or f'qa_{i}'}"] = make_sync_test(_run_test)

# === Cleanup after all tests ===
@pytest.fixture(scope="session", autouse=True)
def cleanup_mcp_server():
    yield
    asyncio.run(mcp_server.cleanup())
