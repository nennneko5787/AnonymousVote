import secrets
import traceback

import emoji
import discord
import orjson
from discord.ext import commands
from discord import app_commands

from .database import Database


def isEmoji(s: str) -> bool:
    return s in emoji.EMOJI_DATA


class PollEditCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def reloadPoll(id: str):


    async def getPollList(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        pollList = await Database.pool.fetch("SELECT * FROM polls")
        polls = []
        for poll in pollList:
            if poll["title"].startswith(current):
                owner_id = poll["owner_id"]
                if owner_id == interaction.user.id:
                    polls.append(
                        app_commands.Choice(
                            name=f'{poll["title"]}',
                            value=poll["id"],
                        )
                    )
        return polls

    @app_commands.command(name="send", description="投票を送信します。")
    @app_commands.rename(
        poll="投票",
    )
    @app_commands.describe(
        poll="送信したい投票を選択してください。",
    )
    @app_commands.autocomplete(poll=getPollList)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def addChoiceCommand(
        self,
        interaction: discord.Interaction,
        poll: str,
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            poll = await Database.pool.fetchrow(
                "SELECT * FROM polls WHERE id = $1", poll
            )
        except:
            poll = await Database.pool.fetchrow(
                "SELECT * FROM polls WHERE title LIKE $1 AND owner_id = $2 LIMIT 1",
                poll,
                interaction.user.id,
            )
        if not poll:
            embed = discord.Embed(
                title="投票が存在しませんでした",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        if poll["owner_id"] != interaction.user.id:
            embed = discord.Embed(
                title="その投票はあなたのものではありません",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # ここから描く


async def setup(bot: commands.Bot):
    await bot.add_cog(PollEditCog(bot))
