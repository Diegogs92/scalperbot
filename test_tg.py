import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from notifications import notifier

async def main():
    await notifier.notify_startup(testnet=True)
    print("Test finished")

asyncio.run(main())
