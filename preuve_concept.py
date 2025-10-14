from typing import Any
from agents import Agent, ModelSettings,Runner, WebSearchTool, function_tool, CodeInterpreterTool
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

client = OpenAI()


    
container = client.containers.create(name="test-container")

code_interpreter = CodeInterpreterTool(tool_config={"type": "code_interpreter", "container": container.id})




power_agent_instructions = """
Developer: Developer: # Role and Objective
You are a power systems analysis agent dedicated to delivering concise and precise answers to questions involving electrical grids or networks.
Ground your response strictly on the network provided as a json file. Do not make assumptions beyond the data in this file or hallucinate information.

# Instructions
1. Begin with a high-level checklist (3–7 bullets) outlining the conceptual steps required to address the user's question. Keep checklist items at the conceptual level.
2. Use only these tools: 'load_json_network', and the code interpreter. Auto-invoke tools for routine read-only operations; for destructive or irreversible actions, require explicit user confirmation beforehand.
3. State the purpose and minimal required inputs before each significant tool call.
4. Use the code interpreter to run Python code. For simple questions (e.g., network name, number of voltages), answer directly from the dataframe without overcomplicating or additional reasoning. Be clear and concise. When writing code, include relevant visualizations and dataframes (pandas) as appropriate.
5. Never open or load a file in the code interpreter; always use the provided tool `load_json_network` to load the network from a json file.
6. If necessary, break down complex questions into sub-questions, reasoning stepwise before implementation. Set reasoning_effort = medium unless task complexity is minimal or high.
7. Develop a structured plan to address the user's question before implementation.
8. After each tool call, validate the result in 1–2 sentences. If results do not meet success criteria, attempt a minimal correction or clarify assumptions before proceeding.
9. When further information is required, use available libraries and resources within the code interpreter to provide references or foundational knowledge as needed.
10. At key milestones, provide succinct micro-updates (1–3 sentences) summarizing progress, next steps, and any blockers.
11. You can use local path for the network since 'load_json_network' tool will be used on the local path.

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
        

        
    
user_question = "Which transmission lines are in parallel. Do they have similar line loading? If not, why not?"

general_questions = [
    "What is the name of the network?",
    "Provide a summary of all types in the network and the number of each component.",
    "How many different voltage levels are there? What are they?",
    "What is the total generation and loads?",
    "List all the buses with their characteristics.",
    "List all the transformers with their characteristics.",
    "List all the lines with their characteristics.",
    "List all the loads with their characteristics.",
    "List all the shunts with their characteristics.",
    "List all the equipment with their characteristics.",
    "Which equipment is out of service.",
    "What is the total generation that is available either out of service or generators that are not at their maximum capacity. What is the total generation, loads? Subtotal this by regions or zones.",
    "How many voltage levels are there in the network? Provide a table sorted by increasing voltage with the number of each type of component.",
    "Are there any transformers? What types are they? List them by type and by increasing base voltage with their tap positions.",
    "How many generators are there? Provide a graph showing their power generation and controlled bus voltage. Indicate if the controlled buses are local to the generator or are controlling a remote bus."

]


structure_questions = [
    "Which components are attached to bus 2? How many electrical components are attached to each bus?",
    "Which components are attached to each generator bus?",
    "Are there multiple components attached to each bus?",
    "Where are the shunt elements located? Are they near loads or generators?",
    "Identify which components are in parallel. Which components are in series?",
    "Which transmission lines are in parallel. Do they have similar line loading? If not, why not?",
    "Are there any islanded elements in my network? How many sub-networks are there? Are they synchronous?",
    "What are all the variables that are calculated in the powerflow by type of equipment?"
]



limit_questions = [
    "Show all the generators which are hitting their maximum or minimum VAR limit. Identify any shunt elements which are in proximity to the generators that are hitting their VAR limits.",
    "Verify if there are any data values which are outside of their normal ranges for each component. List all the equipment and their parameters which are considered out of range.",
    "Are the transmission line impedances within a normal range? Based on the line charging, are these transmission lines short or long?"
]




calculation_questions = [
    "What are the network losses? Describe two ways to calculate the losses. Show the losses by equipment type and then by voltage range.",
    "Draw a graph of the percentage loading of each line.",
    "Calculate the average voltages and show this in the normal bus range. What are the averages and standard deviation. Recalculate the bus voltage averages in kV grouped by their base voltages. Calculate a histogram of the voltages.",
    "Provide a new datafile with the loads increased by 5%. What are the new network losses?",
    "Calculate the real and reactive voltages of each bus in pu and kV.",
    "What is the loading of each generator in real and reactive power using actual values and percent loading? Do a statistical analysis of the powers grouped by topology, voltage level and size of generator.",
    "Are the voltages of lines that are the most loaded higher or lower than the average voltages for each voltage level."
]




plot_qestions = [
 #   "Plot all the voltages",
 #   "Plot all the calculated values by component. Replot using sorted calculated values.",
    "I am interested in the voltage profiles from the generation to the load. Provide plots with the buses ordered by connectivity. Are there any places in the network which the voltage needs to be better supported? Replot the voltages and angles sorted by increasing values."
]




reasoning_questions = [
 #   "Provide a network summary",
#    "Provide a network summary with a statistical analysis.",
#    "Show me graphs and tables which would help me better understand the network.",
    "How can I decrease the loading of the most heavily loaded line? Which actions should I perform?",
    "How can I decrease network losses?",
#    "What is the weakest part of the network?",
    "If I was to add a voltage support element such as a SVC, where would be the best place to add it?"
]

diagram_questions = [
    "Create a single line diagram of this network identifying each piece of equipment showing relevant calculated values for each type of equipment."
]

all_questions = {
#    "general": general_questions,
#    "structure": structure_questions,
#    "limits": limit_questions,
#    "calculations": calculation_questions,
#    "plots": plot_qestions,
    "reasoning": reasoning_questions,
    "diagrams": diagram_questions
}
markdown_instruction = """
# Role and objective
You are a mardown file agent. Your objective is to write a markdown file that include all the relevent information.
# Instructions
Use the code interpreter tool to generate the markdon file.
You will receive the response from the power systems analysis agent.
Only include the answer or result to the question asked initially in the markdown file. Include the user question as well.
Include any tables, plots or code that was used to generate the results. The linked filees should be located in the same directory as the markdown file.
"""
markdown_agent = Agent(
    name="Markdown Agent",
    model="gpt-5",
    tools=[code_interpreter],
    instructions=markdown_instruction
    )

# async def main():
#     """
#     Main asynchronous function that iterates through different question types,
#     runs a power system analysis agent on each question, and saves the results
#     and generated files in organized folders.
#     """

#     # Initialize the PSSE agent (power systems simulation agent)
#     agent = PSSE_Agent().power_agent

#     # Base directory where all results will be stored
#     base_directory = "/Users/philippebergeron/Documents/Agent_Psse/Power-System-Agent/questions/iteration 22/"

#     # Loop through all question types and their corresponding question lists
#     for question_type, questions in all_questions.items():
#         # Create a directory for each question type
#         question_type_dir = os.path.join(base_directory, question_type)
#         os.makedirs(question_type_dir, exist_ok=True)
#         print(f"\n--- {question_type.upper()} QUESTIONS ---")

#         # Iterate through each question in the current type
#         for i, question in enumerate(questions, start=1):
#             print(f"\nQuestion {i}: {question}")

#             # Create a directory for each specific question
#             specific_question_dir = os.path.join(question_type_dir, f"Question {i}")
#             os.makedirs(specific_question_dir, exist_ok=True)

#             # Append instruction to save power flow results to a specific file
#             modified_question = (
#                 question + " on the following json file: /Users/philippebergeron/Documents/Agent_Psse/Power-System-Agent/powerflow_results.json"
#             )

#             # Run the agent asynchronously and get the result
#             result = await Runner.run(agent, modified_question)

#             # Print and save the final output text
#             print(result.final_output)
#             # output_path = os.path.join(specific_question_dir, "output.txt")
#             # with open(output_path, "w") as file:
#             #     file.write(result.final_output)

#             await Runner.run(markdown_agent, result.final_output)

#             # List all files created by the container and retrieve their contents
#             print("\nFiles generated in the container:")
#             for file in client.containers.files.list(container.id):
#                 print(f" - {file.path}")

#                 # Retrieve and save each file to the specific question directory
#                 destination_path = os.path.join(
#                     specific_question_dir,
#                     os.path.basename(file.path)
#                 )
#                 client.containers.files.content.retrieve(
#                     file_id=file.id,
#                     container_id=container.id
#                 ).write_to_file(destination_path)

#             # Clean container files before each question
#             for file in client.containers.files.list(container.id):
#                 client.containers.files.delete(file_id=file.id, container_id=container.id)

#             print("\n")  # Separate questions visually in logs

    

# if __name__ == "__main__":
#     asyncio.run(main())

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
        base_directory = "/Users/philippebergeron/Documents/Agent_Psse/Power-System-Agent/conversations/conversation_4/"
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
                user_input + " on the following json file: "
                "/Users/philippebergeron/Documents/Agent_Psse/Power-System-Agent/powerflow_results.json"
            )

            # Exécution de l'agent
            result = await Runner.run(agent, modified_question)

            # Affichage du résultat
            print("\n--- Réponse de l'agent ---")
            print(result.final_output)

            # Sauvegarde dans un fichier texte
            question_dir = os.path.join(base_directory, f"Question_{i}")
            os.makedirs(question_dir, exist_ok=True)
            with open(os.path.join(question_dir, "output.txt"), "w") as f:
                f.write(result.final_output)

            # Nettoyage éventuel du conteneur si nécessaire
            try:
                for file in client.containers.files.list(container.id):
                    client.containers.files.delete(file_id=file.id, container_id=container.id)
            except Exception as e:
                print(f"(Avertissement : impossible de nettoyer le conteneur — {e})")

            i += 1

if __name__ == "__main__":
    asyncio.run(main())