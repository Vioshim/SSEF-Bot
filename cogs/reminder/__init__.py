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


from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from typing import Literal, Optional

import discord
from discord.ext import commands, tasks
from discord.utils import snowflake_time, get

from classes.client import Client


@dataclass(slots=True, unsafe_hash=True)
class ReminderInfo:
    user_id: int = field(hash=True)
    channel_id: int = field(hash=True)
    cooldown_time: Optional[int] = field(default=None, hash=False)
    last_message_id: Optional[int] = field(default=None, hash=False)
    notified_already: bool = field(default=False, hash=False)

    @property
    def last_date(self) -> Optional[datetime]:
        if self.last_message_id:
            return snowflake_time(self.last_message_id)

    @property
    def next_fire(self) -> Optional[datetime]:
        if self.last_message_id and self.cooldown_time:
            return snowflake_time(self.last_message_id) + timedelta(seconds=self.cooldown_time)

    def expired(self):
        return bool(
            self.last_message_id
            and self.cooldown_time
            and (snowflake_time(self.last_message_id) + timedelta(seconds=self.cooldown_time)) <= datetime.utcnow()
        )


DEFINITIONS = {
    "30s": 0.5,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "3h": 3 * 60,
    "6h": 6 * 60,
    "12h": 12 * 60,
    "24h": 24 * 60,
    "48h": 2 * 24 * 60,
    "1w": 7 * 24 * 60,
}


class Reminder(commands.Cog):
    """Remind in x minutes to reply if no reply has been said by the user in a channel"""

    def __init__(self, bot: Client):
        self.bot = bot
        self.db = bot.db("Reminder")
        self.info_channels: dict[int, set[ReminderInfo]] = {}

    @commands.Cog.listener()
    async def on_ready(self):
        async for info in self.db.find({}):
            info.pop("_id", None)
            data = ReminderInfo(**info)
            self.info_channels.setdefault(data.channel_id, set())
            self.info_channels[data.channel_id].add(data)

    def cog_load(self) -> None:
        self.check.start()

    def cog_unload(self):
        self.check.cancel()
    
    @tasks.loop(minutes=1)
    async def check(self):

        for channel_id, infos in self.info_channels.items():

            if not (channel := self.bot.get_channel(channel_id)):
                channel = await self.bot.fetch_channel(channel_id)

            for info in filter(lambda i: not i.notified_already and i.expired(), infos):

                reference = channel.get_partial_message(info.last_message_id)

                try:
                    message = await channel.send(
                        "Hello, you haven't replied in a while.\nPlease reply to this message, press ❌ to delete this message.",
                        allowed_mentions=discord.AllowedMentions(replied_user=True),
                        reference=reference,
                    )
                except discord.NotFound:
                    view = discord.ui.View()
                    view.add_item(
                        discord.ui.Button(
                            emoji="🔗",
                            style=discord.ButtonStyle.grey,
                            label="Last message",
                            url=reference.jump_url,
                        )
                    )
                    message = await channel.send(
                        f"Hello <@{info.user_id}>, you haven't replied in a while.\nPlease reply to this message, press ❌ to delete this message.",
                        allowed_mentions=discord.AllowedMentions(users=True),
                        view=view,
                    )

                await message.add_reaction("❌")

                info.notified_already = True

                await self.db.update_one(
                    {"user_id": info.user_id, "channel_id": info.channel_id},
                    {"$set": {"notified_already": True}},
                )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if (
            payload.user_id != self.bot.user.id
            and payload.emoji.name == "❌"
            and payload.message_author_id == self.bot.user.id
        ):
            channel = self.bot.get_channel(payload.channel_id)
            await channel.delete_messages([discord.Object(id=payload.message_id)])

    @commands.command()
    async def remind(
        self,
        ctx: commands.Context[Client],
        time: Literal["None", "30s", "5m", "15m", "30m", "1h", "3h", "6h", "12h", "24h", "48h", "1w"],
        channel: discord.TextChannel | discord.Thread = commands.CurrentChannel,
    ):
        """Remind in x minutes to reply if no reply has been said by the user in a channel

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        time : Literal[str]
            Time to remind in
        channel : discord.TextChannel | discord.Thread, optional
            Channel to remind in, by default CurrentChannel
        """
        key = {"user_id": ctx.author.id, "channel_id": channel.id}

        if (amount := DEFINITIONS.get(time)) == "None":
            self.info_channels.setdefault(channel.id, set()).discard(key)
            await ctx.reply(
                "Reminder has been disabled for this channel.",
                ephemeral=True,
            )
            return await self.db.delete_one(key)
        
        if not (data := (await self.db.find_one(key))):
            data = key

        data["cool_down_time"] = amount
        data.pop("_id", None)

        info = ReminderInfo(**data)
        self.info_channels.setdefault(info.channel_id, set())
        self.info_channels[info.channel_id].add(info)
        await self.db.replace_one(key, asdict(info), upsert=True)
        
        await ctx.reply(
            f"From now on, I will remind you every {amount} minutes to reply if you haven't already.",
            ephemeral=True,
        )


async def setup(bot: Client):
    """Load the cog

    Parameters
    ----------
    bot : Client
       Bot instance
    """
    await bot.add_cog(Reminder(bot))
