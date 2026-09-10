import re

import discord
from discord import app_commands
from discord.ext import commands


# ============================================================
# CONFIG
# ============================================================

MAX_CUSTOM_ROLE_PER_USER = 1

ROLE_PREFIX = "✦ "


# ============================================================
# HELPERS
# ============================================================

def parse_color(value: str):

    value = value.strip().replace("#", "")

    if len(value) not in (6, 8):
        raise ValueError(
            "El color debe tener formato `#RRGGBB`."
        )

    if not re.fullmatch(r"[0-9a-fA-F]+", value):
        raise ValueError(
            "El color contiene caracteres inválidos."
        )

    return discord.Color(int(value[:6], 16))


def extract_custom_emoji(value: str):

    """
    Acepta:

    <:nombre:123456789>
    <a:nombre:123456789>

    También acepta un emoji que venga directamente
    de Discord.
    """

    value = value.strip()

    match = re.fullmatch(
        r"<(a?):([a-zA-Z0-9_]+):(\d+)>",
        value
    )

    if not match:
        return None

    animated = bool(match.group(1))
    emoji_id = int(match.group(3))

    return {
        "id": emoji_id,
        "animated": animated
    }


def find_guild_emoji(guild: discord.Guild, emoji_id: int):

    for emoji in guild.emojis:

        if emoji.id == emoji_id:
            return emoji

    return None


# ============================================================
# COG
# ============================================================

class Roles(commands.GroupCog, name="rol"):

    def __init__(self, bot: commands.Bot):

        self.bot = bot

    # ========================================================
    # CREAR
    # ========================================================

    @app_commands.command(
        name="crear",
        description="Crea tu rol personalizado con color e icono."
    )
    @app_commands.describe(
        nombre="Nombre que tendrá tu rol.",
        color="Color hexadecimal, por ejemplo #7B2CFF.",
        icono="Emoji personalizado del servidor, por ejemplo <:emoji:123456789>."
    )
    async def crear(
        self,
        interaction: discord.Interaction,
        nombre: str,
        color: str,
        icono: str
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        guild = interaction.guild

        if guild is None:
            await interaction.followup.send(
                "❌ Este comando solamente funciona dentro de un servidor.",
                ephemeral=True
            )
            return

        member = interaction.user

        # ----------------------------------------------------
        # PERMISOS DEL BOT
        # ----------------------------------------------------

        me = guild.me

        if me is None:
            await interaction.followup.send(
                "❌ No pude comprobar los permisos del bot.",
                ephemeral=True
            )
            return

        if not me.guild_permissions.manage_roles:

            await interaction.followup.send(
                "❌ Necesito el permiso **Gestionar roles**.",
                ephemeral=True
            )
            return

        # ----------------------------------------------------
        # NOMBRE
        # ----------------------------------------------------

        nombre = nombre.strip()

        if not nombre:
            await interaction.followup.send(
                "❌ El nombre no puede estar vacío.",
                ephemeral=True
            )
            return

        if len(nombre) > 100:

            await interaction.followup.send(
                "❌ El nombre no puede superar los 100 caracteres.",
                ephemeral=True
            )
            return

        # ----------------------------------------------------
        # BUSCAR ROL PERSONALIZADO EXISTENTE
        # ----------------------------------------------------

        existing_role = None

        for role in guild.roles:

            if (
                role.name.startswith(ROLE_PREFIX)
                and role.managed is False
                and role in member.roles
            ):
                existing_role = role
                break

        if existing_role:

            await interaction.followup.send(
                "❌ Ya tenés un rol personalizado.\n"
                f"Usá `/rol editar` para modificar {existing_role.mention}.",
                ephemeral=True
            )
            return

        # ----------------------------------------------------
        # COLOR
        # ----------------------------------------------------

        try:

            role_color = parse_color(color)

        except ValueError as error:

            await interaction.followup.send(
                f"❌ {error}",
                ephemeral=True
            )
            return

        # ----------------------------------------------------
        # EMOJI
        # ----------------------------------------------------

        emoji_data = extract_custom_emoji(icono)

        if emoji_data is None:

            await interaction.followup.send(
                "❌ Tenés que utilizar un emoji personalizado del servidor.\n\n"
                "Ejemplo:\n"
                "`<:emoji:123456789>`",
                ephemeral=True
            )
            return

        emoji = find_guild_emoji(
            guild,
            emoji_data["id"]
        )

        if emoji is None:

            await interaction.followup.send(
                "❌ Ese emoji no pertenece a este servidor.",
                ephemeral=True
            )
            return

        # ----------------------------------------------------
        # CREAR ROL
        # ----------------------------------------------------

        role_name = ROLE_PREFIX + nombre

        try:

            role = await guild.create_role(
                name=role_name,
                color=role_color,
                reason=f"Rol personalizado creado por {member}"
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ No tengo permisos suficientes para crear roles.",
                ephemeral=True
            )
            return

        except discord.HTTPException as error:

            await interaction.followup.send(
                f"❌ Discord rechazó la creación del rol.\n`{error}`",
                ephemeral=True
            )
            return

        # ----------------------------------------------------
        # ICONO REAL DEL ROL
        # ----------------------------------------------------

        try:

            await role.edit(
                display_icon=emoji
            )

        except discord.Forbidden:

            await role.delete(
                reason="No se pudo establecer el icono del rol."
            )

            await interaction.followup.send(
                "❌ El rol fue creado, pero Discord no me permite "
                "establecer el icono. Revisá que el servidor tenga "
                "**Role Icons** habilitado y que el bot tenga "
                "**Gestionar roles**.",
                ephemeral=True
            )
            return

        except discord.HTTPException:

            # Si falla el icono, mantenemos el rol para no perderlo.
            pass

        # ----------------------------------------------------
        # MOVER ROL CERCA DEL USUARIO
        # ----------------------------------------------------

        try:

            bot_top_role = me.top_role

            target_position = max(
                1,
                bot_top_role.position - 1
            )

            await role.edit(
                position=target_position
            )

        except (discord.Forbidden, discord.HTTPException):
            pass

        # ----------------------------------------------------
        # DAR ROL
        # ----------------------------------------------------

        try:

            await member.add_roles(
                role,
                reason="Rol personalizado"
            )

        except discord.Forbidden:

            await role.delete(
                reason="No se pudo asignar el rol."
            )

            await interaction.followup.send(
                "❌ Creé el rol pero no puedo asignártelo. "
                "El rol del bot debe estar por encima del rol creado.",
                ephemeral=True
            )
            return

        # ----------------------------------------------------
        # RESPUESTA
        # ----------------------------------------------------

        embed = discord.Embed(
            title="🎨 Rol personalizado creado",
            description=(
                f"Tu rol {role.mention} fue creado correctamente.\n\n"
                f"**Nombre:** {role.name}\n"
                f"**Color:** `#{role.color.value:06X}`\n"
                f"**Icono:** {emoji}"
            ),
            color=role.color
        )

        embed.set_footer(
            text="Sistema de roles personalizados"
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )

    # ========================================================
    # EDITAR
    # ========================================================

    @app_commands.command(
        name="editar",
        description="Edita tu rol personalizado."
    )
    @app_commands.describe(
        nombre="Nuevo nombre.",
        color="Nuevo color hexadecimal.",
        icono="Nuevo emoji personalizado del servidor."
    )
    async def editar(
        self,
        interaction: discord.Interaction,
        nombre: str | None = None,
        color: str | None = None,
        icono: str | None = None
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        guild = interaction.guild
        member = interaction.user

        role = None

        for r in guild.roles:

            if (
                r.name.startswith(ROLE_PREFIX)
                and r in member.roles
            ):
                role = r
                break

        if role is None:

            await interaction.followup.send(
                "❌ No tenés un rol personalizado.",
                ephemeral=True
            )
            return

        me = guild.me

        if me is None or role >= me.top_role:

            await interaction.followup.send(
                "❌ No puedo modificar ese rol porque está "
                "por encima o al mismo nivel que mi rol.",
                ephemeral=True
            )
            return

        changes = {}

        # ----------------------------------------------------
        # NOMBRE
        # ----------------------------------------------------

        if nombre is not None:

            nombre = nombre.strip()

            if not nombre:

                await interaction.followup.send(
                    "❌ El nombre no puede estar vacío.",
                    ephemeral=True
                )
                return

            if len(nombre) > 100:

                await interaction.followup.send(
                    "❌ El nombre es demasiado largo.",
                    ephemeral=True
                )
                return

            changes["name"] = ROLE_PREFIX + nombre

        # ----------------------------------------------------
        # COLOR
        # ----------------------------------------------------

        if color is not None:

            try:
                changes["color"] = parse_color(color)

            except ValueError as error:

                await interaction.followup.send(
                    f"❌ {error}",
                    ephemeral=True
                )
                return

        # ----------------------------------------------------
        # ICONO
        # ----------------------------------------------------

        if icono is not None:

            emoji_data = extract_custom_emoji(icono)

            if emoji_data is None:

                await interaction.followup.send(
                    "❌ El icono debe ser un emoji personalizado del servidor.",
                    ephemeral=True
                )
                return

            emoji = find_guild_emoji(
                guild,
                emoji_data["id"]
            )

            if emoji is None:

                await interaction.followup.send(
                    "❌ Ese emoji no pertenece a este servidor.",
                    ephemeral=True
                )
                return

            changes["display_icon"] = emoji

        if not changes:

            await interaction.followup.send(
                "❌ No especificaste ningún cambio.",
                ephemeral=True
            )
            return

        try:

            await role.edit(
                reason=f"Rol editado por {member}",
                **changes
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ No tengo permisos para modificar este rol.",
                ephemeral=True
            )
            return

        except discord.HTTPException as error:

            await interaction.followup.send(
                f"❌ Discord rechazó el cambio.\n`{error}`",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            f"✅ Tu rol {role.mention} fue actualizado correctamente.",
            ephemeral=True
        )

    # ========================================================
    # ELIMINAR
    # ========================================================

    @app_commands.command(
        name="eliminar",
        description="Elimina tu rol personalizado."
    )
    async def eliminar(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        guild = interaction.guild
        member = interaction.user

        role = None

        for r in guild.roles:

            if (
                r.name.startswith(ROLE_PREFIX)
                and r in member.roles
            ):
                role = r
                break

        if role is None:

            await interaction.followup.send(
                "❌ No tenés un rol personalizado.",
                ephemeral=True
            )
            return

        me = guild.me

        if me is None or role >= me.top_role:

            await interaction.followup.send(
                "❌ No puedo eliminar ese rol porque está "
                "por encima de mi rol.",
                ephemeral=True
            )
            return

        try:

            await role.delete(
                reason=f"Rol eliminado por {member}"
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ No tengo permisos para eliminar ese rol.",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            "🗑️ Tu rol personalizado fue eliminado.",
            ephemeral=True
        )

    # ========================================================
    # MÍO
    # ========================================================

    @app_commands.command(
        name="mío",
        description="Muestra información de tu rol personalizado."
    )
    async def mio(
        self,
        interaction: discord.Interaction
    ):

        guild = interaction.guild
        member = interaction.user

        role = None

        for r in guild.roles:

            if (
                r.name.startswith(ROLE_PREFIX)
                and r in member.roles
            ):
                role = r
                break

        if role is None:

            await interaction.response.send_message(
                "❌ No tenés un rol personalizado.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎨 Tu rol personalizado",
            color=role.color
        )

        embed.add_field(
            name="Nombre",
            value=role.name,
            inline=False
        )

        embed.add_field(
            name="Color",
            value=f"`#{role.color.value:06X}`",
            inline=True
        )

        embed.add_field(
            name="Posición",
            value=str(role.position),
            inline=True
        )

        embed.add_field(
            name="Menciones",
            value=role.mention,
            inline=False
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # ========================================================
    # INFO
    # ========================================================

    @app_commands.command(
        name="info",
        description="Muestra información de un rol."
    )
    @app_commands.describe(
        rol="Rol que querés consultar."
    )
    async def info(
        self,
        interaction: discord.Interaction,
        rol: discord.Role
    ):

        embed = discord.Embed(
            title="📋 Información del rol",
            color=rol.color
        )

        embed.add_field(
            name="Nombre",
            value=rol.name,
            inline=False
        )

        embed.add_field(
            name="ID",
            value=str(rol.id),
            inline=True
        )

        embed.add_field(
            name="Color",
            value=f"`#{rol.color.value:06X}`",
            inline=True
        )

        embed.add_field(
            name="Miembros",
            value=str(len(rol.members)),
            inline=True
        )

        embed.add_field(
            name="Posición",
            value=str(rol.position),
            inline=True
        )

        embed.add_field(
            name="Mencionable",
            value="Sí" if rol.mentionable else "No",
            inline=True
        )

        embed.add_field(
            name="Gestionado por integración",
            value="Sí" if rol.managed else "No",
            inline=True
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


async def setup(bot: commands.Bot):

    await bot.add_cog(
        Roles(bot)
    )