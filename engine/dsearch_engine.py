
from config.config import DeepSearchConfig
from engine.agent_engine import AgentEngine

class DeepSearchEngine:
    def __init__(self):
        self.config = DeepSearchConfig()
        self.agent_name = self.config.agent_name
        self.description = self.config.description
        self.instruction = self.config.instruction
        self.tools = list(self.config.tools)
        self.output_key= self.config.output_key

    def dsearch_agent(self):
        dsearch_engine = AgentEngine(
            self.agent_name, 
            self.description, 
            self.instruction, 
            self.tools, 
            self.output_key
        )
        dsearch_engine.agent_creation()
        return dsearch_engine.agent