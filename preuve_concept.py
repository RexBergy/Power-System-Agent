from typing import Any
from agents import Agent, ModelSettings,Runner, WebSearchTool, function_tool, CodeInterpreterTool, SQLiteSession
import pandapower as pp
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

client = OpenAI()

# client.files.create(
#     file=open("/Users/philippebergeron/Documents/Agent_Psse/Power-System-Agent/powerflow_results.json", "rb"),
#     purpose="user_data"
# )
    
container = client.containers.create(name="test-container")

code_interpreter = CodeInterpreterTool(tool_config={"type": "code_interpreter", "container": container.id})




power_agent_instructions = """
Developer: Developer: # Role and Objective
You are a power systems analysis agent dedicated to delivering concise and precise answers to questions involving electrical grids or networks.
Ground your response strictly on the network provided as a json file. Do not make assumptions beyond the data in this file or hallucinate information.

# Instructions
1. Begin with a high-level checklist (3–7 bullets) outlining the conceptual steps required to address the user's question. Keep checklist items at the conceptual level.
2. Use only these tools: the mcp server and the code interpreter. Auto-invoke tools for routine read-only operations; for destructive or irreversible actions, require explicit user confirmation beforehand.
3. State the purpose and minimal required inputs before each significant tool call.
4. Use the code interpreter to run Python code. For simple questions (e.g., network name, number of voltages), answer directly from the dataframe without overcomplicating or additional reasoning. Be clear and concise. When writing code, include relevant visualizations and dataframes (pandas) as appropriate.
5. If necessary, break down complex questions into sub-questions, reasoning stepwise before implementation. Set reasoning_effort = medium unless task complexity is minimal or high.
6. Develop a structured plan to address the user's question before implementation.
7. When further information is required, use available libraries and resources within the code interpreter to provide references or foundational knowledge as needed.
8. At key milestones, provide succinct micro-updates (1–3 sentences) summarizing progress, next steps, and any blockers.

# Output Format
Be cold, concise, and brief. Present final answers using markdown, including relevant tables or plots. Include any executed Python code in block code. Always output the original user question.
"""



class PSSE_Agent:
    def __init__(self, mcp_server: MCPServer):

        self.network : pp.pandapowerNet = None

        self.power_agent = Agent(
            name="Power Systems Analysis Agent",
            model="gpt-5",
            tools=[
    #            self.load_json_network,
  #              self.get_network_case,
                 code_interpreter,
            ],
            instructions=power_agent_instructions,
            mcp_servers=[mcp_server]
  #          model_settings=ModelSettings(reasoning=Reasoning(effort="high"))            
        )

        
    def run(self, question: str):


        pass

    @function_tool
    def get_network_case(self: str,case_name: str) -> pp.pandapowerNet | str:
        """
        Retrieves a predefined pandapower network case by name.

        :param case_name: Name of the network case to retrieve ['case30', 'case118', 'case300', 'case1888rte']

        :return: The requested pandapower network object or an error message if the case is not found.
        """
        cases = {
            "case30": case30,
            "case118": case118,
            "case300": case300,
            "case1888rte": case1888rte
        }

        self.network = cases[case_name]()
        
        if case_name in cases:
            return cases[case_name]()
        else:
            return f"Case '{case_name}' not found. Available cases: {', '.join(cases.keys())}."

    @function_tool
    def run_power_flow(self: str, algorithm: str = 'nr', 
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

        pp.runpp(self.network, algorithm=algorithm, calculate_voltage_angles=calculate_voltage_angles,
                max_iteration=max_iteration, tolerance_mva=tolerance_mva)
        
       
        pass


    @function_tool
    def executer_power(self: str):
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

    async with MCPServerStdio(
        name="Pandapower MCP Server",
        params={"command": "python",
                "args": ["/Users/philippebergeron/Documents/Agent_Psse/PowerMCP/pandapower/panda_mcp.py"]
                },
        cache_tools_list=True
        ) as server:

        

    # Initialisation de l'agent PSSE
        agent = PSSE_Agent(server).power_agent

        # Base directory pour les sauvegardes
        base_directory = "/Users/philippebergeron/Documents/Agent_Psse/Power-System-Agent/conversations/conversation_7/"
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
                user_input + " on powerflow_results.json "
            )

            # Exécution de l'agent
            start_time = time.time()
            result = await Runner.run(agent, modified_question)
            completed_time = time.time() - start_time

            # Affichage du résultat
            print("\n--- Réponse de l'agent ---")
            print(result.final_output)

            # Sauvegarde dans un fichier texte
            question_dir = os.path.join(base_directory, f"Question_{i}")
            os.makedirs(question_dir, exist_ok=True)
            with open(os.path.join(question_dir, "output.txt"), "w") as f:
                f.write(result.final_output + f"\n\n(Temps d'exécution : {completed_time:.2f} secondes)")

            for file in client.containers.files.list(container.id):
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
                for file in client.containers.files.list(container.id):
                    client.containers.files.delete(file_id=file.id, container_id=container.id)
            except Exception as e:
                print(f"(Avertissement : impossible de nettoyer le conteneur — {e})")

            i += 1

if __name__ == "__main__":
    asyncio.run(main())
    client.containers.delete(container_id=container.id)