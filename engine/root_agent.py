from google.adk.tools import AgentTool
from config.config import RootAgentConfig
from engine.agent_engine import AgentEngine
from engine.dsearch_engine import DeepSearchEngine
from engine.news_engine import NewsEngine

class RootAgentEngine:
    def __init__(self):
        self.config = RootAgentConfig()
        self.research_agent = DeepSearchEngine()
        self.news_agent = NewsEngine()
        self.agent_name = self.config.agent_name
        self.description = self.config.description
        self.instruction = self.config.instruction
        self.tools = [
            AgentTool(self.research_agent.dsearch_agent()), 
            AgentTool(self.news_agent.news_agent())
        ]
        self.output_key= self.config.output_key

    async def root_agent(self):
        root_engine = AgentEngine(
            self.agent_name, 
            self.description, 
            self.instruction, 
            self.tools, 
            self.output_key
        )
        root_engine.agent_creation()
        root_engine.agent_runner()
        root_engine_response = await root_engine.agent_response("Fetch the most recent important tech news from the past 24 hours, perform a deep-dive investigation into the most recent tech news for a provided headlines")
        return root_engine_response