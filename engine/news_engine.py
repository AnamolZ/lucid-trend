
from config.config import NewsEngineConfig
from engine.agent_engine import AgentEngine

class NewsEngine:
    def __init__(self):
        self.config = NewsEngineConfig()
        self.agent_name = self.config.agent_name
        self.description = self.config.description
        self.instruction = self.config.instruction
        self.tools = list(self.config.tools)
        self.output_key= self.config.output_key

    def news_agent(self):
        news_engine = AgentEngine(
            self.agent_name, 
            self.description, 
            self.instruction, 
            self.tools, 
            self.output_key
        )
        news_engine.agent_creation()
        return news_engine.agent