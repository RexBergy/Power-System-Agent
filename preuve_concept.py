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

    
session = SQLiteSession("conversation_14")
container = client.containers.create(name="test-container")

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
        print(f"File '{created_file.path}' uploaded to container.")
        return f"File '{created_file.path}' uploaded to container."
    else:
        return f"File '{path}' does not exist."
    

# def timeseries():
#     # load a pandapower network
#     #net = mv_oberrhein(scenario='generation')
#     # number of time steps
#     n_ts = 95
#     # load your timeseries from a file (here csv file)
#     # df = pd.read_csv("sgen_timeseries.csv")
#     # or create a DataFrame with some random time series as an example
#     df = pd.DataFrame(np.random.normal(1., 0.1, size=(n_ts, len(net.sgen.index))),
#                     index=list(range(n_ts)), columns=net.sgen.index) * net.sgen.p_mw.values
#     # create the data source from it
#     ds = DFData(df)

#     # initialising ConstControl controller to update values of the regenerative generators ("sgen" elements)
#     # the element_index specifies which elements to update (here all sgens in the net since net.sgen.index is passed)
#     # the controlled variable is "p_mw"
#     # the profile_name are the columns in the csv file (here this is also equal to the sgen indices 0-N )
#     const_sgen = ConstControl(net, element='sgen', element_index=net.sgen.index,
#                             variable='p_mw', data_source=ds, profile_name=net.sgen.index)

#     # do the same for loads
#     # df = pd.read_csv("load_timeseries.csv")
#     # create a DataFrame with some random time series as an example
#     df = pd.DataFrame(np.random.normal(1., 0.1, size=(n_ts, len(net.load.index))),
#                     index=list(range(n_ts)), columns=net.load.index) * net.load.p_mw.values
#     ds = DFData(df)
#     const_load = ConstControl(net, element='load', element_index=net.load.index,
#                             variable='p_mw', data_source=ds, profile_name=net.load.index)

#     # starting the timeseries simulation for one day -> 96 15 min values.
#     run_timeseries(net)

current_directory = os.getcwd()

power_agent_instructions = f"""
System: # Role and Objective
You are a power systems analysis agent dedicated to providing concise, accurate answers for queries related to electrical grids or networks. Rely exclusively on data provided within this file—do not speculate or fabricate information.

# Workflow
- For topics involving pandapower, electrical grids, power flow calculations, contingency analysis, or similar, utilize the pandapower MCP server tools. These require user files to be present in the local filesystem; if a file is absent, download it first.
- For coding, data analysis, or file manipulation tasks, use the code interpreter. It requires files to be located in the container directory. If the file is not present, download it locally, then upload it to the container before use.

# Directories
- Local working directory: `{current_directory}`
- Container working directory: `/mnt/data/`

# Instructions
1. Begin with a concise checklist (3–7 bullets) of conceptual steps required to address the user's request.
2. Use only these tools: pandapower MCP server tools, get_network_case, upload_file_to_container, and the code interpreter. Routine read-only tool operations can be auto-invoked; for destructive or irreversible actions, obtain explicit user confirmation before proceeding.
3. When operating with MCP server tools, access files from the local directory. For the code interpreter, use files from the container directory. Before any significant tool call, clearly state its purpose and the minimal required inputs.
4. Execute Python code strictly within the code interpreter. For simple queries (e.g., network name, voltage count), provide direct, clear responses. When writing code, include relevant visualizations and dataframes (using pandas) as needed. Ensure all required files are present in the container directory before code execution. Do not use pandapower.
5. For complex or multi-step queries, decompose the request into sub-questions and reason step by step before coding. Set `reasoning_effort = medium` unless task complexity justifies a different level.
6. Develop and present a structured implementation plan addressing the user's question before starting substantive execution.
7. Use available libraries and resources within the code interpreter, offering references or foundational concepts as needed.
8. After each tool call or code edit, briefly validate the result (1–2 lines) and determine next steps or self-correct as needed.
9. At key milestones, give succinct (1–3 sentence) progress updates with current status, next steps, and blockers, if any.

# Example
User: I want to plot voltage levels on "network.json"

System steps:
- Fetch the network.
- Run a power analysis (using the local file with MCP server).
- Save the updated network.
- Upload the network to the container.
- Use the code interpreter to open the network in the container and plot voltage levels.

# Output Format
Be direct and succinct. Deliver final answers using markdown, with tables or plots as appropriate. Always quote the user question in your output.
"""

class ModelSelection(BaseModel):
    model: Literal["gpt-5-nano", "gpt-5-mini", "gpt-5"]

@dataclass
class UserContext:
    network_case: Literal["case30", "case118", "case300", "case1888rte", "case2848rte"]

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
                    case_name: Literal["case30", "case118", "case300", "case1888rte", "case2848rte"]) -> str:
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




async def main():
    """
    Boucle de conversation CLI avec le PSSE agent.
    Chaque tour, l'utilisateur entre une question,
    le modèle répond, et on nettoie les fichiers générés.
    """



    current_directory = os.getcwd()

    # # Initialisation de l'agent PSSE
        # Base directory pour les sauvegardes
    base_directory = "/Users/philippebergeron/Documents/Agent_Psse/Power-System-Agent/conversations/conversation_39/"
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