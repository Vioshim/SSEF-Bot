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

from enum import IntEnum, StrEnum

import pint
from discord import Interaction
from discord.app_commands import Choice, Transform, Transformer
from discord.ext import commands
from quantulum3.parser import parse
from rapidfuzz import process

from classes.client import Client

ureg = pint.UnitRegistry()


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


class Kind(IntEnum):
    Basic = 11
    Middle = 15
    Final = 20
    Legendary = 25


SIZES = dict(
    Eevee=0.3,
    Vaporeon=1.0,
    Jolteon=0.8,
    Flareon=0.9,
    Espeon=0.9,
    Umbreon=1.0,
    Leafeon=1.0,
    Glaceon=0.8,
    Sylveon=1.0,
)


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
        choices = (
            Stats
            if not value
            else (
                x
                for x, _, _ in process.extract(
                    value.title(),
                    Stats,
                    limit=25,
                    score_cutoff=50,
                    processor=lambda x: x.name if isinstance(x, Stats) else x,
                )
            )
        )
        return [Choice(name=item.name, value=item.value) for item in choices]

    async def convert(self, _: commands.Context[Client], argument: str):
        return await self.process(argument)


class SizeTransformer(commands.Converter[float]):
    async def process(self, argument: str) -> float:
        try:
            return sum(item.value * ureg(item.unit.name).to(ureg.meters).magnitude for item in parse(argument))
        except (ValueError, pint.UndefinedUnitError, AttributeError):
            raise commands.BadArgument(f"Invalid measurement: {argument}")

    async def transform(self, _: Interaction[Client], argument: str) -> float:
        return await self.process(argument)

    async def autocomplete(self, _: Interaction[Client], value: str, /) -> list[Choice[str]]:
        choices = (
            SIZES
            if not value
            else (
                x
                for x, _, _ in process.extract(
                    value.title(),
                    choices=SIZES.keys(),
                    limit=25,
                    score_cutoff=50,
                )
            )
        )
        return [Choice(name=item, value=item) for item in choices]

    async def convert(self, _: commands.Context[Client], argument: str):
        return await self.process(argument)


class KindTransformer(commands.Converter[Kind], Transformer):
    async def process(self, argument: str) -> Kind:
        if argument and (
            item := process.extractOne(
                argument.title(),
                Kind,
                score_cutoff=85,
                processor=lambda x: x.name if isinstance(x, Kind) else x,
            )
        ):
            return item[0]

        raise commands.BadArgument(f"Invalid kind string: {argument}")

    async def transform(self, _: Interaction[Client], argument: str) -> Kind:
        return await self.process(argument)

    async def autocomplete(self, _: Interaction[Client], value: str, /) -> list[Choice[str]]:
        choices = (
            Kind
            if not value
            else (
                x
                for x, _, _ in process.extract(
                    value.title(),
                    Kind,
                    limit=25,
                    score_cutoff=50,
                    processor=lambda x: x.name if isinstance(x, Kind) else x,
                )
            )
        )
        return [Choice(name=item.name, value=item.name) for item in choices]

    async def convert(self, _: commands.Context[Client], argument: str) -> Kind:
        return await self.process(argument)


StatArg = Transform[str, StatTransformer]
KindArg = Transform[Kind, KindTransformer]
SizeArg = Transform[float, SizeTransformer]
