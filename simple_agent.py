import asyncio
from typing import Optional
from agents import Agent, Runner, SQLiteSession


class SimpleAgent:
    def __init__(self, session: Optional[SQLiteSession]):

        self.session = session


        self.agent = Agent(name="Power Systems Agent",
                           instructions="""You are a helpfull one shot power systems agent. 
                           Answer as concisely and precisely as possible""")
        
    async def run(self, user_input: str):

        answer = await Runner.run(self.agent, user_input, session=self.session)

        return answer
        

if __name__ == "__main__":
    enter = input("Question: ")
    answer = asyncio.run(SimpleAgent(None).run(enter))
    print(answer.final_output)
