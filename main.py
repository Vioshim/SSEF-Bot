# Copyright 2021 Vioshim
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

import asyncio
import os
from logging import getLogger

from dotenv import load_dotenv

from classes.client import Client

load_dotenv()

logger = getLogger(__name__)


async def main() -> None:
    try:
        async with Client(logger) as bot:
            await bot.login(os.getenv("DISCORD_TOKEN", ""))
            await bot.connect(reconnect=True)
    except Exception as e:
        logger.critical(
            "An exception occurred while trying to connect.",
            exc_info=e,
        )


if __name__ == "__main__":
    try:
        import uvloop  # type: ignore

        loop_factory = uvloop.new_event_loop
    except ModuleNotFoundError:
        loop_factory = None
        logger.error("Not using uvloop")

    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(main())
