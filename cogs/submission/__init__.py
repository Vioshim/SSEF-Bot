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


from textwrap import TextWrapper

import discord
from discord.ext import commands
from discord.utils import escape_mentions, remove_markdown

from classes.character import Character, CharacterArg
from classes.client import Client
from cogs.submission.modals import CreateCharacterModal, UpdateCharacterModal


class Submission(commands.Cog):
    def __init__(self, bot: Client) -> None:
        self.bot = bot
        self.wrapper = TextWrapper(
            width=2000,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
            drop_whitespace=True,
            fix_sentence_endings=False,
        )
        self.db = bot.db("Characters")

    @commands.hybrid_group(
        aliases=["oc", "character"],
        invoke_without_command=True,
        case_insensitive=True,
    )
    async def char(self, ctx: commands.Context[Client]):
        """Character commands group

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        """
        items = [
            "add <name> <description>",
            "read <name>",
            "delete <name>",
            "edit name <name> <new name>",
            "edit desc <name> <description>",
            "list <user: optional>",
        ]
        description = "\n".join(
            f"{idx}. `{ctx.prefix}{ctx.invoked_with} {item}`" for idx, item in enumerate(items, start=1)
        )
        content = "# Character Commands\n\n" + description
        await ctx.reply(content=content, ephemeral=True)

    @char.app_command.command()
    async def create(self, itx: discord.Interaction[Client]):
        """Create a new character

        Parameters
        ----------
        itx : discord.Interaction
            Interaction of the command
        """
        modal = CreateCharacterModal(timeout=None)
        await itx.response.send_modal(modal)

    @char.command(aliases=["new"], with_app_command=False)
    async def add(
        self,
        ctx: commands.Context[Client],
        name: remove_markdown = "",
        *,
        description: escape_mentions = "",
    ):
        """Create a new character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        name : str
            Name of the character
        description : str
            Description of the character
        """
        if ctx.message and ctx.message.mentions:
            return await ctx.reply(
                "Do not mention users when creating a character.",
                ephemeral=True,
            )

        if description and name:
            if len(name) > 256:
                return await ctx.reply(
                    "Name must be less than 256 characters.",
                    ephemeral=True,
                )

            try:
                oc = await Character.converter(ctx, name)
                await ctx.reply(f"{oc.name!r} already exists.", ephemeral=True)
            except commands.BadArgument:
                await self.db.insert_one(
                    {
                        "name": name,
                        "description": description,
                        "user_id": ctx.author.id,
                    }
                )
                await ctx.reply(f"Created {name!r}", ephemeral=True)
        elif ctx.interaction:
            modal = CreateCharacterModal(timeout=None)
            modal.name.default = name
            if description:
                modal.desc.default = description
            await ctx.interaction.response.send_modal(modal)
        else:
            await ctx.reply("Name and Description cannot be empty.", ephemeral=True)

    @char.command(aliases=["get", "view"])
    async def read(self, ctx: commands.Context[Client], *, oc: CharacterArg):
        """Get a character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        oc : str
            Character
        """
        for text in self.wrapper.wrap(oc.description):
            await ctx.reply(content=text, ephemeral=True)

    @char.command(aliases=["del", "remove"])
    async def delete(self, ctx: commands.Context[Client], *, oc: CharacterArg):
        """Delete a character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        oc: Character
            Character to delete
        """
        await self.db.delete_one({"_id": oc._id, "user_id": ctx.author.id})
        await ctx.reply(embed=oc.embed)

    @char.app_command.command()
    async def update(self, itx: discord.Interaction[Client], *, oc: CharacterArg):
        """Update a character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        oc : Character
            Character
        """
        modal = UpdateCharacterModal(oc)
        await itx.response.send_modal(modal)

    @char.group(invoke_without_command=True)
    async def edit(self, _: commands.Context[Client]):
        """Edit a character

        Parameters
        ----------
        _ : commands.Context
            Context of the command
        """

    @edit.command(with_app_command=False)
    async def name(
        self,
        ctx: commands.Context[Client],
        oc: CharacterArg,
        *,
        name: remove_markdown,
    ):
        """Edit a character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        oc : Character
            Character
        name : str
            New name
        """
        if name == oc.name:
            return await ctx.reply("You can't set the same name as before.")

        if not name or len(name) > 256:
            return await ctx.reply("Name must be less than 256 characters.")

        await self.db.update_one(
            {"_id": oc._id, "user_id": ctx.author.id},
            {"$set": {"name": name}},
            upsert=True,
        )
        await ctx.reply(f"Changed {oc.name!r} to {name!r}", ephemeral=True)

    @edit.command(with_app_command=False, aliases=["desc"])
    async def description(
        self,
        ctx: commands.Context[Client],
        oc: CharacterArg,
        *,
        description: escape_mentions,
    ):
        """Edit a character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        oc : Character
            Character to edit
        description : str
            Description of the character
        """
        if description == oc.description:
            return await ctx.reply("You can't set the same description.")

        await self.db.update_one(
            {"_id": oc._id, "user_id": ctx.author.id},
            {"$set": {"description": description}},
        )
        await ctx.reply(f"Changed description of {oc.name!r}", ephemeral=True)

    @char.command()
    async def list(
        self,
        ctx: commands.Context[Client],
        user: discord.Member | discord.User = commands.Author,
    ):
        """Get a character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        user : discord.Member | discord.User
            User to get the characters from
        """
        ocs = [
            Character(**oc)
            async for oc in self.db.find(
                {
                    "user_id": user.id,
                }
            )
        ]
        ocs.sort(key=lambda oc: oc.name)
        description = "\n".join(f"* {oc.display_name}" for oc in ocs) or "Doesn't have any characters."

        embed = discord.Embed(
            title="Characters",
            color=ctx.author.color,
            description=description,
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar)
        await ctx.reply(embed=embed, ephemeral=True)


async def setup(bot: Client):
    """Load the cog

    Parameters
    ----------
    bot : Client
       Bot instance
    """
    await bot.add_cog(Submission(bot))
