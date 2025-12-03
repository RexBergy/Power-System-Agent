from openai import AsyncOpenAI

class BaseLLM:
    def __init__(self, model: str = "gpt-5"):
        self.client = AsyncOpenAI()
        self.model = model

    async def run(self, input: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": input}
            ],
        )
        return response.choices[0].message.content