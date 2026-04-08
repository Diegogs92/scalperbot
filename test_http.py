import asyncio
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

async def test():
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': "Test directo",
        'parse_mode': 'HTML'
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            print("Status:", response.status)
            print("Body:", await response.text())

asyncio.run(test())
