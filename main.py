import os

import dotenv
import discord
from discord.ext import commands

dotenv.load_dotenv()

bot = commands.Bot("vote#", intents=discord.Intents.default())

bot.run(os.getenv("discord"))
