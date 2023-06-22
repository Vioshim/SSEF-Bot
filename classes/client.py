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

import os
import sys
from logging import Logger
from pathlib import Path, PurePath
from textwrap import TextWrapper

import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection


class Client(commands.Bot):
    def __init__(self, log: Logger) -> None:
        super(Client, self).__init__(
            intents=discord.Intents.all(),
            owner_id=678374009045254198,
            command_prefix=commands.when_mentioned_or("!"),
            description="SSEF Discord Bot",
            command_attrs=dict(hidden=True),
            case_insensitive=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.log = log
        self.wrapper = TextWrapper(
            width=2000,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
            drop_whitespace=True,
            fix_sentence_endings=False,
        )
        self.mongodb = AsyncIOMotorClient(os.getenv("MONGO_URI"))

    def db(self, db: str) -> AsyncIOMotorCollection:
        return self.mongodb.discord[db]

    async def on_error(self, event_method: str, /, *args, **kwargs) -> None:
        self.log.exception(
            "Ignoring exception in %s",
            event_method,
            exc_info=sys.exc_info(),
        )

    async def setup_hook(self) -> None:
        await self.load_extension("jishaku")
        path = Path("cogs")
        for cog in map(PurePath, path.glob("*/__init__.py")):
            route = ".".join(cog.parts[:-1])
            try:
                await self.load_extension(route)
            except Exception as e:
                self.log.exception(
                    "Exception while loading %s",
                    route,
                    exc_info=e,
                )
            else:
                self.log.info(
                    "Successfully loaded %s",
                    route,
                )
