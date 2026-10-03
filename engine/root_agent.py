"""Root agent coordinator orchestrating subagents into a unified editorial pipeline."""

from google.adk.tools import AgentTool
from config.config import RootAgentConfig
from engine.agent_engine import AgentEngine
from engine.dsearch_engine import DeepSearchEngine
from engine.news_engine import NewsEngine
from config.model_pool import get_active_model

class RootAgentEngine:
    """Coordinates news discovery and investigation subagents under an Editor-in-Chief persona."""

    def __init__(self):
        self.config = RootAgentConfig()
        self.agent_name = self.config.agent_name
        self.description = self.config.description
        self.instruction = self.config.instruction
        self.output_key = self.config.output_key
        self.root_engine = None

    def _build_tools(self, model_name: str = None) -> list:
        research_agent = DeepSearchEngine()
        news_agent = NewsEngine()
        return [
            AgentTool(research_agent.dsearch_agent(model_name=model_name)),
            AgentTool(news_agent.news_agent(model_name=model_name))
        ]

    def _on_failover(self, new_model: str, new_key: str):
        """Reconstructs subagents and coordinator runner when model cascading occurs."""
        tools = self._build_tools(model_name=new_model)
        self.root_engine.tools = tools
        self.root_engine.agent_creation(model_name=new_model)
        self.root_engine.agent_runner()

    def root_agent(self) -> AgentEngine:
        """Assembles and initializes the complete root agent engine."""
        active_model = get_active_model()
        tools = self._build_tools(model_name=active_model)
        self.root_engine = AgentEngine(
            self.agent_name, 
            self.description, 
            self.instruction, 
            tools, 
            self.output_key,
            on_failover=self._on_failover
        )
        self.root_engine.agent_creation(model_name=active_model)
        self.root_engine.agent_runner()
        return self.root_engine