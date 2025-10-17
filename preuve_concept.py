from dataclasses import dataclass
from typing import Any, Literal
from agents import Agent, ModelSettings, RunContextWrapper,Runner, WebSearchTool, function_tool, CodeInterpreterTool, SQLiteSession, FileSearchTool
import pandapower.networks as pn
import asyncio
from pandapower.networks.power_system_test_cases import case30, case1888rte, case300, case118
from openai.types.shared import Reasoning

from pandapower.file_io import to_json
import json as js
from openai import OpenAI
import shutil
import os
from agents.mcp import MCPServer, MCPServerStdio
import time
from pydantic import BaseModel
import pandapower as pp

client = OpenAI()

# client.files.create(
#     file=open("/Users/philippebergeron/Documents/Agent_Psse/Power-System-Agent/powerflow_results.json", "rb"),
#     purpose="user_data"
# )
    
session = SQLiteSession("conversation_14")
container = client.containers.create(name="test-container")
# client.files.create(
#     file=open('case.json', 'rb'),
#     purpose="user_data"
# )
# client.containers.files.create(
#     container_id=container.id,
#     file=open("/Users/philippebergeron/Documents/Agent_Psse/Power-System-Agent/case.json", "rb")
#     )

code_interpreter = CodeInterpreterTool(tool_config={"type": "code_interpreter", "container": container.id})

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
        
        return f"File '{created_file.path}' uploaded to container."
    else:
        return f"File '{path}' does not exist."
current_directory = os.getcwd()

power_agent_instructions = f"""
Developer: Developer: # Role and Objective
You are a power systems analysis agent dedicated to delivering concise and precise answers to questions involving electrical grids or networks. Do not make assumptions beyond the data in this file or hallucinate information.

# Workflow
For anything related to pandapower, electrical grids, power flow calculation, contingency analysis, or similar topics, use the pandapower MCP server tools provided. Use user local files, meaning you juat need to download it if not found.
For programming tasks, data analysis, or file manipulations, use the code interpreter tool. Therefore, you need to upload a local user file to the container. If not found, download it.

# Local directory
{current_directory}

# Container directory
/mnt/data/

# Instructions
1. Begin with a high-level checklist (3–7 bullets) outlining the conceptual steps required to address the user's question. Keep checklist items at the conceptual level.
2. Use only these tools: the pandapower mcp server tools, get_network_case, upload_file_to_container and the code interpreter. Auto-invoke tools for routine read-only operations; for destructive or irreversible actions, require explicit user confirmation beforehand.
3. Make sure to use local files (i.e not in container) with the mcp server tools. With the code interpreter, you can use files in the container.
4. State the purpose and minimal required inputs before each significant tool call.
5. Use the code interpreter to run Python code. For simple questions (e.g., network name, number of voltages).
    Be clear and concise. When writing code, include relevant visualizations and dataframes (pandas) as appropriate.
    If working with files, they need to be in the container.
6. If necessary, break down complex questions into sub-questions, reasoning stepwise before implementation. Set reasoning_effort = medium unless task complexity is minimal or high.
7. Develop a structured plan to address the user's question before implementation.
8. When further information is required, use available libraries and resources within the code interpreter to provide references or foundational knowledge as needed.
9. At key milestones, provide succinct micro-updates (1–3 sentences) summarizing progress, next steps, and any blockers.

# Output Format
Be cold, concise, and brief. Present final answers using markdown, including relevant tables or plots. Always output the original user question.
"""

class ModelSelection(BaseModel):
    model: Literal["gpt-5-nano", "gpt-5-mini", "gpt-5"]

@dataclass
class UserContext:
    network_case: Literal["case30", "case118", "case300", "case1888rte"]


# class PSSE_Agent:
#     def __init__(self, mcp_server: MCPServer):


#         self.router_agent = Agent[UserContext](
#             name="Router Agent",
#             model="gpt-5-nano",
#             instructions="Decide weather the question is simple, intermediate or complex. Your answer is only either 'gpt-5-nano', gpt-5-mini' or 'gpt-5'." \
#             "Example: 'What is the name of the network?' -> 'gpt-5-nano'.",
#             output_type=ModelSelection,
#         )

#         self.mcp_server = mcp_server
     
router_agent = Agent(
    name="Router Agent",
    model="gpt-5-nano",
    instructions="Decide weather the question is simple, intermediate or complex. Your answer is only either 'gpt-5-nano', gpt-5-mini' or 'gpt-5'." \
    "Example: 'What is the name of the network?' -> 'gpt-5-nano'.",
    output_type=ModelSelection,
)
     
async def run(question: str):
    """

    """
    result = await Runner.run(router_agent, question)
    print("Selected model:", result.final_output)
    async with MCPServerStdio(
        name="Pandapower MCP Server",
        params={"command": ".venv/bin/python3.12",
                "args": ["/Users/philippebergeron/Documents/Agent_Psse/PowerMCP/pandapower/panda_mcp.py"]
                },
        cache_tools_list=True,
        client_session_timeout_seconds=30
        ) as server:

        power_agent = Agent(
            name="Power Systems Analysis Agent",
            model=result.final_output.model,
            tools=[
                code_interpreter,
                upload_file_to_container,
                get_network_case
            ],
            instructions=power_agent_instructions,
            mcp_servers=[server],
            model_settings=ModelSettings(reasoning=Reasoning(effort="high")),
        )
        result = await Runner.run(power_agent, question, session=session)

    return result

@function_tool
def get_network_case(
                    case_name: Literal["case30", "case118", "case300", "case1888rte"]) -> str:
    """
    Retrieves a predefined pandapower network case by name and saves it to JSON file on the current directory.

    :param case_name: Name of the network case to retrieve ['case30', 'case118', 'case300', 'case1888rte']

    :return: The requested pandapower network object or an error message if the case is not found.
    """
    cases = {
        "case30": case30,
        "case118": case118,
        "case300": case300,
        "case1888rte": case1888rte
    }
    #self.network = cases[case_name]()
    pp.to_json(cases[case_name](), f"{case_name}.json")
    #run_context.context.network_case = case_name
    
    if case_name in cases:
        return f"Network case '{case_name}' loaded and saved to '{case_name}.json'."
    else:
        return f"Case '{case_name}' not found. Available cases: {', '.join(cases.keys())}."

@function_tool
def run_power_flow(run_context: RunContextWrapper[UserContext],
                    algorithm: str = 'nr', 
                    calculate_voltage_angles: bool = True, 
                    max_iteration: int = 10, 
                    tolerance_mva: float = 1e-8):
    """
    Executes a power flow calculation on the current network/grid.
    :param algorithm: Power flow algorithm ('nr' for Newton-Raphson, 'bfsw' for backward/forward sweep)
    :param calculate_voltage_angles: Whether to calculate voltage angles.
    :param max_iteration: Maximum number of iterations for the power flow calculation.
    :param tolerance_mva: Convergence tolerance in MVA.
    """
    network = run_context.context.network_case
    pp.runpp(network,algorithm=algorithm, calculate_voltage_angles=calculate_voltage_angles,
            max_iteration=max_iteration, tolerance_mva=tolerance_mva)
    
    
    pass


@function_tool
def executer_power():
    """
    Executes a power flow calculation on a network/grid and saves the results to a JSON file.

    :return: Success message with the path to the saved file.
    """
    output_path = "/Users/philippebergeron/Documents/Agent_Psse/Power-System-Agent/powerflow_results.json"
    print("Running power flow calculation...", output_path)
    net = case30()
    pp.run.runpp(net)
    if net.converged:
        to_json(net, output_path)
        return f"Power flow calculation successful. Results saved to {output_path}."
    else:
        return "Power flow calculation did not converge."
    


    
@function_tool  
def load_json_network(self: str,file_path: str):
    """
    Loads power flow results from a JSON file and returns a dataframe object.
    :param file_path: Path to the JSON file containing the network.

    :return: Pandapower network object as dataframes.
    """
    print("Loading results from ...", file_path)
    with open(file_path, 'r') as f:
        df = js.load(f)
    if df is not None:
        
        return df
    else:
        return "Failed to load network from JSON."


async def main():
    """
    Boucle de conversation CLI avec le PSSE agent.
    Chaque tour, l'utilisateur entre une question,
    le modèle répond, et on nettoie les fichiers générés.
    """

    # async with MCPServerStdio(
    #     name="Pandapower MCP Server",
    #     params={"command": ".venv/bin/python3.12",
    #             "args": ["/Users/philippebergeron/Documents/Agent_Psse/PowerMCP/pandapower/panda_mcp.py"]
    #             },
    #     cache_tools_list=True
    #     ) as server:


    current_directory = os.getcwd()

    # # Initialisation de l'agent PSSE
    #     agent = PSSE_Agent(server)

        # Base directory pour les sauvegardes
    base_directory = "/Users/philippebergeron/Documents/Agent_Psse/Power-System-Agent/conversations/conversation_25/"
    os.makedirs(base_directory, exist_ok=True)

    print("=== Conversation avec le PSSE Agent ===")
    print("Tape 'exit' pour quitter.\n")

    i = 1  # compteur de questions

    while True:
        # Lecture de la question
        user_input = input(f"\nQuestion {i}: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("\nConversation terminée.")
            break

        # Ajout d'une instruction de sauvegarde pour le power flow
        modified_question = (
            user_input 
        )

        # Exécution de l'agent
        start_time = time.time()
        #   result = await Runner.run(agent, modified_question, session=session)
        result = await run(modified_question)
        completed_time = time.time() - start_time

        # Affichage du résultat
        print("\n--- Réponse de l'agent ---")
        print(result.final_output)

        # Sauvegarde dans un fichier texte
        question_dir = os.path.join(base_directory, f"Question_{i}")
        os.makedirs(question_dir, exist_ok=True)
        with open(os.path.join(question_dir, "output.txt"), "w") as f:
            f.write(result.final_output + f"\n\n(Temps d'exécution : {completed_time:.2f} secondes)")

        for file in filter(lambda x: x.id.startswith("cfile") ,client.containers.files.list(container.id)):
            print(f" - {file.path}")

            # Retrieve and save each file to the specific question directory
            destination_path = os.path.join(
                question_dir,
                os.path.basename(file.path)
            )
            client.containers.files.content.retrieve(
                file_id=file.id,
                container_id=container.id
            ).write_to_file(destination_path)

        # Nettoyage éventuel du conteneur si nécessaire
        try:
            for file in filter(lambda x: x.id.startswith("cfile") ,client.containers.files.list(container.id)):
                client.containers.files.delete(file_id=file.id, container_id=container.id)
        except Exception as e:
            print(f"(Avertissement : impossible de nettoyer le conteneur — {e})")

        i += 1

if __name__ == "__main__":
    asyncio.run(main())
    client.containers.delete(container_id=container.id)