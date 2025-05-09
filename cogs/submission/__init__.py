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


import io
from itertools import groupby
from typing import Optional, Annotated

import discord
import matplotlib.pyplot as plt
import numpy as np
from discord import app_commands
from discord.ext import commands
from discord.utils import escape_mentions, remove_markdown
from rapidfuzz import process
from scipy.stats import norm

from classes.character import Character, CharacterArg
from classes.client import Client
from cogs.submission.modals import CreateCharacterModal, UpdateCharacterModal
from cogs.submission.sheets import Sheet
from cogs.submission.stats import Kind, KindArg, SizeArg, StatArg


class Submission(commands.Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self.db = bot.db("Characters")
        self.itx_menu1 = app_commands.ContextMenu(name="See list", callback=self.list_menu)

    async def cog_load(self):
        self.bot.tree.add_command(self.itx_menu1)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.itx_menu1.name, type=self.itx_menu1.type)

    @commands.guild_only()
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
        ocs = {
            o: o.name
            async for oc in self.db.find({"server": ctx.guild and ctx.guild.id})
            if (ctx.guild and ctx.guild.get_member(oc["user_id"]))
            and (o := Character(**oc)).oc_name.lower().startswith(text.lower())
        }

        if len(text) >= 2 and (result := process.extractOne(text, ocs, score_cutoff=90)):
            return await ctx.invoke(self.read, oc=result[-1])

        ocs = sorted(ocs, key=lambda x: (x.user_id, x.oc_name))
        data = {m: list(v) for k, v in groupby(ocs, lambda x: x.user_id) if (m := ctx.guild.get_member(k))}

        embeds = [
            discord.Embed(
                description="\n".join(f"* {oc.display_name}" for oc in v),
                color=k.color,
            ).set_author(name=k.display_name, icon_url=k.display_avatar)
            for k, v in data.items()
        ]

        if embeds and len(embeds) <= 10 and sum(len(x) for x in embeds) <= 6000:
            return await ctx.reply(embeds=embeds, ephemeral=True)

        for text in ctx.bot.wrapper.wrap(
            "\n".join(
                f"## {m.mention}\n" + "\n".join(f"* {oc.display_name}" for oc in v)
                for k, v in groupby(ocs, lambda x: x.user_id)
                if (m := ctx.guild and ctx.guild.get_member(k))
            )
            or "No characters found."
        ):
            await ctx.reply(content=text, ephemeral=True)

    @char.app_command.command()
    async def create(
        self,
        itx: discord.Interaction[Client],
        sheet: Sheet,
        image: Optional[discord.Attachment] = None,
    ):
        """Create a new character

        Parameters
        ----------
        itx : discord.Interaction
            Interaction of the command
        sheet : Sheet
            Sheet template to use
        image : Optional[discord.Attachment]
            Image of the character
        """
        if not itx.guild:
            return await itx.response.send_message(
                "You can only create characters in servers.",
                ephemeral=True,
            )

        modal = CreateCharacterModal(sheet, image)
        await itx.response.send_modal(modal)

    @char.command(aliases=["new"], with_app_command=False)
    async def add(
        self,
        ctx: commands.Context[Client],
        name: Annotated[str, remove_markdown] = "",
        *,
        description: Annotated[str, escape_mentions] = "",
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
        if not ctx.guild:
            return await ctx.reply(
                "You can only create characters in servers.",
                ephemeral=True,
            )

        if ctx.message and ctx.message.mentions:
            return await ctx.reply(
                "Do not mention users when creating a character.",
                ephemeral=True,
            )

        if description and name:
            if name.lower().startswith("name:"):
                name = name[5:].strip()

            if len(name) > 256:
                return await ctx.reply(
                    "Name must be less than 256 characters.",
                    ephemeral=True,
                )

            if ctx.message and ctx.message.attachments:
                description, *imgs = description.split("\n# Attachments\n")
                imgs = "\n".join(x.strip() for x in imgs if x) + "\n".join(
                    f"* {item.proxy_url}" for item in ctx.message.attachments
                )
                description = f"{description.strip()}\n# Attachments\n{imgs}"

            try:
                oc = await Character.convert(ctx, name)
                await ctx.reply(f"{oc.name!r} already exists.", ephemeral=True)
            except commands.BadArgument:
                await self.db.insert_one(
                    {
                        "name": name.strip(),
                        "description": description.strip(),
                        "user_id": ctx.author.id,
                        "server": ctx.guild.id if ctx.guild else None,
                    }
                )
                await ctx.reply(f"Created {name!r}", ephemeral=True)
        elif ctx.interaction:
            modal = CreateCharacterModal()
            modal.name.default = name
            if description:
                modal.desc.default = description
            await ctx.interaction.response.send_modal(modal)
        else:
            await ctx.reply(Sheet.Normal.template, ephemeral=True)

    @commands.guild_only()
    @commands.command()
    async def addchar(
        self,
        ctx: commands.Context[Client],
        name: Annotated[str, remove_markdown] = "",
        *,
        description: Annotated[str, escape_mentions] = "",
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
    async def read(self, ctx: commands.Context[Client], *, oc: CharacterArg):
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
        info = f"# ============================\nID: {oc._id} | Created by <@{oc.user_id}>"
        for text in ctx.bot.wrapper.wrap(f"{oc.description.removesuffix(info).strip()}\n{info}"):
            await ctx.reply(content=text, ephemeral=True)

    @char.command(with_app_command=False)
    async def query(self, ctx: commands.Context[Client], *, query: Annotated[str, remove_markdown] = ""):
        """Query characters

        Parameters
        ----------
        ctx : commands.Context[Client]
            Context of the command
        query : remove_markdown, optional
            Query to search for, by default ""
        """
        embed = discord.Embed(title="Characters", color=ctx.author.color)
        ocs = [
            Character(**oc)
            async for oc in self.db.find({"server": ctx.guild.id})
            if ctx.guild and ctx.guild.get_member(oc["user_id"])
        ]
        items = [
            x
            for x, _, _ in process.extract(
                query,
                ocs,
                processor=lambda x: x.name if isinstance(x, Character) else x,
                score_cutoff=80,
            )
        ]

        if not items and query:
            query: str = query.lower()
            items.extend(x for x in ocs if query in x.display_name.lower())

        items.sort(key=lambda x: (x.user_id, x.oc_name))

        for k, v in groupby(items, key=lambda x: x.user_id):
            m = ctx.guild and ctx.guild.get_member(k)
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
        author: discord.Member | discord.User = commands.Author,
        *,
        query: Optional[str] = None,
    ):
        """Find a character

        Parameters
        ----------
        ctx : commands.Context[Client]
            Context of the command
        author : Optional[discord.Member  |  discord.User], optional
            Author of the character, by default None
        query : Optional[str], optional
            Query to search for, by default None
        """
        if not query:
            return await ctx.invoke(self.list, user=author)

        ocs = {
            o: o.name
            async for oc in self.db.find({"user_id": author.id, "server": ctx.guild.id})
            if (o := Character(**oc))
        }
        if result := process.extractOne(query, ocs, score_cutoff=80):
            return await ctx.invoke(self.read, oc=result[-1])

        await ctx.reply("No characters found.", ephemeral=True)

    @char.app_command.command()
    async def search(
        self,
        itx: discord.Interaction[Client],
        query: str = "",
        author: Optional[discord.Member | discord.User] = None,
        *,
        oc: Optional[CharacterArg] = None,
    ):
        """Search for a character

        Parameters
        ----------
        itx : discord.Interaction
            Interaction
        query : str
            Query to search
        author : Optional[discord.Member | discord.User]
            Author of the character
        oc : Optional[str]
            Character
        """
        await itx.response.defer(ephemeral=True, thinking=True)

        if isinstance(oc, Character):
            info = f"# ============================\nID: {oc._id} | Created by <@{oc.user_id}>"
            content = f"{oc.description.removesuffix(info).strip()}\n{info}"
        else:
            key = {} if author is None else {"user_id": author.id}
            guild = itx.guild or itx.user.mutual_guilds[0]
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

            if not items:
                query = query.lower()
                items.extend(x for x in ocs if query in x.display_name.lower())

            items.sort(key=lambda x: (x.user_id, x.name))

            content = "\n".join(
                f"## {m.mention}\n" + "\n".join(f"* {oc.display_name}" for oc in v)
                for k, v in groupby(items, lambda x: x.user_id)
                if (m := guild.get_member(k))
            )

        for text in self.bot.wrapper.wrap(content):
            await itx.followup.send(content=text, ephemeral=True)

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
        await self.db.delete_one({"_id": oc._id, "user_id": ctx.author.id, "server": ctx.guild and ctx.guild.id})
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

    @char.command(aliases=["delete-many"], with_app_command=False)
    async def delete_many(self, ctx: commands.Context[Client], *ocs: CharacterArg):
        """Delete many characters

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        ocs: Character
            Characters to delete
        """
        oc_ids = {x._id for x in ocs}

        if not oc_ids:
            return await ctx.reply("No characters provided", ephemeral=True)

        await self.db.delete_many(
            {
                "_id": {"$in": list(oc_ids)},
                "user_id": ctx.author.id,
                "server": ctx.guild and ctx.guild.id,
            }
        )
        await ctx.reply(
            embed=discord.Embed(
                title=f"Deleted {len(ocs)} characters",
                description="\n".join(oc.display_name for oc in ocs),
            ),
        )

    @commands.guild_only()
    @commands.command(aliases=["deletechars", "removechars"])
    async def delchars(self, ctx: commands.Context[Client], *ocs: CharacterArg):
        """Delete many characters

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        ocs: Character
            Characters to delete
        """
        await ctx.invoke(self.delete_many, *ocs)

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
        if not itx.guild:
            return await itx.response.send_message(
                "This command can only be used in a server",
                ephemeral=True,
            )

        modal = UpdateCharacterModal(oc)
        await itx.response.send_modal(modal)

    @char.command()
    async def stats(
        self,
        ctx: commands.Context[Client],
        level: commands.Range[float, 0.0],
        kind: KindArg = Kind.Final,
        *,
        stats: Optional[StatArg] = None,
    ):
        """Calculate stats for a character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        level : commands.Range[float, 1.0]
            Level of the character
        kind : Kind
            Kind of the character (default: Final)
        stats : Stats
            Stats of the character (default: 1 1 1 1 1 1)
        """
        points = kind.value * level + 42

        embed = discord.Embed(title=f"Total Points = {points:,.2f}".replace(",", "\u2009"))
        embed.set_author(name=f"Using {kind.name} which has {kind.value} points per level")

        try:
            values = {
                k: float(v)
                for k, v in zip(
                    [
                        "HP",
                        "Attack",
                        "Defense",
                        "Sp. Attack",
                        "Sp. Defense",
                        "Speed",
                    ],
                    str(stats or "1 1 1 1 1 1").split(),
                    strict=True,
                )
            }

            total_stat = sum(values.values())
            for stat, value in values.items():
                perc = value / total_stat
                embed.add_field(
                    name=f"{perc:.2%} | {stat}",
                    value=f"{perc * points:,.2f}".replace(",", "\u2009"),
                )

            embed.set_footer(text="These stats are averages for a character of this level.")

        except ValueError:
            embed.description = "Invalid stats"
            embed.clear_fields()

        await ctx.reply(embed=embed, ephemeral=True)

    @char.command()
    async def size(self, ctx: commands.Context[Client], *, mean: SizeArg = 1.0):
        """Normal Distribution of a species's size

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        mean : Size
            Average size of the species (default: 1.0)
        """
        lower_limit = 0.75 * mean
        upper_limit = 1.25 * mean
        std_dev = 0.15 * mean

        # Generate x values for the normal distribution curve
        x = np.linspace(mean - 2.5 * std_dev, mean + 2.5 * std_dev, 1000)

        # Calculate the normal distribution values using scipy's norm.pdf function
        y = norm.pdf(x, mean, std_dev)

        # Create a mask for the shaded area between lower and upper limits
        mask = (x >= lower_limit) & (x <= upper_limit)

        # Calculate the area under the curve for the shaded region
        area = np.trapz(y[mask], x[mask])
        percentage = area * 100

        # Convert mean, lower limit, upper limit, and standard deviation to feet-inches
        mean_ft, mean_inch = mean // 0.3048, mean / 0.3048 % 1 * 12
        std_dev_ft, std_dev_inch = std_dev // 0.3048, std_dev / 0.3048 % 1 * 12

        # Determine the number of ticks dynamically based on the requirement
        ticks_values = np.linspace(lower_limit, upper_limit, 5)
        feet_ticks = [f"{val:.02f} m\n{int(val // 0.3048)}' {int(val / 0.3048 % 1 * 12)}\"ft" for val in ticks_values]

        # Create the plot with improved aesthetics
        plt.figure(figsize=(10, 6))
        plt.plot(x, y, color="darkblue", label="Normal Distribution", linewidth=2)
        plt.fill_between(x, y, where=mask, alpha=0.5, color="skyblue", label=f"Shaded Area ({percentage:.2f}%)")
        plt.title(
            f"Normal Distribution (Mean: {mean_ft:.0f}' {mean_inch:.1f}\" / {mean:.2f}m | SD: {std_dev_ft:.0f}' {std_dev_inch:.1f}\" / {std_dev:.2f}m)",
            fontsize=16,
        )
        plt.legend(fontsize=12)
        plt.grid(True, linestyle="--", alpha=0.7)
        plt.xticks(ticks_values, feet_ticks, fontsize=12, fontweight="bold")
        plt.tight_layout()

        # Save the plot to a BytesIO object and send it to Discord
        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        file = discord.File(buf, filename="plot.png")
        await ctx.reply(file=file, ephemeral=True)

    @commands.command(aliases=["size", "measure"])
    async def height(self, ctx: commands.Context[Client], *, mean: SizeArg = 1.0):
        """Get a character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        mean : Size
            Average size of the species (default: 1.0)
        """
        await ctx.invoke(self.size, mean=mean)

    @char.group(invoke_without_command=True, aliases=["update"])
    async def edit(
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
            New description
        """
        await ctx.invoke(self.description, oc=oc, description=description)

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
            {"_id": oc._id, "user_id": ctx.author.id, "server": ctx.guild and ctx.guild.id},
            {"$set": {"name": name}},
            upsert=True,
        )
        await ctx.reply(f"Changed {oc.name!r} to {name!r}", ephemeral=True)

    @commands.guild_only()
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
        if ctx.message and ctx.message.attachments:
            description, *imgs = description.split("\n# Attachments\n")
            imgs = "\n".join(x.strip() for x in imgs if x) + "\n".join(
                f"* {item.proxy_url}" for item in ctx.message.attachments
            )
            description = f"{description.strip()}\n# Attachments\n{imgs}"

        if description == oc.description:
            return await ctx.reply("You can't set the same description.", ephemeral=True)

        await self.db.update_one(
            {"_id": oc._id, "user_id": ctx.author.id, "server": ctx.guild and ctx.guild.id},
            {"$set": {"description": description}},
        )
        await ctx.reply(f"Changed description of {oc.name!r}", ephemeral=True)

    @commands.guild_only()
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

    @commands.guild_only()
    @commands.command(aliases=["list", "charlist", "oclist", "ocs"])
    async def listchar(
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
        await ctx.invoke(self.list, user=user)

    @commands.guild_only()
    @commands.command()
    async def purge(self, ctx: commands.Context[Client]):
        """Purge all characters of a user

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        """
        await self.db.delete_many({"user_id": ctx.author.id, "server": ctx.guild and ctx.guild.id})
        await ctx.reply(f"Purged all characters of {ctx.author}", ephemeral=True)

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
                    "server": ctx.guild and ctx.guild.id,
                }
            )
        ]
        ocs.sort(key=lambda oc: oc.oc_name)
        description = "\n".join(f"* {oc.display_name}" for oc in ocs) or "Doesn't have any characters."

        embed = discord.Embed(
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
                    "server": itx.guild_id,
                }
            )
        ]
        ocs.sort(key=lambda oc: oc.oc_name)
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
