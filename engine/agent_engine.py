import os
import asyncio
import logging
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.models.google_llm import Gemini
from google.genai import types
from config.logging_config import setup_logging
from config.model_pool import get_active_model, get_active_key, report_failure, coordinator

setup_logging()

class AgentEngine:
    def __init__(self, agent_name, description, instruction, tools, output_key, on_failover=None):
        self.retry_config = types.HttpRetryOptions(
            attempts=2,
            exp_base=2,
            initial_delay=1,
            http_status_codes=[429, 500, 503, 504]
        )
        self.agent_name = agent_name
        self.description = description
        self.instruction = instruction
        self.tools = tools
        self.output_key = output_key
        self.on_failover = on_failover
        self.agent = None
        self.runner = None
        self.model_name = get_active_model()
        self.api_key = get_active_key()

    def agent_creation(self, model_name=None):
        if model_name:
            self.model_name = model_name
        else:
            self.model_name = get_active_model()
            
        self.agent = Agent(
            name=self.agent_name,
            model=Gemini(
                model=self.model_name,
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

        attempt_count = 0
        max_attempts = 12  # Sufficient retry attempts across all 4 keys and model tiers

        while attempt_count < max_attempts:
            attempt_count += 1
            try:
                active_key_num = coordinator.key_index + 1
                logging.info(f"[{self.agent_name}] Processing query on '{self.model_name}' (Key #{active_key_num})...")
                
                # quiet=True suppresses raw session dump; logging handles clean output
                events = await self.runner.run_debug(ask, quiet=True)
                response = ""

                for event in events:
                    if not event.content or not event.content.parts:
                        continue

                    for part in event.content.parts:
                        if hasattr(part, "function_call") and part.function_call:
                            call_name = getattr(part.function_call, "name", "tool")
                            logging.info(f"[{self.agent_name}] Agent invoked tool: '{call_name}'.")
                        elif hasattr(part, "tool_response") and part.tool_response:
                            logging.info(f"[{self.agent_name}] Tool execution returned verified results.")
                        elif hasattr(part, "text") and part.text:
                            response += part.text

                if response:
                    logging.info(f"[{self.agent_name}] Response synthesized successfully ({len(response)} chars).")
                    return response
                
                await asyncio.sleep(1)

            except Exception as e:
                err_str = str(e)
                # Catch rate limits, service busy, 403 permission errors, or 404 missing models
                if any(code in err_str for code in ["429", "ResourceExhausted", "503", "500", "404", "403", "400", "PERMISSION_DENIED"]):
                    if "429" in err_str or "ResourceExhausted" in err_str:
                        reason = "429 Rate Limit"
                    elif "403" in err_str or "PERMISSION_DENIED" in err_str:
                        reason = "403 Forbidden"
                    elif "503" in err_str:
                        reason = "503 Service Busy"
                    else:
                        reason = "API Exception"

                    new_model, new_key = report_failure(self.model_name, self.api_key, error_code=reason)
                    self.model_name = new_model
                    self.api_key = new_key

                    if self.on_failover:
                        self.on_failover(new_model, new_key)
                    else:
                        self.agent_creation(model_name=new_model)
                        self.agent_runner()

                    await asyncio.sleep(1)
                else:
                    logging.warning(f"[{self.agent_name}] Transient notice: {err_str[:120]} - retrying in 2s...")
                    await asyncio.sleep(2)
                continue

        logging.error(f"[{self.agent_name}] Max attempts ({max_attempts}) reached without completion.")
        return None