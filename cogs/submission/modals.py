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

import contextlib
from typing import Optional

from discord import Attachment, Interaction, TextStyle
from discord.ext import commands
from discord.ui import Modal, TextInput

from classes.character import Character
from classes.client import Client
from cogs.submission.sheets import Sheet

__all__ = (
    "CreateCharacterModal",
    "UpdateCharacterModal",
)


class CreateCharacterModal(Modal, title="Create Character"):
    def __init__(self, sheet: Sheet = Sheet.Empty, image: Optional[Attachment] = None) -> None:
        super().__init__(timeout=None)
        self.image = image
        self.name = TextInput(
            label="Name",
            placeholder="Name",
            max_length=256,
            required=True,
        )
        self.desc = TextInput(
            label="Description",
            style=TextStyle.paragraph,
            placeholder="OC's Description",
            max_length=4000,
            required=True,
            default=sheet.template,
        )
        self.add_item(self.name)
        self.add_item(self.desc)

    async def on_error(self, interaction: Interaction[Client], error: Exception):
        interaction.client.log.error(
            "An exception occurred while trying to create a character.",
            exc_info=error,
        )

    async def on_submit(self, interaction: Interaction[Client]):
        with contextlib.suppress(commands.BadArgument):
            if oc := await Character.converter(interaction, self.name.value):
                await interaction.response.send_message(
                    f"Character {oc.name!r} already exists!",
                    ephemeral=True,
                )
                return self.stop()

        name, desc = self.name.value.strip(), self.desc.value.strip()
        if not (name and desc):
            await interaction.response.send_message(
                "Name and Description cannot be empty!",
                ephemeral=True,
            )
            return self.stop()

        db = interaction.client.db("Characters")
        await interaction.response.defer(thinking=True, ephemeral=False)
        info = interaction.client.wrapper.wrap(desc)
        for i, text in enumerate(info):
            files = [await self.image.to_file()] if i == len(info) - 1 and self.image else []
            msg = await interaction.followup.send(content=text, files=files, wait=True)
            if msg.attachments:
                self.image = msg.attachments[0]

        if self.image:
            desc, *imgs = desc.split("\n# Attachments\n")
            imgs = "\n".join(x.strip() for x in imgs if x) + f"\n* {self.image.proxy_url}"
            desc = f"{desc.strip()}\n# Attachments\n{imgs}"

        result = await db.insert_one(
            {
                "name": name,
                "description": desc,
                "user_id": interaction.user.id,
                "server": interaction.guild_id,
            }
        )
        oc = Character(
            _id=result.inserted_id,
            user_id=interaction.user.id,
            name=name,
            description=desc,
            server=interaction.guild_id or 0,
        )

        self.stop()


class UpdateCharacterModal(Modal, title="Update Character"):
    def __init__(self, character: Character):
        super(UpdateCharacterModal, self).__init__(timeout=None)
        self.character = character
        self.name = TextInput(
            label="Name",
            placeholder="Name",
            max_length=256,
            default=character.name,
            required=True,
        )
        self.desc = TextInput(
            label="Description",
            style=TextStyle.paragraph,
            placeholder="OC's Description",
            max_length=4000,
            default=character.description,
            required=True,
        )
        self.add_item(self.name)
        self.add_item(self.desc)

    async def on_submit(self, interaction: Interaction[Client]):
        with contextlib.suppress(commands.BadArgument):
            oc = await Character.converter(interaction, self.name.value)
            if oc != self.character:
                await interaction.response.send_message(
                    f"Character {oc.name!r} already exists!",
                    ephemeral=True,
                )
                return self.stop()

        oc = self.character
        name, desc = self.name.value.strip(), self.desc.value.strip()
        if not (name and desc):
            await interaction.response.send_message(
                "Name and Description cannot be empty!",
                ephemeral=True,
            )
            return self.stop()

        db = interaction.client.db("Characters")
        await db.update_one(
            {"_id": oc._id, "server": interaction.guild_id},
            {"$set": {"name": name, "description": desc}},
        )
        await interaction.response.defer(thinking=True, ephemeral=False)
        oc.name, oc.description = name, desc
        for text in interaction.client.wrapper.wrap(oc.description):
            await interaction.followup.send(content=text)

        self.stop()
