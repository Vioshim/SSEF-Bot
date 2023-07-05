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
from enum import StrEnum
from discord.ext import commands
from discord import Interaction
from discord.app_commands import Choice, Transform, Transformer
from classes.client import Client
from rapidfuzz import process


class Stats(StrEnum):
    Eevee = "55 55 50 45 65 55"
    Vaporeon = "130 65 60 110 95 65"
    Jolteon = "65 65 60 110 95 130"
    Flareon = "65 130 60 95 110 65"
    Espeon = "65 65 60 130 95 110"
    Umbreon = "95 65 110 60 130 65"
    Leafeon = "65 110 130 60 65 95"
    Glaceon = "65 60 110 130 95 65"
    Sylveon = "95 65 65 110 130 60"


class StatTransformer(commands.Converter[str], Transformer):
    async def process(self, argument: str) -> str:
        if argument and (
            item := process.extractOne(
                argument.title(),
                Stats,
                score_cutoff=85,
                processor=lambda x: x.name if isinstance(x, Stats) else x,
            )
        ):
            return item[0].value

        value = str(argument or "1 1 1 1 1 1").split()

        if len(value) != 6:
            raise commands.BadArgument(f"Invalid stat string: {argument}")

        try:
            values = [float(x) for x in value]
            return " ".join(map(str, values))
        except ValueError:
            raise commands.BadArgument(f"Invalid stat string: {argument}")

    async def transform(self, _: Interaction[Client], argument: str) -> str:
        return await self.process(argument)

    async def autocomplete(self, _: Interaction[Client], value: str, /) -> list[Choice[str]]:
        choices = Stats if not value else (
            x
            for x, _, _ in process.extract(
                value.title(),
                Stats,
                limit=25,
                score_cutoff=50,
                processor=lambda x: x.name if isinstance(x, Stats) else x,
            )
        )
        return [Choice(name=item.name, value=item.value) for item in choices]

    async def convert(self, _: commands.Context[Client], argument: str):
        return await self.process(argument)


StatArg = Transform[str, StatTransformer]
