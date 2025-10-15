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
   "Plot all the voltages",
   "Plot all the calculated values by component. Replot using sorted calculated values.",
    "I am interested in the voltage profiles from the generation to the load. Provide plots with the buses ordered by connectivity. Are there any places in the network which the voltage needs to be better supported? Replot the voltages and angles sorted by increasing values."
]




reasoning_questions = [
   "Provide a network summary",
   "Provide a network summary with a statistical analysis.",
   "Show me graphs and tables which would help me better understand the network.",
    "How can I decrease the loading of the most heavily loaded line? Which actions should I perform?",
    "How can I decrease network losses?",
    "What is the weakest part of the network?",
    "If I was to add a voltage support element such as a SVC, where would be the best place to add it?"
]

diagram_questions = [
    "Create a single line diagram of this network identifying each piece of equipment showing relevant calculated values for each type of equipment."
]

all_questions = {
   "general": general_questions,
   "structure": structure_questions,
   "limits": limit_questions,
   "calculations": calculation_questions,
   "plots": plot_qestions,
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
# markdown_agent = Agent(
#     name="Markdown Agent",
#     model="gpt-5",
#     tools=[code_interpreter],
#     instructions=markdown_instruction
#     )

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