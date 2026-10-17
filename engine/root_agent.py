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

    async def agent_response(self, ask: str, category_key: str = "Technology", exclusions: list = None) -> str:
        """Executes the Category-Targeted 2-Stage Intelligence & Synthesis Pipeline."""
        from engine.slot_coordinator import CATEGORY_PILLARS
        from engine.live_scout import scout_category_intel, format_category_dossier
        from service.telemetry.quota_tracker import telemetry_tracker
        from config.model_pool import get_active_key, get_active_model

        pillar_info = CATEGORY_PILLARS.get(category_key, CATEGORY_PILLARS["Technology"])
        pillar_title = pillar_info["pillar"]
        queries = pillar_info["search_queries"]

        logger.info(f"[RootPipeline] Step 1/2: Scouting verified 24h developments for '{pillar_title}'...")
        raw_intel = await asyncio.to_thread(scout_category_intel, category_key, queries, max_items=12)
        dossier = format_category_dossier(raw_intel, exclusions or [])
        logger.info(f"[RootPipeline] Step 1/2 Complete: {len(raw_intel)} verified developments scouted.")

        logger.info(f"[RootPipeline] Step 2/2: Synthesizing publication-ready article for '{category_key}' via Editor-in-Chief...")
        grounded_prompt = (
            f"PILLAR: {pillar_title}\n\n"
            f"{dossier}\n\n"
            f"EDITORIAL DIRECTIVE:\n"
            f"{ask}\n\n"
            f"Select the SINGLE MOST SIGNIFICANT, verified breaking development in '{pillar_title}' from the past 24 hours "
            f"that does NOT violate the critical exclusion mandate above. Synthesize exactly ONE publication-ready technical dispatch strictly matching the required JSON schema."
        )

        reply = await self.root_engine.agent_response(grounded_prompt)

        # Record API call in telemetry tracker
        telemetry_tracker.record_call(get_active_key(), get_active_model())
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