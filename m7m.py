import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from dotenv import load_dotenv

# 1. Cargar variables de entorno
print("▶️ Cargando variables de entorno desde .env...")
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# 2. Verificar si el token existe
if not DISCORD_TOKEN:
    print("❌ ERROR: DISCORD_TOKEN no encontrado en el archivo .env.")
    raise ValueError("DISCORD_TOKEN no encontrado en .env")
else:
    print(f"✅ Token cargado correctamente. (Empieza con: {DISCORD_TOKEN[:5]}...)")

# 3. Configurar el bot
print("▶️ Configurando intents y objeto 'bot'...")
intents = discord.Intents.default()
# Si vas a usar comandos slash en servidores, asegúrate de que el bot tenga privilegios de "applications.commands"
bot = commands.Bot(command_prefix="/", intents=intents)

NPCS_FILE = "npcs.json"

def cargar_npcs():
    print("   • Leer archivo de NPCs:", NPCS_FILE)
    if not os.path.exists(NPCS_FILE):
        print("     - No existe aún. Devuelvo diccionario vacío.")
        return {}
    with open(NPCS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"     - Cargados {len(data)} NPC(s).")
    return data

def guardar_npcs(data):
    print(f"   • Guardando {len(data)} NPC(s) en {NPCS_FILE}...")
    with open(NPCS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print("     - Guardado completo.")

# 4. Definir comando slash para crear NPC
@bot.tree.command(name="crear_npc", description="Crea un NPC tienda personalizado.")
@app_commands.describe(
    nombre="Nombre del NPC",
    dialogo="Mensaje o diálogo del NPC",
    imagen="URL de la imagen que representa al NPC",
    items="Lista de ítems en formato: nombre,precio,url;nombre,precio,url"
)
async def crear_npc(interaction: discord.Interaction, nombre: str, dialogo: str, imagen: str, items: str):
    print(f"\n▶️ Comando /crear_npc invocado por {interaction.user} (ID: {interaction.user.id})")
    npcs = cargar_npcs()

    if nombre in npcs:
        print(f"   ⚠️ Ya existe un NPC llamado '{nombre}'.")
        await interaction.response.send_message(f"⚠️ Ya existe un NPC llamado '{nombre}'. Usa otro nombre.", ephemeral=True)
        return

    lista_items = []
    try:
        for entrada in items.split(";"):
            nombre_item, precio, url = [x.strip() for x in entrada.split(",")]
            lista_items.append({
                "nombre": nombre_item,
                "precio": precio,
                "imagen": url
            })
    except Exception as e:
        print("   ❌ Error al procesar los ítems:", e)
        await interaction.response.send_message("❌ Error al procesar los ítems. Asegúrate del formato: nombre,precio,url;...", ephemeral=True)
        return

    npcs[nombre] = {
        "dialogo": dialogo,
        "imagen": imagen,
        "items": lista_items,
        "canal_id": None
    }

    guardar_npcs(npcs)
    print(f"   ✅ NPC '{nombre}' creado y guardado.")
    await interaction.response.send_message(f"✅ NPC '{nombre}' creado exitosamente.", ephemeral=True)

# 5. Evento on_ready
@bot.event
async def on_ready():
    print("\n▶️ Conectado a Discord. Inicializando sincronización de comandos slash...")
    try:
        await bot.tree.sync()
        print("   ✅ Comandos slash sincronizados con Discord.")
    except Exception as e:
        print("   ❌ Error al sincronizar comandos slash:", e)
    print(f"🎉 Bot conectado como {bot.user} (ID: {bot.user.id})\n")

# 6. Iniciar el bot
if __name__ == "__main__":
    print("▶️ Iniciando bot de Discord con token proporcionado...")
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print("❌ Ocurrió un error al iniciar el bot:", e)
    