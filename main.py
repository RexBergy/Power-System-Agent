
from agents import  SQLiteSession
from agents.mcp import MCPServerStdio
from power_agents import AgenticPowerSystem, CONTAINER
from power_agents_variant1 import AgenticPowerSystem as AgenticPowerSystemVariant1
from power_agents_variant1 import CONTAINER as CONTAINER_VARIENT1
from agents.extensions.visualization import draw_graph
import asyncio
import time

from openai import OpenAI
import os

dir_path = os.path.dirname(os.path.realpath(__file__))

client = OpenAI()

    
session = SQLiteSession("conversation_40")

async def run_system(agent_system):

    # # Initialisation de l'agent PSSE
    # Base directory pour les sauvegardes

    base_directory = dir_path + "/conversations/conversation_52/"
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
    # result = await orchestrate_question(modified_question)
        result = await agent_system.run(modified_question)
        completed_time = time.time() - start_time

        # Affichage du résultat
        print("\n--- Réponse de l'agent ---")
        print(result.final_output)

        # Sauvegarde dans un fichier texte
        question_dir = os.path.join(base_directory, f"Question_{i}")
        os.makedirs(question_dir, exist_ok=True)
        with open(os.path.join(question_dir, "output.txt"), "w") as f:
            f.write(result.final_output + f"\n\n(Temps d'exécution : {completed_time:.2f} secondes)")

        for file in filter(lambda x: x.id.startswith("cfile") ,client.containers.files.list(CONTAINER_VARIENT1.id)):
            print(f" - {file.path}")

            # Retrieve and save each file to the specific question directory
            destination_path = os.path.join(
                question_dir,
                os.path.basename(file.path)
            )
            client.containers.files.content.retrieve(
                file_id=file.id,
                container_id=CONTAINER_VARIENT1.id
            ).write_to_file(destination_path)

        # Nettoyage éventuel du conteneur si nécessaire
        try:
            for file in filter(lambda x: x.id.startswith("cfile") ,client.containers.files.list(CONTAINER_VARIENT1.id)):
                client.containers.files.delete(file_id=file.id, container_id=CONTAINER_VARIENT1.id)
        except Exception as e:
            print(f"(Avertissement : impossible de nettoyer le conteneur — {e})")

        i += 1

async def test_system(system, question):
    result = await system.run(question)


async def main():
    """
    Boucle de conversation CLI avec le PSSE agent.
    Chaque tour, l'utilisateur entre une question,
    le modèle répond, et on nettoie les fichiers générés.
    """

    async with MCPServerStdio(
            name="Pandapower MCP Server",
            params={"command": ".venv/bin/python3.12",
                    "args": ["/Users/philippebergeron/Documents/Agent_Psse/PowerMCP/pandapower/panda_mcp.py"]
                    },
            cache_tools_list=True,
            client_session_timeout_seconds=30
        ) as mcp_server:

        system = AgenticPowerSystemVariant1(session=session, mcp_server=mcp_server)

        #draw_graph(system.orchestrator_agent, "graph.png")
        

        await run_system(system)
        
async def test(question: str):
    """
    Test function
    """

    

    async with MCPServerStdio(
        name="Pandapower MCP Server",
        params={"command": ".venv/bin/python3.12",
                "args": ["/Users/philippebergeron/Documents/Agent_Psse/PowerMCP/pandapower/panda_mcp.py"]
                },
        cache_tools_list=True,
        client_session_timeout_seconds=30
    ) as mcp_server:

        system = AgenticPowerSystemVariant1(session=None, mcp_server=mcp_server)

        draw_graph(system.orchestrator_agent, "graph.png")

      

if __name__ == "__main__":
    asyncio.run(main())
    client.containers.delete(container_id=CONTAINER_VARIENT1.id)