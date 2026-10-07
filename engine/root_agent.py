"""Root agent coordinator orchestrating real-time discovery and editorial synthesis into a unified pipeline."""

import logging
import asyncio
from config.config import RootAgentConfig
from engine.agent_engine import AgentEngine
from engine.web_scout import fetch_recent_tech_intel, format_intel_dossier
from config.model_pool import get_active_model

logger = logging.getLogger(__name__)

class RootAgentPipeline:
    """Orchestrates 2-Stage Grounded Discovery and Editorial Synthesis with zero rate-limit waste."""

    def __init__(self, root_engine: AgentEngine):
        self.root_engine = root_engine

    def __getattr__(self, name):
        """Proxies any standard AgentEngine properties to the underlying engine."""
        return getattr(self.root_engine, name)

    async def agent_response(self, ask: str) -> str:
        """Executes the 2-Stage Grounded Research & Synthesis Pipeline."""
        logger.info("[RootPipeline] Step 1/2: Scouting verified 24-hour tech breakthroughs...")
        raw_intel = await asyncio.to_thread(fetch_recent_tech_intel, max_items=12)
        dossier = format_intel_dossier(raw_intel)
        logger.info(f"[RootPipeline] Step 1/2 Complete: {len(raw_intel)} verified developments scouted.")

        logger.info("[RootPipeline] Step 2/2: Synthesizing publication-ready articles via Editor-in-Chief...")
        grounded_prompt = (
            f"{dossier}\n\n"
            f"EDITORIAL DIRECTIVE:\n"
            f"{ask}\n\n"
            f"Select the top 2 genuine breakthrough developments from the verified intelligence above "
            f"and synthesize publication-ready articles strictly matching the required JSON schema."
        )

        reply = await self.root_engine.agent_response(grounded_prompt)
        return reply

class RootAgentEngine:
    """Coordinates real-time 24h discovery and editorial synthesis under an Editor-in-Chief persona."""

    def __init__(self):
        self.config = RootAgentConfig()
        self.agent_name = self.config.agent_name
        self.description = self.config.description
        self.instruction = self.config.instruction
        self.output_key = self.config.output_key
        self.root_engine = None

    def root_agent(self) -> RootAgentPipeline:
        """Assembles and initializes the complete 2-stage intelligence pipeline."""
        active_model = get_active_model()
        self.root_engine = AgentEngine(
            self.agent_name, 
            self.description, 
            self.instruction, 
            [], 
            self.output_key
        )
        self.root_engine.agent_creation(model_name=active_model)
        self.root_engine.agent_runner()
        return RootAgentPipeline(self.root_engine)