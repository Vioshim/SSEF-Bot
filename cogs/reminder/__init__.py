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


import asyncio
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from textwrap import TextWrapper
from typing import Literal, Optional

import discord
from discord.ext import commands, tasks
from discord.utils import format_dt, get, snowflake_time, time_snowflake, utcnow
from rapidfuzz import fuzz
from itertools import chain

from classes.client import Client

TUPPER_REPLY_PATTERN = re.compile(
    r"^> (?P<response>.+)\n"
    r"@(?P<user>.*) \(<@!(?P<user_id>\d+)>\) - \[jump\]\(<https:\/\/discord\.com\/channels\/@me\/(?P<channel>\d+)\/(?P<message>\d+)>\)\n"
    r"(?P<content>.*)$",
    re.DOTALL,
)


@dataclass(slots=True, unsafe_hash=True)
class ReminderInfo:
    user_id: int = field(hash=True)
    channel_id: int = field(hash=True)
    server_id: int = field(hash=True)
    cooldown_time: int = field(default=0, hash=False, compare=False)
    last_message_id: Optional[int] = field(default=None, hash=False, compare=False)
    notified_already: bool = field(default=False, hash=False, compare=False)

    def __post_init__(self):
        self.cooldown_time = self.cooldown_time or 0

    @property
    def jump_url(self):
        url = f"https://discord.com/channels/{self.server_id}/{self.channel_id}"
        return f"{url}/{self.last_message_id}" if self.last_message_id else url

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
    "None": 0,
    "1m": 1,
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
TXT_REMINDER = {
    0: "I'll remind you of this RP without ping if you use </remind:1183192458805387348>",
    None: "Reminder has been disabled for this channel.",
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
        """Load the reminders from the database"""
        async for info in self.db.find({}, {"_id": 0}):
            data = ReminderInfo(**info)
            self.info_channels.setdefault(data.channel_id, set())
            self.info_channels[data.channel_id].add(data)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Update the regex patterns for the no ping role

        Parameters
        ----------
        before : discord.Member
            The member before the update.
        after : discord.Member
            The member after the update.
        """
        roles = set(before.roles) ^ set(after.roles)
        if not (roles and (no_ping_role := get(roles, id=1183590174110785566))):
            return

        rule = await after.guild.fetch_automod_rule(1183591766696411206)
        member_text = self.wrapper.wrap(" ".join(str(x.id) for x in sorted(no_ping_role.members, key=lambda x: x.id)))
        regex_patterns = [f"<@({line.replace(' ', '|')})>" for line in member_text if line]
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

        if not (
            info := get(
                self.info_channels.get(message.channel.id, []),
                user_id=message.author.id,
            )
        ):
            return

        aux_message = message

        context = await self.bot.get_context(message)
        if context.command:
            return

        messages: list[discord.Message] = []

        def checker(m: discord.Message):
            if m.webhook_id and message.channel == m.channel:
                messages.append(m)
            return False

        done, pending = await asyncio.wait(
            [
                asyncio.create_task(
                    self.bot.wait_for("message", check=checker, timeout=2),
                    name="Message",
                ),
                asyncio.create_task(
                    self.bot.wait_for("message_edit", check=lambda x, _: x == message),
                    name="Edit",
                ),
                asyncio.create_task(
                    self.bot.wait_for("message_delete", check=lambda x: x == message),
                    name="Delete",
                ),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for future in pending:
            future.cancel()

        for future in done:
            future.exception()

        futures = (future.get_name() for future in done)
        if "Edit" in futures or not (messages or "Message" in futures):
            return

        attachments = message.attachments
        for msg in sorted(messages, key=lambda x: x.id):
            if data := TUPPER_REPLY_PATTERN.search(msg.content):
                text = str(data.group("content") or msg.content)
            else:
                text = msg.content

            if (
                fuzz.WRatio(text, message.content, score_cutoff=95)
                or text in message.content
                or (
                    attachments
                    and len(attachments) == len(msg.attachments)
                    and all(x.filename == y.filename for x, y in zip(attachments, msg.attachments))
                )
            ):
                aux_message = msg

        info.last_message_id = aux_message.id
        info.notified_already = False
        await self.db.update_one(
            {"user_id": info.user_id, "channel_id": info.channel_id},
            {"$set": {"last_message_id": aux_message.id, "notified_already": False}},
        )

    async def cog_load(self):
        """Start the task loop for the reminders"""
        self.check.start()

    async def cog_unload(self):
        """End the task loop for the reminders"""
        self.check.cancel()

    @staticmethod
    def reminder_check(channel: discord.TextChannel | discord.Thread):
        """Check if the reminder is valid for the channel

        Parameters
        ----------
        channel : discord.TextChannel | discord.Thread
            The channel to check
        """

        def inner_check(item: ReminderInfo) -> bool:
            if item.last_message_id == channel.last_message_id:
                return False

            m = channel.guild.get_member(item.user_id)
            if m and str(m.status) == "offline":
                return False

            return not item.notified_already and item.expired()

        return inner_check

    @tasks.loop(seconds=5)
    async def check(self):
        """Check for reminders that have expired and send a message to the user."""

        for channel_id, infos in self.info_channels.items():
            if not (channel := self.bot.get_channel(channel_id)):
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except discord.NotFound:
                    self.info_channels.pop(channel_id, None)
                    await self.db.delete_many({"channel_id": channel_id})
                    continue

            for info in filter(self.reminder_check(channel), infos):
                reference = channel.get_partial_message(info.last_message_id)
                try:
                    last = await reference.fetch()
                    message = await last.reply(
                        "Hello, you haven't replied in a while."
                        "\nPlease reply to this message, press ❌ to delete this message.",
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
                        f"Hello <@{info.user_id}>, you haven't replied in a while."
                        "\nPlease reply to this message, press ❌ to delete this message.",
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
    @commands.hybrid_group(invoke_without_command=True, case_insensitive=True, fallback="list")
    async def remind(
        self,
        ctx: commands.Context[Client],
        channel: Optional[discord.TextChannel | discord.Thread] = None,
    ):
        """Display reminders for replies in a Discord channel.

        Parameters
        ----------
        ctx : commands.Context
            The context of the command.
        channel : Optional[discord.TextChannel | discord.Thread], optional
            The channel for which the reminder is set. Defaults to the current channel.
        """

        await ctx.reply(
            embed=discord.Embed(
                title=f"Reminders in {channel.name}" if channel else "Reminders",
                description="\n".join(
                    f"* {item.jump_url} - {(nf := item.next_fire) and format_dt(nf, 'R')}"
                    for item in sorted(
                        chain(*self.info_channels.values()),
                        key=lambda x: x.last_message_id or 0,
                        reverse=True,
                    )
                    if item.server_id == ctx.guild.id
                    and item.user_id == ctx.author.id
                    and (channel is None or channel.id == item.channel_id)
                )
                or "No reminders.",
                color=ctx.author.color,
            ),
            ephemeral=True,
        )

    @commands.guild_only()
    @remind.command(name="set")
    async def remind_set(
        self,
        ctx: commands.Context[Client],
        time: Literal[
            "None",
            "1m",
            "5m",
            "15m",
            "30m",
            "1h",
            "3h",
            "6h",
            "12h",
            "24h",
            "48h",
            "1w",
        ] = "None",
        channel: discord.TextChannel | discord.Thread = commands.CurrentChannel,
    ):
        """Set reminders for replies in a Discord channel.

        Parameters
        ----------
        ctx : commands.Context
            The context of the command.
        time : Optional[Literal[str]], optional
            Time interval for setting the reminder. Use 'None' to display current reminders.
        channel : Optional[discord.TextChannel | discord.Thread], optional
            The channel for which the reminder is set. Defaults to the current channel.
        """
        permissions = channel.permissions_for(ctx.author)
        if not (
            permissions.send_messages
            if isinstance(channel, discord.TextChannel)
            else permissions.send_messages_in_threads
        ):
            return await ctx.reply(
                f"You don't have permission to send messages in {channel.mention}",
                ephemeral=True,
            )

        query = {
            "channel_id": channel.id,
            "user_id": ctx.author.id,
            "server_id": ctx.guild.id,
        }

        infos = self.info_channels.get(channel.id, set())
        info = get(infos, **query)
        amount = DEFINITIONS[time]

        if not (data := await self.db.find_one(query, {"_id": 0, "cooldown_time": 0})):
            data = query | {"last_message_id": time_snowflake(utcnow())}

        infos.discard(info)
        info = ReminderInfo(**data, cooldown_time=amount)
        self.info_channels.setdefault(channel.id, set())
        self.info_channels[channel.id].add(info)

        await self.db.replace_one(query, asdict(info), upsert=True)
        await ctx.reply(
            TXT_REMINDER.get(amount, f"Reminder has been set to {amount} minutes."),
            ephemeral=True,
        )

    @commands.guild_only()
    @remind.command(name="clear")
    async def remind_clear(
        self,
        ctx: commands.Context[Client],
        channel: discord.TextChannel | discord.Thread = commands.CurrentChannel,
    ):
        """Clear reminders for replies in a Discord channel.

        Parameters
        ----------
        ctx : commands.Context
            The context of the command.
        channel : Optional[discord.TextChannel | discord.Thread], optional
            The channel for which the reminder is set. Defaults to the current channel.
        """
        query = {
            "channel_id": channel.id,
            "user_id": ctx.author.id,
            "server_id": ctx.guild.id,
        }
        infos = self.info_channels.get(channel.id, set())
        infos.discard(get(infos, **query))
        await self.db.delete_one(query)
        await ctx.reply("Reminder has been cleared.", ephemeral=True)


async def setup(bot: Client):
    """Load the cog

    Parameters
    ----------
    bot : Client
       Bot instance
    """
    await bot.add_cog(Reminder(bot))
