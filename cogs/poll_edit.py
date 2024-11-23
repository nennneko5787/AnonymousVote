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

    @app_commands.command(name="makepoll", description="投票を作成します。")
    @app_commands.rename(
        title="タイトル",
        description="説明",
        reselectable="再投票",
    )
    @app_commands.describe(
        title="投票のタイトル。",
        description="投票の説明。",
        reselectable="ユーザーが後で選択肢を変えれるようにする？",
    )
    @app_commands.choices(
        reselectable=[
            app_commands.Choice(name="はい！", value=True),
            app_commands.Choice(name="いいえ。", value=False),
        ],
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def makePollCommand(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        reselectable: app_commands.Choice[int] = False,
    ):
        await interaction.response.defer(ephemeral=True)
        await Database.pool.execute(
            "INSERT INTO polls (id, title, description, reselectable, owner_id) VALUES ($1, $2, $3, $4, $5)",
            secrets.token_hex(10),
            title,
            description,
            reselectable.value,
            interaction.user.id,
        )
        embed = discord.Embed(
            title="作成しました！",
            description="`/addchoice` コマンドで選択肢を追加できます",
            colour=discord.Colour.green(),
        )
        await interaction.followup.send(embed=embed)

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

    @app_commands.command(name="addchoice", description="投票に選択肢を追加します。")
    @app_commands.rename(
        poll="投票",
        name="名前",
        emoji="絵文字",
    )
    @app_commands.describe(
        poll="選択肢を追加する投票を選択してください。",
        name="選択肢の名前。",
        emoji="（オプション）選択肢表示する絵文字。",
    )
    @app_commands.autocomplete(poll=getPollList)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def addChoiceCommand(
        self,
        interaction: discord.Interaction,
        poll: str,
        name: str,
        emoji: str = None,
    ):
        if emoji:
            _emoji = discord.PartialEmoji.from_str(emoji)
            if not _emoji.is_custom_emoji() and not isEmoji(_emoji.name):
                embed = discord.Embed(
                    title="絵文字が無効です！\n❤️などの通常の絵文字は`:heart:`ではなく`❤️`の状態で入力する必要があります。",
                    colour=discord.Colour.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

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

        poll = dict(poll)
        items: list = orjson.loads(poll["items"])
        items.append({"name": name, "emoji": emoji})
        items = orjson.dumps(items).decode()
        await Database.pool.execute(
            "UPDATE ONLY polls SET items = $1 WHERE id = $2", items, poll["id"]
        )
        embed = discord.Embed(title="追加しました", colour=discord.Colour.green())
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="removechoice", description="投票から選択肢を削除します。"
    )
    @app_commands.autocomplete(poll=getPollList)
    @app_commands.rename(poll="投票")
    @app_commands.describe(poll="選択肢を削除する投票を選択してください。")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def removeChoiceCommand(
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
        items: list[dict[str, str]] = orjson.loads(poll["items"])
        view = discord.ui.View(timeout=None)
        select = discord.ui.Select(
            options=[
                discord.SelectOption(
                    label=item["name"],
                    value=index,
                )
                for index, item in enumerate(items)
            ]
        )

        async def removeChoiceOnSelect(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            try:
                items.remove(items[int(interaction.data["values"][0])])
                await Database.pool.execute(
                    "UPDATE ONLY polls SET items = $1 WHERE id = $2",
                    orjson.dumps(items).decode(),
                    poll["id"],
                )

                embed = discord.Embed(
                    title="投票から選択肢を削除しました",
                    colour=discord.Colour.green(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                traceback.print_exception(e)
                embed = discord.Embed(title="削除済みです", colour=discord.Colour.red())
                await interaction.followup.send(embed=embed, ephemeral=True)

        select.callback = removeChoiceOnSelect
        view.add_item(select)
        embed = discord.Embed(
            title="削除する選択肢を選択してください", colour=discord.Colour.red()
        )
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(PollEditCog(bot))
