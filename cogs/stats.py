import json
import os
import time
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands


# ============================================================
# CONFIG
# ============================================================

DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "stats.json"

XP_PER_MESSAGE = 5

XP_BASE = 100

VOICE_REWARD_ENABLED = True


# ============================================================
# DATA
# ============================================================

def ensure_data():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if not DATA_FILE.exists():

        DATA_FILE.write_text(
            "{}",
            encoding="utf-8"
        )


def load_data():

    ensure_data()

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except (
        json.JSONDecodeError,
        OSError
    ):

        return {}


def save_data(data):

    ensure_data()

    temporary = DATA_FILE.with_suffix(".tmp")

    with open(
        temporary,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4
        )

    os.replace(
        temporary,
        DATA_FILE
    )


# ============================================================
# HELPERS
# ============================================================

def get_user_data(
    data,
    guild_id,
    user_id
):

    guild_id = str(guild_id)
    user_id = str(user_id)

    if guild_id not in data:
        data[guild_id] = {}

    if user_id not in data[guild_id]:

        data[guild_id][user_id] = {
            "messages": 0,
            "voice_seconds": 0,
            "voice_sessions": 0,
            "xp": 0,
            "level": 0,
            "last_message": 0
        }

    return data[guild_id][user_id]


def calculate_level(xp):

    level = 0
    required = XP_BASE

    while xp >= required:

        xp -= required
        level += 1

        required = XP_BASE + (
            level * 50
        )

    return level, xp, required


def format_seconds(seconds):

    seconds = int(seconds)

    days = seconds // 86400
    seconds %= 86400

    hours = seconds // 3600
    seconds %= 3600

    minutes = seconds // 60

    if days:
        return f"{days}d {hours}h {minutes}m"

    if hours:
        return f"{hours}h {minutes}m"

    return f"{minutes}m"


# ============================================================
# COG
# ============================================================

class Stats(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.data = load_data()

        self.voice_join_times = {}

    # ========================================================
    # READY
    # ========================================================

    @commands.Cog.listener()
    async def on_ready(self):

        print("📊 Sistema de estadísticas iniciado.")

    # ========================================================
    # MENSAJES
    # ========================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        if message.guild is None:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        user_data = get_user_data(
            self.data,
            guild_id,
            user_id
        )

        user_data["messages"] += 1

        # -----------------------------------------------
        # XP
        # -----------------------------------------------

        now = time.time()

        # Evita que una ráfaga de mensajes genere demasiado XP.
        if now - user_data.get("last_message", 0) >= 5:

            user_data["xp"] += XP_PER_MESSAGE

            user_data["last_message"] = now

            level, current_xp, required = calculate_level(
                user_data["xp"]
            )

            user_data["level"] = level

        # -----------------------------------------------
        # GUARDAR
        # -----------------------------------------------

        save_data(
            self.data
        )

    # ========================================================
    # VOICE
    # ========================================================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member,
        before,
        after
    ):

        if member.bot:
            return

        guild_id = member.guild.id
        user_id = member.id

        key = (
            guild_id,
            user_id
        )

        # ----------------------------------------------------
        # ENTRA A VOZ
        # ----------------------------------------------------

        if before.channel is None and after.channel is not None:

            self.voice_join_times[key] = time.time()

            user_data = get_user_data(
                self.data,
                guild_id,
                user_id
            )

            user_data["voice_sessions"] += 1

            save_data(
                self.data
            )

        # ----------------------------------------------------
        # CAMBIA DE CANAL
        # ----------------------------------------------------

        elif (
            before.channel is not None
            and after.channel is not None
            and before.channel.id != after.channel.id
        ):

            # Sigue contando el mismo período.
            pass

        # ----------------------------------------------------
        # SALE DE VOZ
        # ----------------------------------------------------

        elif before.channel is not None and after.channel is None:

            joined_at = self.voice_join_times.pop(
                key,
                None
            )

            if joined_at is None:
                return

            elapsed = int(
                time.time() - joined_at
            )

            if elapsed < 0:
                elapsed = 0

            user_data = get_user_data(
                self.data,
                guild_id,
                user_id
            )

            user_data["voice_seconds"] += elapsed

            save_data(
                self.data
            )

    # ========================================================
    # STATS
    # ========================================================

    @app_commands.command(
        name="stats",
        description="Muestra tus estadísticas del servidor."
    )
    async def stats(
        self,
        interaction: discord.Interaction
    ):

        await self.send_user_stats(
            interaction,
            interaction.user
        )

    # ========================================================
    # STATS USUARIO
    # ========================================================

    @app_commands.command(
        name="stats_usuario",
        description="Muestra las estadísticas de un usuario."
    )
    @app_commands.describe(
        usuario="Usuario que querés consultar."
    )
    async def stats_usuario(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member
    ):

        await self.send_user_stats(
            interaction,
            usuario
        )

    # ========================================================
    # STATS MENSAJES
    # ========================================================

    @app_commands.command(
        name="stats_mensajes",
        description="Muestra tu cantidad de mensajes."
    )
    async def stats_mensajes(
        self,
        interaction: discord.Interaction
    ):

        user_data = get_user_data(
            self.data,
            interaction.guild.id,
            interaction.user.id
        )

        await interaction.response.send_message(
            f"💬 **{interaction.user.display_name}**\n\n"
            f"Mensajes enviados: **{user_data['messages']:,}**",
            ephemeral=True
        )

    # ========================================================
    # STATS VOZ
    # ========================================================

    @app_commands.command(
        name="stats_voz",
        description="Muestra tu tiempo en canales de voz."
    )
    async def stats_voz(
        self,
        interaction: discord.Interaction
    ):

        user_data = get_user_data(
            self.data,
            interaction.guild.id,
            interaction.user.id
        )

        seconds = user_data["voice_seconds"]

        # Si actualmente está en voz,
        # sumamos el período actual visualmente.
        key = (
            interaction.guild.id,
            interaction.user.id
        )

        if key in self.voice_join_times:

            seconds += int(
                time.time()
                - self.voice_join_times[key]
            )

        await interaction.response.send_message(
            f"🎤 **{interaction.user.display_name}**\n\n"
            f"Tiempo en voz: **{format_seconds(seconds)}**\n"
            f"Sesiones: **{user_data['voice_sessions']:,}**",
            ephemeral=True
        )

    # ========================================================
    # RANKING
    # ========================================================

    @app_commands.command(
        name="stats_ranking",
        description="Muestra el ranking de actividad del servidor."
    )
    @app_commands.describe(
        tipo="Ranking por mensajes o voz."
    )
    @app_commands.choices(
        tipo=[
            app_commands.Choice(
                name="Mensajes",
                value="messages"
            ),
            app_commands.Choice(
                name="Voz",
                value="voice"
            )
        ]
    )
    async def stats_ranking(
        self,
        interaction: discord.Interaction,
        tipo: app_commands.Choice[str]
    ):

        guild_id = str(
            interaction.guild.id
        )

        guild_data = self.data.get(
            guild_id,
            {}
        )

        if not guild_data:

            await interaction.response.send_message(
                "📊 Todavía no hay estadísticas registradas.",
                ephemeral=True
            )
            return

        if tipo.value == "messages":

            ranking = sorted(
                guild_data.items(),
                key=lambda item: item[1].get(
                    "messages",
                    0
                ),
                reverse=True
            )

            title = "💬 Ranking de mensajes"

        else:

            ranking = sorted(
                guild_data.items(),
                key=lambda item: item[1].get(
                    "voice_seconds",
                    0
                ),
                reverse=True
            )

            title = "🎤 Ranking de voz"

        lines = []

        position = 1

        for user_id, stats in ranking[:10]:

            member = interaction.guild.get_member(
                int(user_id)
            )

            if member is None:
                continue

            if tipo.value == "messages":

                value = (
                    f"{stats.get('messages', 0):,} mensajes"
                )

            else:

                value = (
                    format_seconds(
                        stats.get(
                            "voice_seconds",
                            0
                        )
                    )
                )

            medals = {
                1: "🥇",
                2: "🥈",
                3: "🥉"
            }

            medal = medals.get(
                position,
                f"`#{position}`"
            )

            lines.append(
                f"{medal} {member.mention} — **{value}**"
            )

            position += 1

        if not lines:

            await interaction.response.send_message(
                "📊 Todavía no hay usuarios suficientes.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=title,
            description="\n".join(lines),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="Top 10 del servidor"
        )

        await interaction.response.send_message(
            embed=embed
        )

    # ========================================================
    # RESET
    # ========================================================

    @app_commands.command(
        name="stats_reset",
        description="Reinicia las estadísticas de un usuario."
    )
    @app_commands.describe(
        usuario="Usuario al que se le reiniciarán las estadísticas."
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def stats_reset(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member
    ):

        guild_id = str(
            interaction.guild.id
        )

        user_id = str(
            usuario.id
        )

        if guild_id in self.data:

            self.data[guild_id].pop(
                user_id,
                None
            )

        key = (
            interaction.guild.id,
            usuario.id
        )

        self.voice_join_times.pop(
            key,
            None
        )

        save_data(
            self.data
        )

        await interaction.response.send_message(
            f"🗑️ Se reiniciaron las estadísticas de {usuario.mention}."
        )

    # ========================================================
    # EMBED DE USUARIO
    # ========================================================

    async def send_user_stats(
        self,
        interaction,
        member
    ):

        user_data = get_user_data(
            self.data,
            interaction.guild.id,
            member.id
        )

        total_voice = user_data.get(
            "voice_seconds",
            0
        )

        key = (
            interaction.guild.id,
            member.id
        )

        if key in self.voice_join_times:

            total_voice += int(
                time.time()
                - self.voice_join_times[key]
            )

        level, current_xp, required = calculate_level(
            user_data.get(
                "xp",
                0
            )
        )

        progress = (
            f"{current_xp:,} / {required:,} XP"
        )

        embed = discord.Embed(
            title=f"📊 Estadísticas de {member.display_name}",
            color=discord.Color.blurple()
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.add_field(
            name="💬 Mensajes",
            value=f"**{user_data.get('messages', 0):,}**",
            inline=True
        )

        embed.add_field(
            name="🎤 Tiempo en voz",
            value=f"**{format_seconds(total_voice)}**",
            inline=True
        )

        embed.add_field(
            name="🔊 Sesiones",
            value=f"**{user_data.get('voice_sessions', 0):,}**",
            inline=True
        )

        embed.add_field(
            name="⭐ Nivel",
            value=f"**{level}**",
            inline=True
        )

        embed.add_field(
            name="✨ XP",
            value=f"**{progress}**",
            inline=True
        )

        embed.add_field(
            name="🆔 Usuario",
            value=f"`{member.id}`",
            inline=True
        )

        embed.set_footer(
            text="Estadísticas del servidor"
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):

    await bot.add_cog(
        Stats(bot)
    )