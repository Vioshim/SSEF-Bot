# Copyright 2023 Vioshim
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from typing import Optional

import d20
import discord
from discord.ext import commands

from classes.client import Client


class Utilities(commands.Cog):
    def __init__(self, bot: Client):
        """Initialize the cog

        Parameters
        ----------
        bot : Client
            Bot instance
        """
        self.bot = bot

    @commands.hybrid_command()
    async def roll(self, ctx: commands.Context[Client], *, expression: str = "d20"):
        """Allows to roll dice based on 20

        Parameters
        ----------
        ctx : Context
            Context
        expression : str
            Expression (Example: d20)
        """
        await ctx.defer(ephemeral=True)

        embed = discord.Embed(
            title=f"Rolling: {expression}",
            color=ctx.author.color,
        )

        if embed.title and len(embed.title) > 256:
            embed.title = "Rolling Expression"

        embed.set_image(url="https://dummyimage.com/500x5/FFFFFF/000000&text=%20")

        try:
            value = d20.roll(expr=expression, allow_comments=True)
            if len(value.result) > 4096:
                d20.utils.simplify_expr(value.expr)
            embed.description = value.result
            embed.set_thumbnail(url=f"https://dummyimage.com/512x512/FFFFFF/000000&text={value.total}")
        except Exception:
            embed.description = "Invalid expression."

        await ctx.reply(embed=embed, ephemeral=True)


async def setup(bot: Client):
    """Load the cog

    Parameters
    ----------
    bot : Client
       Bot instance
    """
    await bot.add_cog(Utilities(bot))
