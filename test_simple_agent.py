import asyncio
import pytest
import csv
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

# Import the specific agent to be tested
from simple_agent import SimpleAgent

# === Load QA data from CSV ===
try:
    with open("qa_results-4.csv", newline='', encoding='utf-8') as csvfile:
        qa_data = list(csv.DictReader(csvfile))
except FileNotFoundError:
    pytest.fail("Test data file 'qa_results-4.csv' not found. Please ensure it is in the correct directory.", pytrace=False)

# === Define the metric once ===
correctness_metric = GEval(
    name="Correctness",
    criteria="Determine if the 'actual output' is correct based on the 'expected output'.",
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    threshold=0.5,
)

# === Fixture to Create the Agent ===
@pytest.fixture
def agent():
    """Creates an instance of the SimpleAgent."""
    return SimpleAgent(session=None)

# === Parameterized Test Function ===
@pytest.mark.asyncio
@pytest.mark.parametrize("qa_pair", qa_data, ids=[f"QA{i}" for i in range(len(qa_data))])
async def test_agent_qa(agent, qa_pair):
    """Runs a single question-answer test against the agent."""
    question = qa_pair["question"]
    expected_answer = qa_pair["answer"]

    result = await agent.run(question)

    actual_output = result.final_output if hasattr(result, "final_output") else str(result)

    test_case = LLMTestCase(
        input=question,
        actual_output=actual_output,
        expected_output=expected_answer,
    )
    assert_test(test_case, [correctness_metric])
