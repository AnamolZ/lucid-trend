
import asyncio
import logging
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.models.google_llm import Gemini
from google.genai import types

logging.getLogger("google_genai.types").setLevel(logging.ERROR)
logging.getLogger("google_genai").setLevel(logging.ERROR)

class AgentEngine:
    def __init__(self, agent_name, description, instruction, tools, output_key):
        self.retry_config = types.HttpRetryOptions(
            attempts=5,
            exp_base=7,
            initial_delay=1,
            http_status_codes=[429, 500, 503, 504]
        )
        self.agent_name = agent_name
        self.description = description
        self.instruction = instruction
        self.tools = tools
        self.output_key = output_key
        self.agent = None
        self.runner = None

    def agent_creation(self):
        self.agent = Agent(
            name=self.agent_name,
            model=Gemini(
                model="gemini-2.5-flash-lite",
                retry_options=self.retry_config
            ),
            description=self.description,
            instruction=self.instruction,
            tools=self.tools,
            output_key=self.output_key,
        )

    def agent_runner(self):
        if not self.agent:
            raise RuntimeError("Agent not created.")
        self.runner = InMemoryRunner(agent=self.agent, app_name="agents")

    async def agent_response(self, ask: str):
        if not self.runner:
            raise RuntimeError("Runner not initialized.")

        while True:
            try:
                events = await self.runner.run_debug(ask)
                response = ""

                for event in events:
                    if not event.content or not event.content.parts:
                        continue

                    for part in event.content.parts:
                        if hasattr(part, "function_call") and part.function_call:
                            response += f"[FUNCTION_CALL] {part.function_call.name}\n"
                        elif hasattr(part, "tool_response") and part.tool_response:
                            response += f"[TOOL_RESPONSE] OK\n"
                        elif hasattr(part, "text") and part.text:
                            response += part.text

                if response:
                    return response
                
                await asyncio.sleep(1)

            except Exception:
                await asyncio.sleep(2)
                continue