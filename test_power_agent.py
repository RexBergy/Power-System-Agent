# import asyncio
# import pytest
# import csv
# from deepeval import assert_test
# from deepeval.metrics import GEval
# from deepeval.test_case import LLMTestCase, LLMTestCaseParams
# from agents.mcp import MCPServerStdio
# from power_agent_simplified import SimplifiedPowerSystemAgent

# # === Load QA data ===
# with open("qa_results-4.csv", newline="", encoding="utf-8") as csvfile:
#     qa_data = list(csv.DictReader(csvfile))

# # === Define metric once ===
# correctness_metric = GEval(
#     name="Correctness",
#     criteria="Determine if the 'actual output' is correct based on the 'expected output'.",
#     evaluation_params=[
#         LLMTestCaseParams.ACTUAL_OUTPUT,
#         LLMTestCaseParams.EXPECTED_OUTPUT,
#     ],
#     threshold=0.5,
# )

# # === Parameterized test function ===
# @pytest.mark.parametrize("qa_item", qa_data)
# @pytest.mark.asyncio
# async def test_power_agent_qa(qa_item):
#     question = qa_item["question"]
#     expected_answer = qa_item["answer"]

#     mcp_server = MCPServerStdio(
#         name="Pandapower MCP Server",
#         params={
#             "command": ".venv/bin/python3.12",
#             "args": ["/Users/philippebergeron/Documents/Agent_Psse/PowerMCP/pandapower/panda_mcp.py"],
#         },
#         cache_tools_list=True,
#         client_session_timeout_seconds=30,
#     )

#     try:
#         await mcp_server.connect()
#         system = SimplifiedPowerSystemAgent(session=None, mcp_server=mcp_server)

#         result = await system.run(question)
#         # Ensure actual_output is not None
#         actual_output = result.final_output if result.final_output is not None else ""

#         print(f"Input: {question}")
#         print(f"Actual Output: {repr(actual_output)}")
#         print(f"Expected Output: {expected_answer}")
#         print("-" * 20)

#         test_case = LLMTestCase(
#             input=question,
#             actual_output=actual_output,
#             expected_output=expected_answer,
#         )
#         assert_test(test_case, [correctness_metric])

#     finally:
#         await mcp_server.cleanup()
import asyncio
import pytest
import re
import csv
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from agents.mcp import MCPServerStdio
from power_agent_simplified import PowerSystemAgent

# === Load QA data ===
with open("qa_results-4.csv", newline='', encoding='utf-8') as csvfile:
    qa_data = list(csv.DictReader(csvfile))

# === Prepare MCP server and system ===
# mcp_server = MCPServerStdio(
#     name="Pandapower MCP Server",
#     params={
#         "command": ".venv/bin/python3.12",
#         "args": ["/Users/philippebergeron/Documents/Agent_Psse/PowerMCP/pandapower/panda_mcp.py"],
#     },
#     cache_tools_list=True,
#     client_session_timeout_seconds=30,
# )

# asyncio.run(mcp_server.connect())
# system = SimplifiedPowerSystemAgent(session=None, mcp_server=mcp_server)

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
        mcp_server = MCPServerStdio(
            name="Pandapower MCP Server",
            params={
                "command": ".venv/bin/python3.12",
                "args": ["/Users/philippebergeron/Documents/Agent_Psse/PowerMCP/pandapower/panda_mcp.py"],
            },
            cache_tools_list=True,
            client_session_timeout_seconds=30,
        )
        try:
            await mcp_server.connect()
            system = PowerSystemAgent(model="gpt-5-mini", session=None, mcp_server=mcp_server)
            result = await system.run(q)
          #  Ensure actual_output is not None
            actual_output = result.final_output if result.final_output is not None else ""

            print(f"Input: {question}")
            print(f"Actual Output: {repr(actual_output)}")
            print(f"Expected Output: {answer}")
            print("-" * 20)
            test_case = LLMTestCase(
                input=q,
                actual_output=actual_output,
                expected_output=a,
            )
            assert_test(test_case, [correctness_metric])

        finally:
            await mcp_server.cleanup()


    # Wrap async in a pytest-compatible sync function
    def make_sync_test(async_func):
        def sync_test():
            asyncio.run(async_func())
        return sync_test

    globals()[f"test_{f'qa_{i}'}"] = make_sync_test(_run_test)

# # === Cleanup after all tests ===
# @pytest.fixture(scope="session", autouse=True)
# def cleanup_mcp_server():
#     yield
#     asyncio.run(mcp_server.cleanup())
