
from agents import  CodeInterpreterTool, SQLiteSession
from power_agents import AgenticPowerSystem
import asyncio
import time

from openai import OpenAI
import os

client = OpenAI()

    
session = SQLiteSession("conversation_40")
container = client.containers.create(name="test-container")

code_interpreter = CodeInterpreterTool(tool_config={"type": "code_interpreter", "container": container.id})



async def main():
    """
    Boucle de conversation CLI avec le PSSE agent.
    Chaque tour, l'utilisateur entre une question,
    le modèle répond, et on nettoie les fichiers générés.
    """

    system = AgenticPowerSystem(session=session)


    # # Initialisation de l'agent PSSE
        # Base directory pour les sauvegardes
    base_directory = "/Users/philippebergeron/Documents/Agent_Psse/Power-System-Agent/conversations/conversation_41/"
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
        result = await system.run(modified_question)
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