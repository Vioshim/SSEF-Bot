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

from discord import Interaction, TextStyle
from discord.ext import commands
from discord.ui import Modal, TextInput

from classes.character import Character
from classes.client import Client

__all__ = (
    "CreateCharacterModal",
    "UpdateCharacterModal",
)


class CreateCharacterModal(Modal, title="Create Character"):
    name = TextInput(
        label="Name",
        placeholder="Name",
        max_length=256,
        required=True,
    )
    desc = TextInput(
        label="Description",
        style=TextStyle.paragraph,
        placeholder="OC's Description",
        default="Species:\nMoveset:\nLevel:\nAge:\nGender:\nInfo:\nAppearance:",
        max_length=4000,
        required=True,
    )

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
        result = await db.insert_one(
            {
                "name": name,
                "description": desc,
                "user_id": interaction.user.id,
            }
        )
        oc = Character(
            _id=result.inserted_id,
            user_id=interaction.user.id,
            name=name,
            description=desc,
        )

        await interaction.response.send_message(f"Registered {name!r}", embed=oc.embed)
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

        db = interaction.client.db("Characters")
        await db.update_one(
            {"_id": self.character._id},
            {
                "$set": {
                    "name": self.name.value,
                    "description": self.desc.value,
                }
            },
        )

        await interaction.response.send_message(
            f"Updated {self.name.value!r}",
            ephemeral=True,
        )
        self.stop()
