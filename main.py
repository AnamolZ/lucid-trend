import os
import asyncio
from engine.news_engine import NewsEngine
from engine.dsearch_engine import DeepSearchEngine
from engine.root_agent import RootAgentEngine
from dotenv import load_dotenv

load_dotenv()

async def main():
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY not found in environment.")
        return

    news_fetch = NewsEngine()
    news_fetch.news_agent()
    
    deep_engine = DeepSearchEngine()
    deep_engine.dsearch_agent()
    
    root_agent = RootAgentEngine()
    await root_agent.root_agent()

if __name__ == "__main__":
    asyncio.run(main())