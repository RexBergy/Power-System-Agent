from dataclasses import dataclass
from typing import Literal
from agents import Agent, ModelSettings, Runner, function_tool, CodeInterpreterTool, SQLiteSession
import pandapower.networks as pn
import asyncio
from pandapower.networks.power_system_test_cases import case30, case1888rte, case300, case118, case2848rte
from openai.types.shared import Reasoning

from openai import OpenAI
import os
from agents.mcp import MCPServerStdio
import time
from pydantic import BaseModel
import pandapower as pp
    
client = OpenAI()

class AgentSelection(BaseModel):
    type: Literal["case_retrieval", "analysis", "visualization", "diagnostics", "other"]

class Plan(BaseModel):
    steps: list[str]


class AgenticPowerSystem:
    def __init__(self, session: SQLiteSession):

        self.session = session

        self.mcp_server = MCPServerStdio(
            name="Pandapower MCP Server",
            params={"command": ".venv/bin/python3.12",
                    "args": ["/Users/philippebergeron/Documents/Agent_Psse/PowerMCP/pandapower/panda_mcp.py"]
                    },
            cache_tools_list=True,
            client_session_timeout_seconds=30
        )
        
        self.planner_agent = Agent(
            name="Power System Planner Agent",
            model="gpt-5-nano",
            instructions="""Given a user input, create a sequential plan with steps to address the user's request.
            
            Decompose the user input into sub-tasks (1-5 steps) that can be handled by specialized agents.
            The following agents are availble:
            - Case Retrieval Agent: for retrieving pandapower test cases
            - Power Systems Analysis Agent: for powerflow, contingency and timeseries analysis
            - Visualization Agent: for data visulization tasks
            - Diagnostics Agent: for diagnosing issues in power system networks
            - Other Agent: for general power system tasks and broader topics not covered by other agents

            Your output must be a list of steps where give the chossen agent and instruction.
            """,
            output_type=Plan
        )

        self.selection_agent = Agent(
            name="Agent Selection Agent",
            model="gpt-5-nano",
            instructions="""Given a user input, select the most appropriate agent to hadle the request.
            The following agents are availble:
            - Case Retrieval Agent: for retrieving pandapower test cases
            - Power Systems Analysis Agent: for powerflow, contingency and timeseries analysis
            - Visualization Agent: for data visulization tasks
            - Diagnostics Agent: for diagnosing issues in power system networks
            - Other Agent: for general power system tasks and broader topics not covered by other agents
            Your answer must be one of the following:
            'case_retrieval', 'analysis', 'visualization', diagnostics', 'other'.""",
            output_type=AgentSelection
        )

        self.model_router_agent = Agent(
            name="Router Agent",
            model="gpt-5-nano",
            instructions="Decide weather the question is simple, intermediate or complex. Your answer is only either 'gpt-5-nano', gpt-5-mini' or 'gpt-5'." \
            "Example: 'What is the name of the network?' -> 'gpt-5-nano'.",
            output_type=ModelSelection,
        )

        self.analysis_agent = Agent(
            name="Power Systems Analysis Agent",
            model="gpt-5",
            tools=[
                code_interpreter,
                upload_file_to_container
            ],
            instructions=power_agent_instructions,
            mcp_servers=[self.mcp_server],
            model_settings=ModelSettings(reasoning=Reasoning(effort="high")),
        )

        self.case_retrieval_agent = Agent(
            name="Case Retrieval Agent",
            model="gpt-5-nano",
            instructions="""Given a request for a power system test case, retrieve the appropriate pandapower test using the following tool: 
            - get_network_case""",
            tools=[get_network_case]
        )

        self.visualization_agent = Agent(
            name="Visualization Agent",
            model="gpt-5",
            instructions=visualization_agent_instructions,
            tools=[code_interpreter, upload_file_to_container]
        )

        self.diagnostics_agent = Agent(
            name="Diagnostics Agent",
            model="gpt-5",
            instructions=diagnostics_agent_instructions
        )

        self.other_agent = Agent(
            name="Other Agent",
            model="gpt-5",
            instructions=other_agent_instructions
        )

    async def run(self, user_input: str):

        plan = await Runner.run(self.planner_agent, user_input, session=self.session)
        print("Generated Plan: ", plan.final_output.steps)

        for step in plan.final_output.steps:
            print(f"\nExecuting step: {step}")

            selected_agent = await Runner.run(self.selection_agent, step, session=self.session)
            print(f"Selected agent: {selected_agent.final_output.type}")
            selected_agent = selected_agent.final_output.type

            if selected_agent == "case_retrieval":
                agent = self.case_retrieval_agent
            elif selected_agent == "analysis":
                agent = self.analysis_agent
            elif selected_agent == "visualization":
                agent = self.visualization_agent
            elif selected_agent == "diagnostics":
                agent = self.diagnostics_agent
            else:
                agent = self.other_agent

            result = await Runner.run(agent,step, session=self.session)

        return result
############## Router ####################

class ModelSelection(BaseModel):
    model: Literal["gpt-5-nano", "gpt-5-mini", "gpt-5"]




########## Case retrieval #############

@function_tool
def get_network_case(case_name: Literal["case30", "case118", "case300", "case1888rte", "case2848rte"]) -> str:
    """
    Retrieves a predefined pandapower network case by name and saves it to JSON file on the current directory.

    :param case_name: Name of the network case to retrieve ['case30', 'case118', 'case300', 'case1888rte']

    :return: The requested pandapower network object or an error message if the case is not found.
    """
    cases = {
        "case30": case30,
        "case118": case118,
        "case300": case300,
        "case1888rte": case1888rte,
        "case2848rte": case2848rte
    }
    #self.network = cases[case_name]()
    pp.to_json(cases[case_name](), f"{case_name}.json")
    #run_context.context.network_case = case_name
    
    if case_name in cases:
        return f"Network case '{case_name}' loaded and saved to '{case_name}.json'."
    else:
        return f"Case '{case_name}' not found. Available cases: {', '.join(cases.keys())}."





######################## Analysis #########################

@function_tool
def upload_file_to_container(path: str):
    """
    Uploads a file from the local filesystem to the container.

    :param path: Path to the local file to upload.
    """
    print(f"Uploading file '{path}' to container...")
    if os.path.isfile(path):
        created_file = client.containers.files.create(
            container_id=container.id,
            file=open(path, "rb"),
            
        )
        print(f"File '{created_file.path}' uploaded to container.")
        return f"File '{created_file.path}' uploaded to container."
    else:
        return f"File '{path}' does not exist."

container = client.containers.create(name="test-container")

code_interpreter = CodeInterpreterTool(tool_config={"type": "code_interpreter", "container": container.id})

current_directory = os.getcwd()

power_agent_instructions = f"""
System: # Role and Objective
You are a power systems analysis agent specializing in powerflow, contingency and timeseries analysis. Rely exclusively on data provided within this file—do not speculate or fabricate information.

# Workflow
- For topics involving pandapower, electrical grids, power flow calculations, contingency analysis, or similar, utilize the pandapower MCP server tools. These require user files to be present in the local filesystem; if a file is absent, download it first.

# Directories
- Local working directory: `{current_directory}`

# Instructions
1. Begin with a concise checklist (3–7 bullets) of conceptual steps required to address the user's request.
2. Use only these tools: pandapower MCP server tools.
3. When operating with MCP server tools, access files from the local directory. Before any significant tool call, clearly state its purpose and the minimal required inputs.
4. For complex or multi-step queries, decompose the request into sub-questions and reason step by step before coding. Set `reasoning_effort = medium` unless task complexity justifies a different level.
5. Develop and present a structured implementation plan addressing the user's question before starting substantive execution.
6. After each tool call, briefly validate the result (1–2 lines) and determine next steps or self-correct as needed.
7. At key milestones, give succinct (1–3 sentence) progress updates with current status, next steps, and blockers, if any.


# Output Format
Be direct and succinct.
"""




######################## Visualization #####################

visualization_agent_instructions = """
System: Provide accurate and insightful data visualizations for power system analysis using the data provided in the supplied files. Use any suitable visualization libraries. Do not speculate or generate data not present in the files.

# Instructions
1. Load the supplied data files using appropriate libraries (e.g., pandas for CSV files).
2. Analyze the data to identify key trends and insights relevant to power system analysis.
3. Generate relevant visualizations (e.g., line plots, bar charts, heatmaps) using suitable libraries such as matplotlib, seaborn, or plotly.
4. Ensure that all visuals are clearly labeled and include legends or annotations as necessary.
5. Do not generate or speculate data that is not present in the provided files.
"""



################### Diagnostics ###############

diagnostics_agent_instructions = """
System: Diagnose issues in power system networks using the data provided in the supplied files. Use your knowledge of power systems to iddentify
potential problems and suggest solutions. Do not speculate or generate data not present in the files
"""

#################### Other ####################

other_agent_instructions = """
System: Assist with general power system analysis tasks and other user questions on broader topics not covered.
"""



#### Planner Agent ###########


####### Exectuer Agent #########