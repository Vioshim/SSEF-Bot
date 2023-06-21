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


from __future__ import annotations

import re
from dataclasses import dataclass

from bson.objectid import ObjectId
from discord import Embed, Interaction
from discord.app_commands import Choice, Transform, Transformer
from discord.ext import commands
from discord.utils import remove_markdown
from rapidfuzz import process

from classes.client import Client

matchers = (
    re.compile(r"Name\s*:\s*(.+)", re.IGNORECASE),
    re.compile(r"Species\s*:\s*(.+)", re.IGNORECASE),
    re.compile(r"Level\s*:\s*(\d+)", re.IGNORECASE),
)


@dataclass(slots=True)
class Character:
    _id: ObjectId
    user_id: int
    name: str
    description: str

    def __hash__(self) -> int:
        return hash(self._id)

    def __eq__(self, other: Character) -> bool:
        return self._id == other._id

    @property
    def created_at(self):
        return self._id.generation_time

    @property
    def embed(self):
        embed = Embed(
            title=self.name,
            description=self.description,
            timestamp=self.created_at,
        )
        embed.set_footer(text=f"ID: {self._id}")
        return embed

    @property
    def oc_name(self):
        desc = remove_markdown(self.description)
        name = name[1].strip() if (name := matchers[0].search(desc)) else self.name
        return remove_markdown(name)

    @property
    def display_name(self):
        desc = remove_markdown(self.description)
        nm, mm, lm = matchers
        name = name[1].strip() if (name := nm.search(desc)) else self.name
        name += f"《{mon[1].strip()}》" if (mon := mm.search(desc)) else "《...》"
        if lvl := lm.search(desc):
            name = f"{int(lvl[1]):03d}〙{name}"
        else:
            name = f"...〙{name}"

        return remove_markdown(name)

    @classmethod
    async def converter(cls, ctx: commands.Context[Client] | Interaction[Client], argument: str):
        """Convert a string to a Character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        argument : str
            String to convert

        Returns
        -------
        Character
            Character object
        """
        if isinstance(ctx, Interaction):
            db = ctx.client.db("Characters")
            key = {"user_id": ctx.user.id}
        else:
            db = ctx.bot.db("Characters")
            key = {"user_id": ctx.author.id}

        try:
            key["_id"] = ObjectId(argument)
        except Exception:
            key["name"] = remove_markdown(argument)

        if result := await db.find_one(key):
            return cls(**result)

        ocs = [cls(**oc) async for oc in db.find({"user_id": key["user_id"]})]

        if not ocs:
            raise commands.BadArgument("You have no characters")

        if result := process.extractOne(
            argument,
            ocs,
            processor=lambda x: x.oc_name if isinstance(x, Character) else x,
            score_cutoff=95,
        ):
            return result[0]

        raise commands.BadArgument(f"Character {argument!r} not found")


class CharacterTransformer(commands.Converter[Character], Transformer):
    async def transform(self, interaction: Interaction[Client], argument: str) -> Character:
        db = interaction.client.db("Characters")

        key = {"user_id": interaction.user.id}

        try:
            key["_id"] = ObjectId(argument)
        except Exception:
            key["name"] = remove_markdown(argument)

        if result := await db.find_one(key):
            return Character(**result)

        ocs = [Character(**oc) async for oc in db.find({"user_id": interaction.user.id})]

        if not ocs:
            raise commands.BadArgument("You have no characters")

        if result := process.extractOne(
            argument,
            ocs,
            processor=lambda x: x.name if isinstance(x, Character) else x,
            score_cutoff=95,
        ):
            return result[0]

        raise commands.BadArgument(f"Character {argument!r} not found")

    async def autocomplete(
        self,
        interaction: Interaction[Client],
        value: str,
        /,
    ) -> list[Choice[str]]:
        db = interaction.client.db("Characters")

        return [
            Choice(
                name=o.display_name,
                value=str(o._id),
            )
            async for oc in db.find(
                {
                    "user_id": interaction.user.id,
                    "name": {
                        "$regex": remove_markdown(value) or ".+",
                        "$options": "i",
                    },
                }
            )
            if (o := Character(**oc))
        ]

    async def convert(self, ctx: commands.Context[Client], argument: str):
        """Convert a string to a Character

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        argument : str
            String to convert

        Returns
        -------
        Character
            Character object
        """
        return await Character.converter(ctx, argument)


CharacterArg = Transform[Character, CharacterTransformer]
