from dataclasses import dataclass
from typing import Literal, Optional
from agents import Agent, ModelSettings, Runner, function_tool, CodeInterpreterTool, SQLiteSession, Prompt
from pandapower.networks.power_system_test_cases import case30, case1888rte, case300, case118, case2848rte
from openai import OpenAI
import os
import pandapower as pp
from agents.mcp import MCPServerStdio

client = OpenAI()


@function_tool
def get_network_case(case_name: Literal["case30", "case118", "case300", "case1888rte", "case2848rte"]) -> str:
    """
    Retrieves a predefined pandapower network case by name and saves it to a JSON file in the current directory.
    This file can then be used by other tools.

    :param case_name: Name of the network case to retrieve ['case30', 'case118', 'case300', 'case1888rte', 'case2848rte']
    :return: A message indicating the result of the operation.
    """
    cases = {
        "case30": case30,
        "case118": case118,
        "case300": case300,
        "case1888rte": case1888rte,
        "case2848rte": case2848rte
    }
    if case_name in cases:
        net = cases[case_name]()
        file_path = f"{case_name}.json"
        pp.to_json(net, file_path)
        return f"Network case '{case_name}' fetched and saved to '{file_path}'. You can now use this file with other tools."
    else:
        return f"Case '{case_name}' not found. Available cases: {', '.join(cases.keys())}."

def upload_file_to_container_func(container_id: str, path: str) -> str:
    """
    Helper function to upload a file to the container.
    This is not a tool itself, but called by the agent's context.
    """
    print(f"Uploading file '{path}' to container...")
    if os.path.isfile(path):
        try:
            created_file = client.containers.files.create(
                container_id=container_id,
                file=open(path, "rb"),
            )
            print(f"File '{created_file.path}' uploaded to container.")
            return f"File '{created_file.path}' uploaded to container."
        except Exception as e:
            return f"Error uploading file: {e}"
    else:
        return f"File '{path}' does not exist."


def upload_file_to_container_func(container_id: str, path: str) -> str:
    """
    Helper function to upload a file to the container.
    This is not a tool itself, but called by the agent's context.
    """
    print(f"Uploading file '{path}' to container...")
    if os.path.isfile(path):
        try:
            created_file = client.containers.files.create(
                container_id=container_id,
                file=open(path, "rb"),
            )
            print(f"File '{created_file.path}' uploaded to container.")
            return f"File '{created_file.path}' uploaded to container."
        except Exception as e:
            return f"Error uploading file: {e}"
    else:
        return f"File '{path}' does not exist."


@dataclass
class PowerSystemAgent:
    model: str
    mcp_server: MCPServerStdio
    session: Optional[SQLiteSession] = None
    container_name: str = "power-system-analysis-container"
    prompt_template: str = (
        "Please answer the following question based on the context provided."
        "If the context is empty, answer the question without it."
        "Question: {question}\nContext:\n{context}"
    )

    def _create_container(self):
        print("Creating a new container...")
        self.container = client.containers.create(name=self.container_name)
        print(f"Container '{self.container.id}' created.")

    def _destroy_container(self):
        if self.container:
            print(f"Destroying container '{self.container.id}'...")
            try:
                client.containers.delete(self.container.id)
                print("Container destroyed.")
            except Exception as e:
                print(f"Could not destroy container: {e}")
            self.container = None

    async def run(self, user_input: str):
        self._create_container()

        @function_tool
        def upload_file_to_container(path: str) -> str:
            """
            Uploads a file from the local filesystem to the container for analysis.
            :param path: Path to the local file to upload.
            """
            return upload_file_to_container_func(self.container.id, path)

        power_system_agent = Agent(
            name="PowerSystemAnalysisAgent",
            model=self.model,
            instructions="""
            You are a power systems analysis expert. Your primary goal is to provide precise, quantitative, and factual answers to user requests by strictly adhering to the following guidelines.
            **Core Directives:**
            1.  **Quantitative & Precise:** Always provide exact numerical values, including totals, minimums, maximums, and averages where applicable. Never omit critical data.
            2.  **Concise & Formatted:** Present data in a structured and clean format. Use Markdown tables for summaries and lists. Avoid verbose, procedural, or conversational text.
            3.  **Fact-Based:** Base all responses directly on the outputs from your tools. Do not add extra explanations or plans unless the tool output is an error.
            4.  **Error Reporting:** If a tool call results in an error (e.g., power flow non-convergence), report the exact error message.
            **Workflow:**
            1.  Analyze the user's request to determine the required tools.
            2.  Silently formulate and execute a step-by-step plan.
            3.  Synthesize the tool outputs into a concise, factual answer that directly addresses the user's query, formatted as requested.
            **Tool Usage:**
            -   `get_network_case`: Fetch standard network cases first.
            -   `mcp_server` tools (`load_network`, `run_power_flow`, etc.): `load_network` is mandatory before any simulation.
            -   `code_interpreter`: For data analysis and file manipulation. Upload files with `upload_file_to_container` before use.
            Execute the full plan and provide a final, data-driven answer in one go.
            """,
            tools=[
                get_network_case,
                upload_file_to_container,
                CodeInterpreterTool(tool_config={"type": "code_interpreter", "container": self.container.id})
            ],
            mcp_servers=[self.mcp_server],
        )

        try:
            result = await Runner.run(power_system_agent, user_input, session=self.session)
            return result
        finally:
            self._destroy_container()


# Example of how to run this simplified agent
async def main():
    """
    Example main function to demonstrate running the PowerSystemAgent.
    This sets up and tears down an MCP server for the agent to use.
    """
    mcp_server = MCPServerStdio(
        name="Pandapower MCP Server",
        params={
            "command": ".venv/bin/python3.12",
            "args": ["/Users/philippebergeron/Documents/Agent_Psse/PowerMCP/pandapower/panda_mcp.py"],
        },
        cache_tools_list=True,
        client_session_timeout_seconds=30,
    )
    await mcp_server.connect()
    try:
        agent = PowerSystemAgent(model="gpt-5-mini", mcp_server=mcp_server)
        user_request = "Run a power flow on case118 and tell me if it converged."
        response = await agent.run(user_request)
        print(response.final_output)
    finally:
        print("Cleaning up MCP server...")
        await mcp_server.cleanup()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
