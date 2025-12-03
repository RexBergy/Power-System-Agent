from typing import Literal, Optional
from agents import Agent, ModelSettings, Runner, function_tool, CodeInterpreterTool, SQLiteSession

from pandapower.networks.power_system_test_cases import case30, case1888rte, case300, case118, case2848rte
from openai.types.shared import Reasoning


from openai import OpenAI
import os
import time
from pydantic import BaseModel
import pandapower as pp

client = OpenAI()

container = client.containers.create(name="test-container")

code_interpreter = CodeInterpreterTool(tool_config={"type": "code_interpreter", "container": container.id})

CONTAINER = container
    
class Step(BaseModel):
    prompt: str

class CaseRetrieval(Step):
    prompt: str

class Upload(Step):
    prompt: str

class Analysis(Step):
    prompt: str

class Pandas(Step):
    prompt: str

class Visualization(Step):
    prompt: str

class Diagnostics(Step):
    prompt: str

class Other(Step):
    prompt: str



class AgentSelection(BaseModel):
    type: Literal["case_retrieval", "upload", "analysis", "pandas" ,"visualization", "diagnostics", "other"]


class Plan(BaseModel):
    steps: list[str]


class AgenticPowerSystem:
    def __init__(self, session: Optional[SQLiteSession], mcp_server):

        self.session = session

        self.mcp_server = mcp_server
        
        

        self.upload_agent = Agent(
            name="Upload Agent",
            model="gpt-5-nano",
            instructions="""
            You are an upload agent specialized in uploading files to the code interpreter container.

            Output the input file path and the upload file path only.
            """,
            tools=[upload_file_to_container]
        )

        self.selection_agent = Agent(
            name="Agent Selection Agent",
            model="gpt-5-nano",
            instructions="""Given a user input, select the most appropriate agent to hadle the request.
            The following agents are availble:
            - Case Retrieval Agent: for retrieving pandapower test cases
            - Upload Agent: for uploading files to the code interpreter container
            - Analysis Agent: for powerflow, contingency and timeseries analysis
            - Pandas Agent: for data manipulation tasks
            - Visualization Agent: for data visulization tasks
            - Diagnostics Agent: for diagnosing issues in power system networks
            - Other Agent: for general power system tasks and broader topics not covered by other agents
            Your answer must be one of the following:
            'case_retrieval', 'upload', 'analysis', 'pandas', 'visualization', diagnostics', 'other'.""",
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
            name="Analysis Agent",
            model="gpt-5",
            instructions=power_agent_instructions,
            mcp_servers=[self.mcp_server],
            model_settings=ModelSettings(reasoning=Reasoning(effort="high")),
        )

        self.pandas_agent = Agent(
            name="Pandas Agent",
            model="gpt-5",
            instructions="""You are a data analysis agent specializing in data manipulation using pandas.
            Before using the code interpreter tool, upload any required data files using the upload_file tool.
            Use the code interpreter tool to execute python code for data analysis tasks.
            
            Upload any required data files using the upload_file_to_container tool before analysis.
            Use the minimal code necessary to perform the analysis requested.
            """,
            tools=[code_interpreter, upload_file_to_container]
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

        self.planner_agent = Agent(
            name="Planner Agent",
            model="gpt-5-nano",
            instructions=f"""Given a user input, create a sequential plan with steps to address the user's request and then execute it.
            
            Decompose the user input into sub-tasks (1-7 steps) that can be handled by specialized agents.
            The following agents are availble:
            - Case Retrieval Agent: for retrieving pandapower test cases. (Instructions: 
                Given a request for a power system test case, retrieve the appropriate pandapower test using the following tool: 
                    - get_network_case
            )   
            - Upload Agent: for uploading files to the code interpreter container. (Instructions: 
                You are an upload agent specialized in uploading files to the code interpreter container.
                Output the input file path and the upload file path only.
                )
            - Analysis Agent: only for powerflow, contingency and timeseries analysis only. ( Instructions: {power_agent_instructions} )
                Results are written to json files. Upload them to further work with them.
            - Pandas Agent: for data manipulation tasks. Needs to upload data files before code interpretor. ( Instructions:
                You are a data analysis agent specializing in data manipulation using pandas.
                Before using the code interpreter tool, upload any required data files using the upload_file tool.
                Use the code interpreter tool to execute python code for data analysis tasks.
                
                Upload any required data files using the upload_file_to_container tool before analysis.
                Use the minimal code necessary to perform the analysis requested.
                )
            - Visualization Agent: for data visulization tasks. Needs to upload data files before code interpretor. (Instructions: {visualization_agent_instructions} )
            - Diagnostics Agent: for diagnosing issues in power system networks. ( Instructions: {diagnostics_agent_instructions})
            - Other Agent: for general power system tasks and broader topics not covered by other agents. ( Instructions: {other_agent_instructions})

            Ensure that everytime a file is created or needed, you upload it using the upload agent.

            Each step must be the prompt you will give to the chosen agent to handle that step.

            Example input: "I want to plot the voltage levels of case30."
            Example ouput: [
            Case Retrieval Agent: "Retrieve the pandapower test case 'case30' using the get_network_case_tool",
            Pandapower Analysis Agent: "Run a power flow analysis on the retrieved 'case30' network using the pandapower mcp server tools, save the results in a different jsno filename."
            Upload Agent: "Upload the saved json file to the code interpreter container using the upload_file_to_container tool",
            Pandas Agent: "Load the uploaded json file and extract the voltage levels data using pandas and plot it using matplotlib in the code interpreter tool."
            ]

            Your output must be the plan
            """,
            
          #  output_type=Plan
        )


        self.orchestrator_agent = Agent(
            name="Power System Orchestrator Agent",
            model="gpt-5",
            instructions=f"""You are an orchestrator agent that responds to user inputs in power systems analysis.
            Try to answer yourself. If you can't, create a plan with the planner agent and execute it step by step using the specialized agents available.

            Specialized agents available:
                - Planner Agent: for creating a sequential plan to address the user's request with the agents below
                - Case Retrieval Agent: for retrieving pandapower test cases. (Instructions: 
                Given a request for a power system test case, retrieve the appropriate pandapower test using the following tool: 
                    - get_network_case
                )   
                - Upload Agent: for uploading files to the code interpreter container. (Instructions: 
                    You are an upload agent specialized in uploading files to the code interpreter container.
                    Output the input file path and the upload file path only.
                    )
                - Analysis Agent: only for powerflow, contingency and timeseries analysis only. ( Instructions: {power_agent_instructions} )
                    Results are written to json files. Upload them to further work with them.
                - Pandas Agent: for data manipulation tasks. Needs to upload data files before code interpretor. ( Instructions:
                    You are a data analysis agent specializing in data manipulation using pandas.
                    Before using the code interpreter tool, upload any required data files using the upload_file tool.
                    Use the code interpreter tool to execute python code for data analysis tasks.
                    
                    Upload any required data files using the upload_file_to_container tool before analysis.
                    Use the minimal code necessary to perform the analysis requested.
                    )
                - Visualization Agent: for data visulization tasks. Needs to upload data files before code interpretor. (Instructions: {visualization_agent_instructions} )
                - Diagnostics Agent: for diagnosing issues in power system networks. ( Instructions: {diagnostics_agent_instructions})
                - Other Agent: for general power system tasks and broader topics not covered by other agents. ( Instructions: {other_agent_instructions})

            When executing a plan step by step clearly state which step you are executing.

            ### Always execute your plan. Do not ask or do follow ups. Do it and give the answer.
            """,
            tools=[
                self.planner_agent.as_tool(
                    tool_name="planner_agent",
                    tool_description="For creating a sequential plan to address the user's request with the agents below"
                ),
                self.pandas_agent.as_tool(
                    tool_name="pandas_agent",
                    tool_description="For data manipulation tasks. Needs to upload data files before code interpretor"
                    
                ), 
                self.visualization_agent.as_tool(
                    tool_name="visualization_agent",
                    tool_description="For data visulization tasks. Needs to upload data files before code interpretor"

                ), 
                self.analysis_agent.as_tool(
                    tool_name="analysis_agent",
                    tool_description="Only for powerflow, contingency and timeseries analysis only"

                ), 
                self.case_retrieval_agent.as_tool(
                    tool_name="case_retrieval_agent",
                    tool_description="For retrieving pandapower test cases"

                ), 
                self.upload_agent.as_tool(
                    tool_name="upload_agent",
                    tool_description="For uploading files to the code interpreter container"

                ), 
                self.diagnostics_agent.as_tool(
                    tool_name="diagnostics_agent",
                    tool_description="For diagnosing issues in power system networks."

                ), 
                self.other_agent.as_tool(
                    tool_name="other_agent",
                    tool_description="For general power system tasks and broader topics not covered by other agents"

                )
            ]
        )

        

    async def run(self, user_input: str):

        plan = await Runner.run(self.orchestrator_agent, user_input, session=self.session)
   
        return plan
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
        return f"Network case '{case_name}' fetched and saved to '{case_name}.json'. UPLOAD THIS FILE TO THE CONTAINER BEFORE USING."
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


### Que reste-t-il a faire

# Il reste a enregistrer les resultats, je dois avoir plus de questions aussi 
# la bonne chose cest que jai les resultats dans confidant AI
# Il faudrait que je mette en place un systeme de base, un plus complexe et le mien