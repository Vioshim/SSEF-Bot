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


from itertools import groupby
from textwrap import TextWrapper
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import escape_mentions, remove_markdown
from rapidfuzz import process

from classes.character import Character, CharacterArg
from classes.client import Client
from cogs.submission.modals import CreateCharacterModal, UpdateCharacterModal


class Submission(commands.Cog):
    def __init__(self, bot: Client):
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
        self.itx_menu1 = app_commands.ContextMenu(
            name="See list",
            callback=self.list_menu,
        )

    async def cog_load(self):
        self.bot.tree.add_command(self.itx_menu1)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.itx_menu1.name, type=self.itx_menu1.type)

    @commands.hybrid_group(
        aliases=["oc", "character"],
        invoke_without_command=True,
        case_insensitive=True,
        fallback="lookup",
    )
    async def char(self, ctx: commands.Context[Client], *, text: str):
        """Character commands group

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        """
        ocs = []

        try:
            oc = await Character.converter(ctx, text)
        except commands.BadArgument:
            oc = None

        if oc is None:
            guild = ctx.guild or ctx.author.mutual_guilds[0]
            ocs = [Character(**oc) async for oc in self.db.find({}) if guild.get_member(oc["user_id"])]

            if result := process.extractOne(
                text,
                ocs,
                processor=lambda oc: oc.name if isinstance(oc, Character) else oc,
                score_cutoff=60,
            ):
                oc = result[0]
            elif len(ocs := [oc for oc in ocs if text.lower() in oc.display_name.lower()]) == 1:
                oc = ocs[0]

        if isinstance(oc, Character):
            for index, text in enumerate(self.wrapper.wrap(oc.description)):
                await ctx.reply(
                    content=text,
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions(
                        replied_user=index == 0,
                    ),
                )
        elif ocs:
            embed = discord.Embed(title="Characters", color=ctx.author.color)

            ocs.sort(key=lambda x: (x.user_id, x.name))
            guild = ctx.guild or ctx.author.mutual_guilds[0]

            for k, v in groupby(ocs, lambda x: x.user_id):
                m = guild.get_member(k)
                if m and len(embed.fields) < 25:
                    embed.add_field(
                        name=str(m),
                        value="\n".join(f"* {oc.display_name}" for oc in v)[:1024],
                    )

            await ctx.reply(embed=embed, ephemeral=True)
        else:
            await ctx.reply(
                content="No characters found.",
                ephemeral=True,
            )

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
            await ctx.reply("You must provide a name and description.", ephemeral=True)

    @commands.command()
    async def addchar(
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
        await ctx.invoke(self.add, name=name, description=description)

    @char.command(aliases=["get", "view"])
    async def read(
        self,
        ctx: commands.Context[Client],
        *,
        oc: CharacterArg,
    ):
        """Get a character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        author : discord.Member | discord.User
            Author of the character
        oc : str
            Character
        """
        if isinstance(oc, Character):
            for index, text in enumerate(self.wrapper.wrap(oc.description)):
                await ctx.reply(
                    content=text,
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions(
                        replied_user=index == 0,
                    ),
                )

    @char.command(with_app_command=False)
    async def query(
        self,
        ctx: commands.Context[Client],
        *,
        query: remove_markdown = "",
    ):
        embed = discord.Embed(title="Characters", color=ctx.author.color)
        guild = ctx.guild or ctx.author.mutual_guilds[0]
        ocs = [Character(**oc) async for oc in self.db.find({}) if guild.get_member(oc["user_id"])]
        items = [
            x
            for x, _, _ in process.extract(
                query,
                ocs,
                processor=lambda x: x.name if isinstance(x, Character) else x,
                score_cutoff=80,
            )
        ]

        if not items:
            items.extend(x for x in ocs if x not in items and query.lower() in x.display_name.lower())

        items.sort(key=lambda x: (x.user_id, x.name))
        guild = ctx.guild or ctx.author.mutual_guilds[0]

        for k, v in groupby(items, key=lambda x: x.user_id):
            m = guild.get_member(k)
            if m and len(embed.fields) < 25:
                embed.add_field(
                    name=str(m),
                    value="\n".join(f"* {oc.display_name}" for oc in v)[:1024],
                )

        if len(embed) > 6000:
            await ctx.reply("Too many characters found.", ephemeral=True)
        else:
            await ctx.reply(embed=embed, ephemeral=True)

    @char.command(with_app_command=False)
    async def find(
        self,
        ctx: commands.Context[Client],
        author: Optional[discord.Member | discord.User] = None,
        *,
        query: Optional[CharacterArg | str] = None,
    ):
        if isinstance(query, Character):
            return await ctx.invoke(self.read, oc=query)

        if not query:
            return await ctx.invoke(self.list, user=author)

        author = author or ctx.author
        key = {"user_id": author.id}
        ocs = [Character(**oc) async for oc in self.db.find(key)]
        if result := process.extractOne(
            query,
            ocs,
            processor=lambda x: x.name if isinstance(x, Character) else x,
            score_cutoff=80,
        ):
            return await ctx.invoke(self.read, oc=result[0])

        await ctx.reply("No characters found.", ephemeral=True)

    @char.app_command.command()
    async def search(
        self,
        ctx: commands.Context[Client],
        query: str = "",
        author: Optional[discord.Member | discord.User] = None,
        *,
        oc: Optional[CharacterArg] = None,
    ):
        """Search for a character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        query : str
            Query to search
        author : Optional[discord.Member | discord.User]
            Author of the character
        oc : Optional[str]
            Character
        """
        if oc:
            return await ctx.invoke(self.read, oc=oc)

        embed = discord.Embed(title="Characters")
        if author is None:
            key = {}
            embed.color = ctx.author.color
        else:
            key = {"user_id": author.id}
            embed.color = author.color
            embed.set_author(name=author.display_name, icon_url=author.display_avatar)

        guild = ctx.guild or ctx.author.mutual_guilds[0]
        ocs = [Character(**oc) async for oc in self.db.find(key) if guild.get_member(oc["user_id"])]
        query = remove_markdown(query)
        items = [
            x
            for x, _, _ in process.extract(
                query,
                ocs,
                processor=lambda x: x.name if isinstance(x, Character) else x,
                score_cutoff=80,
            )
        ]

        items.extend(x for x in ocs if x not in items and query.lower() in x.display_name.lower())
        items.sort(key=lambda x: (x.user_id, x.name))
        guild = ctx.guild or ctx.author.mutual_guilds[0]

        for k, v in groupby(items, lambda x: x.user_id):
            m = guild.get_member(k)
            if m and len(embed.fields) < 25:
                embed.add_field(name=str(m), value="\n".join(f"* {oc.display_name}" for oc in v)[:1024])

        await ctx.reply(embed=embed, ephemeral=True)

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

    @commands.command(aliases=["deletechar", "removechar"])
    async def delchar(self, ctx: commands.Context[Client], *, oc: CharacterArg):
        """Delete a character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        oc: Character
            Character to delete
        """
        await ctx.invoke(self.delete, oc=oc)

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

    @commands.command(aliases=["editname", "rename"])
    async def renamechar(
        self,
        ctx: commands.Context[Client],
        oc: CharacterArg,
        name: str,
    ):
        """Rename a character

        Parameters
        ----------
        oc : CharacterArg
            Character to rename
        name : str
            New name
        """
        await ctx.invoke(self.name, oc=oc, name=name)

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

    @commands.command()
    async def editchar(
        self,
        ctx: commands.Context[Client],
        oc: CharacterArg,
        *,
        description: escape_mentions,
    ):
        """Edit a character

        Parameters
        ----------
        ctx : commands.Context[Client]
            Context of the command
        oc : CharacterArg
            Character to edit
        description : str
            Description of the character
        """
        await ctx.invoke(self.description, oc=oc, description=description)

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

    async def list_menu(self, itx: discord.Interaction[Client], member: discord.Member | discord.User):
        """Get a character

        Parameters
        ----------
        itx : discord.Interaction[Client]
            Interaction
        member : discord.Member | discord.User
            User to get the characters from
        """
        ocs = [
            Character(**oc)
            async for oc in self.db.find(
                {
                    "user_id": member.id,
                }
            )
        ]
        ocs.sort(key=lambda oc: oc.name)
        description = "\n".join(f"* {oc.display_name}" for oc in ocs) or "Doesn't have any characters."

        embed = discord.Embed(
            title="Characters",
            color=member.color,
            description=description,
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar)
        await itx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: Client):
    """Load the cog

    Parameters
    ----------
    bot : Client
       Bot instance
    """
    await bot.add_cog(Submission(bot))
