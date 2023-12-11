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


from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from textwrap import TextWrapper
from typing import Literal, Optional

import discord
from discord.ext import commands, tasks
from discord.utils import get, snowflake_time, utcnow

from classes.client import Client


@dataclass(slots=True, unsafe_hash=True)
class ReminderInfo:
    user_id: int = field(hash=True)
    channel_id: int = field(hash=True)
    cooldown_time: Optional[int] = field(default=None, hash=False, compare=False)
    last_message_id: Optional[int] = field(default=None, hash=False, compare=False)
    notified_already: bool = field(default=False, hash=False, compare=False)

    @property
    def last_date(self) -> Optional[datetime]:
        if self.last_message_id:
            return snowflake_time(self.last_message_id)

    @property
    def next_fire(self) -> Optional[datetime]:
        if self.last_message_id and self.cooldown_time:
            return snowflake_time(self.last_message_id) + timedelta(minutes=self.cooldown_time)

    def expired(self):
        return bool(
            self.last_message_id
            and self.cooldown_time
            and (snowflake_time(self.last_message_id) + timedelta(minutes=self.cooldown_time)) <= utcnow()
        )


DEFINITIONS = {
    "30s": 1,
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
        self.wrapper = TextWrapper(width=250, placeholder="", max_lines=10)

    @commands.Cog.listener()
    async def on_ready(self):
        async for info in self.db.find({}):
            info.pop("_id", None)
            data = ReminderInfo(**info)
            self.info_channels.setdefault(data.channel_id, set())
            self.info_channels[data.channel_id].add(data)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        roles = set(before.roles) ^ set(after.roles)
        if roles and (no_ping_role := get(roles, id=1183590174110785566)):
            members_text = " ".join(str(x.id) for x in sorted(no_ping_role.members, key=lambda x: x.id))
            rule = await after.guild.fetch_automod_rule(1183591766696411206)
            regex_patterns = [f"<@({line.replace(' ', '|')})>" for line in self.wrapper.wrap(members_text) if line]
            if rule.trigger.regex_patterns != regex_patterns:
                await rule.edit(trigger=discord.AutoModTrigger(regex_patterns=regex_patterns))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.flags.ephemeral or not message.guild or message.webhook_id or message.author.bot:
            return

        no_ping_role = get(message.guild.roles, id=1183590174110785566)
        if (
            not message.author.guild_permissions.manage_messages
            and not message.author.guild_permissions.administrator
            and no_ping_role
            and any(
                no_ping_role in x.roles
                for x in message.mentions
                if isinstance(x, discord.Member) and x != message.author
            )
        ):
            await message.reply(
                "You shouldn't ping users with the no ping role.",
                allowed_mentions=discord.AllowedMentions(replied_user=True),
            )

        if (infos := self.info_channels.get(message.channel.id)) and (info := get(infos, user_id=message.author.id)):
            info.last_message_id = message.id
            info.notified_already = False
            await self.db.update_one(
                {"user_id": info.user_id, "channel_id": info.channel_id},
                {"$set": {"last_message_id": info.last_message_id, "notified_already": False}},
            )

    def cog_load(self) -> None:
        self.check.start()

    def cog_unload(self):
        self.check.cancel()

    @tasks.loop(seconds=5)
    async def check(self):
        for channel_id, infos in self.info_channels.items():
            if not (channel := self.bot.get_channel(channel_id)):
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except discord.NotFound:
                    self.info_channels.pop(channel_id, None)
                    await self.db.delete_many({"channel_id": channel_id})
                    continue

            def reminder_check(item: ReminderInfo) -> bool:
                m = channel.guild.get_member(item.user_id)
                if m and str(m.status) == "offline":
                    return False

                return not item.notified_already and item.expired()

            for info in filter(reminder_check, infos):
                reference = channel.get_partial_message(info.last_message_id)
                try:
                    last = await reference.fetch()
                    message = await last.reply(
                        "Hello, you haven't replied in a while.\nPlease reply to this message, press ❌ to delete this message.",
                        allowed_mentions=discord.AllowedMentions(replied_user=True),
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
                except (discord.Forbidden, discord.HTTPException):
                    continue

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

    @commands.guild_only()
    @commands.hybrid_command()
    async def remind(
        self,
        ctx: commands.Context[Client],
        time: Optional[Literal["None", "1m", "5m", "15m", "30m", "1h", "3h", "6h", "12h", "24h", "48h", "1w"]] = None,
        channel: discord.TextChannel | discord.Thread = commands.CurrentChannel,
    ):
        """Remind in x minutes to reply if no reply has been said by the user in a channel

        Parameters
        ----------
        ctx : commands.Context
            Context of the command
        time : Optional[Literal[str]], optional
            Time to remind in
        channel : discord.TextChannel | discord.Thread, optional
            Channel to remind in, by default CurrentChannel
        """
        key = {"user_id": ctx.author.id, "channel_id": channel.id}
        infos = self.info_channels.get(channel.id, set())
        permissions = channel.permissions_for(ctx.author)
        able_to_send = (
            permissions.send_messages
            if isinstance(channel, discord.TextChannel)
            else permissions.send_messages_in_threads
        )
        info = get(infos, **key)

        if not able_to_send:
            return await ctx.reply(
                "You don't have the permission to send messages in this channel.",
                ephemeral=True,
            )

        if not (amount := DEFINITIONS.get(time)):
            if not info:
                amount = 1
            else:
                infos.discard(info)
                await ctx.reply(
                    "Reminder has been disabled for this channel.",
                    ephemeral=True,
                )
                return await self.db.delete_one(key)

        if not (data := (await self.db.find_one(key))):
            data = key

        infos.discard(info)
        data["cooldown_time"] = amount
        data.pop("_id", None)

        info = ReminderInfo(**data)
        self.info_channels.setdefault(channel.id, set())
        self.info_channels[channel.id].add(info)

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
