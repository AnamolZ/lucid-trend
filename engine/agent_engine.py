
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.models.google_llm import Gemini
from google.genai import types

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
        agent_reply = await self.runner.run_debug(ask)
        response = ""

        if isinstance(agent_reply, list):
            for event in agent_reply:
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response = part.text
        return response