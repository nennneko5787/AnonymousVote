import asyncio
import os
from contextlib import asynccontextmanager

import dotenv
import discord
from fastapi import FastAPI
from discord.ext import commands

from cogs.database import Database

dotenv.load_dotenv()
discord.utils.setup_logging()

bot = commands.Bot("vote#", intents=discord.Intents.default())


@bot.event
async def setup_hook():
    await bot.load_extension("cogs.poll_edit")
    await bot.tree.sync(guild=bot.get_guild(1282708798791745626))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await Database.connect()
    asyncio.create_task(bot.start(os.getenv("discord")))
    yield
    async with asyncio.timeout(60):
        await Database.pool.close()


app = FastAPI(lifespan=lifespan)
