import os
import asyncio
import threading
import traceback

import discord
from discord.ext import commands
from flask import Flask, jsonify


# ============================================================
# CONFIGURACIÓN
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

# ID de tu servidor.
# También podés definir GUILD_ID en las variables de Render.
GUILD_ID = int(os.getenv("GUILD_ID", "1534290216418938891"))

PORT = int(os.getenv("PORT", "10000"))


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return jsonify(
        {
            "status": "online",
            "bot": "Discord Bot",
            "message": "El bot está funcionando correctamente."
        }
    )


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "healthy"
        }
    )


def run_flask():
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False
    )


# ============================================================
# INTENTS
# ============================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
intents.voice_states = True
intents.presences = True


# ============================================================
# BOT
# ============================================================

class ModernBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):

        print("========================================")
        print("Cargando extensiones...")
        print("========================================")

        extensions = [
            "cogs.roles",
            "cogs.stats"
        ]

        for extension in extensions:

            try:
                await self.load_extension(extension)
                print(f"✅ Cargado: {extension}")

            except Exception:
                print(f"❌ Error cargando: {extension}")
                traceback.print_exc()

        # ----------------------------------------------------
        # SINCRONIZACIÓN DE SLASH COMMANDS
        # ----------------------------------------------------

        try:

            guild = discord.Object(id=GUILD_ID)

            self.tree.copy_global_to(guild=guild)

            synced = await self.tree.sync(guild=guild)

            print(
                f"✅ {len(synced)} comandos sincronizados "
                f"en el servidor {GUILD_ID}"
            )

        except Exception:
            print("❌ Error sincronizando comandos.")
            traceback.print_exc()

    async def on_ready(self):

        print("========================================")
        print(f"🤖 Bot: {self.user}")
        print(f"🆔 ID: {self.user.id}")
        print(f"🌐 Servidores: {len(self.guilds)}")
        print("========================================")

        # ----------------------------------------------------
        # PRESENCIA
        # ----------------------------------------------------

        try:

            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name="las estadísticas del servidor"
            )

            await self.change_presence(
                status=discord.Status.idle,
                activity=activity
            )

            print("🟡 Presencia configurada como AUSENTE.")

        except Exception:
            traceback.print_exc()


# ============================================================
# CREAR BOT
# ============================================================

bot = ModernBot()


# ============================================================
# MANEJADOR DE ERRORES
# ============================================================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.CommandNotFound):
        return

    print("Error:")
    traceback.print_exception(
        type(error),
        error,
        error.__traceback__
    )


# ============================================================
# ARRANQUE
# ============================================================

if __name__ == "__main__":

    if not TOKEN:
        raise RuntimeError(
            "Falta la variable de entorno DISCORD_TOKEN."
        )

    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True
    )

    flask_thread.start()

    print("🌐 Flask iniciado.")
    print(f"🔌 Puerto: {PORT}")

    bot.run(TOKEN)