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

import contextlib

import discord
from discord import app_commands
from discord.ext import commands

from classes.client import Client


class Information(commands.Cog):
    """Informational commands"""

    def __init__(self, bot: Client):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx: commands.Context[Client]):
        """Get the bot's latency

        Parameters
        ----------
        ctx : commands.Context[Client]
            Context
        """
        await ctx.send(f"Pong! {round(self.bot.latency * 1000)}ms")

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context[Client]):
        """This allows me to check when commands are being used.

        Parameters
        ----------
        ctx: Context
            Context
        """
        name: str = ctx.guild.name if ctx.guild else "Private Message"
        self.bot.log.info("%s > %s > %s", name, ctx.author, ctx.command.qualified_name)

    async def on_error(
        self,
        interaction: discord.Interaction[Client],
        error: app_commands.AppCommandError,
    ):
        error: Exception | app_commands.AppCommandError = getattr(error, "original", error)
        command = interaction.command
        resp = interaction.response
        if command and command._has_any_error_handlers():  # skipcq: PYL-W0212
            return

        self.bot.log.error(
            "Interaction Error(%s, %s)",
            getattr(command, "name", "Unknown"),
            ", ".join(f"{k}={v}" for k, v in interaction.data.items()),
            exc_info=error,
        )

        with contextlib.suppress(discord.NotFound):
            if not resp.is_done():
                await resp.defer(thinking=True, ephemeral=True)

        embed = discord.Embed(color=discord.Colour.red(), timestamp=interaction.created_at)

        if not isinstance(error, app_commands.AppCommandError):
            embed.title = f"Error - {type(error := error.__cause__ or error).__name__}"
            embed.description = f"```py\n{error}\n```"
        else:
            embed.title = f"Error - {type(error).__name__}"
            embed.description = str(error)

        with contextlib.suppress(discord.NotFound):
            await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context[Client], error: commands.CommandError):
        """Command error handler

        Parameters
        ----------
        ctx: Context
            Context
        error: CommandError
            Error
        """
        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(
            error,
            (
                commands.CheckFailure,
                commands.UserInputError,
                commands.CommandOnCooldown,
                commands.MaxConcurrencyReached,
                commands.DisabledCommand,
            ),
        ):
            await ctx.send(
                embed=discord.Embed(
                    color=discord.Colour.red(),
                    title=f"Error - {ctx.command.qualified_name}",
                    description=str(error),
                )
            )
            return

        if hasattr(ctx.command, "on_error"):
            return

        # skipcq: PYL-W0212
        if (cog := ctx.cog) and cog._get_overridden_method(cog.cog_command_error):
            return

        error_cause = error.__cause__ or error
        await ctx.send(
            embed=discord.Embed(
                color=discord.Colour.red(),
                title=f"Unexpected error - {ctx.command.qualified_name}",
                description=f"```py\n{type(error_cause).__name__}: {error_cause}\n```",
            )
        )

        self.bot.log.error(
            "Command Error(%s, %s)",
            ctx.command.qualified_name,
            ", ".join(f"{k}={v!r}" for k, v in ctx.kwargs.items()),
            exc_info=error,
        )


async def setup(bot: Client):
    """Setup function for Information

    Parameters
    ----------
    bot : Client
        Bot client
    """
    await bot.add_cog(Information(bot))
