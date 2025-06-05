import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('NPCBot')

# Cargar variables de entorno
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN:
    logger.error("DISCORD_TOKEN no encontrado en el archivo .env")
    raise ValueError("DISCORD_TOKEN no encontrado en .env")

# Configuración del bot
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

class NPCShopBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="/", intents=intents)
        self.npcs_file = "npcs.json"
        self.active_shops = {}  # Almacena las tiendas activas por canal
        
    async def setup_hook(self):
        # Añadir el cog directamente sin cargar extensión externa
        await self.add_cog(NPCCommands(self))
        logger.info("Comandos cargados correctamente")

bot = NPCShopBot()

# Clase para manejar NPCs
class NPCManager:
    def __init__(self, filename: str = "npcs.json"):
        self.filename = filename
        self.npcs = self.load_npcs()
    
    def load_npcs(self) -> Dict[str, Dict[str, Any]]:
        """Carga los NPCs desde el archivo JSON"""
        if not os.path.exists(self.filename):
            logger.info(f"Archivo {self.filename} no existe. Creando nuevo...")
            return {}
        
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Cargados {len(data)} NPCs")
            return data
        except Exception as e:
            logger.error(f"Error al cargar NPCs: {e}")
            return {}
    
    def save_npcs(self) -> None:
        """Guarda los NPCs en el archivo JSON"""
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.npcs, f, indent=4, ensure_ascii=False)
            logger.info(f"Guardados {len(self.npcs)} NPCs")
        except Exception as e:
            logger.error(f"Error al guardar NPCs: {e}")
    
    def create_npc(self, nombre: str, dialogo: str, imagen: str, items: List[Dict[str, str]]) -> bool:
        """Crea un nuevo NPC"""
        if nombre in self.npcs:
            return False
        
        self.npcs[nombre] = {
            "dialogo": dialogo,
            "imagen": imagen,
            "items": items,
            "canal_id": None,
            "creado_en": datetime.now().isoformat(),
            "activo": True
        }
        self.save_npcs()
        return True
    
    def edit_npc(self, nombre: str, **kwargs) -> bool:
        """Edita un NPC existente"""
        if nombre not in self.npcs:
            return False
        
        for key, value in kwargs.items():
            if key in self.npcs[nombre]:
                self.npcs[nombre][key] = value
        
        self.npcs[nombre]["modificado_en"] = datetime.now().isoformat()
        self.save_npcs()
        return True
    
    def delete_npc(self, nombre: str) -> bool:
        """Elimina un NPC"""
        if nombre not in self.npcs:
            return False
        
        del self.npcs[nombre]
        self.save_npcs()
        return True
    
    def assign_channel(self, nombre: str, canal_id: int) -> bool:
        """Asigna un NPC a un canal específico"""
        if nombre not in self.npcs:
            return False
        
        self.npcs[nombre]["canal_id"] = canal_id
        self.save_npcs()
        return True
    
    def get_npc(self, nombre: str) -> Optional[Dict[str, Any]]:
        """Obtiene un NPC por nombre"""
        return self.npcs.get(nombre)
    
    def get_npcs_by_channel(self, canal_id: int) -> List[str]:
        """Obtiene todos los NPCs asignados a un canal"""
        return [nombre for nombre, data in self.npcs.items() 
                if data.get("canal_id") == canal_id and data.get("activo", True)]

# Instancia global del manager
npc_manager = NPCManager()

# Clase para manejar la vista de la tienda
class ShopView(discord.ui.View):
    def __init__(self, npc_data: Dict[str, Any], npc_name: str, page: int = 0):
        super().__init__(timeout=300)  # 5 minutos de timeout
        self.npc_data = npc_data
        self.npc_name = npc_name
        self.page = page
        self.items_per_page = 5
        self.max_pages = (len(npc_data["items"]) - 1) // self.items_per_page + 1
        self.update_buttons()
    
    def update_buttons(self):
        """Actualiza el estado de los botones de navegación"""
        self.clear_items()
        
        # Botón anterior
        prev_button = discord.ui.Button(
            label="◀️ Anterior",
            style=discord.ButtonStyle.secondary,
            disabled=self.page == 0
        )
        prev_button.callback = self.previous_page
        self.add_item(prev_button)
        
        # Botón de página actual
        page_button = discord.ui.Button(
            label=f"Página {self.page + 1}/{self.max_pages}",
            style=discord.ButtonStyle.primary,
            disabled=True
        )
        self.add_item(page_button)
        
        # Botón siguiente
        next_button = discord.ui.Button(
            label="Siguiente ▶️",
            style=discord.ButtonStyle.secondary,
            disabled=self.page >= self.max_pages - 1
        )
        next_button.callback = self.next_page
        self.add_item(next_button)
        
        # Botón de cerrar
        close_button = discord.ui.Button(
            label="❌ Cerrar",
            style=discord.ButtonStyle.danger
        )
        close_button.callback = self.close_shop
        self.add_item(close_button)
    
    async def previous_page(self, interaction: discord.Interaction):
        """Página anterior"""
        self.page = max(0, self.page - 1)
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def next_page(self, interaction: discord.Interaction):
        """Página siguiente"""
        self.page = min(self.max_pages - 1, self.page + 1)
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def close_shop(self, interaction: discord.Interaction):
        """Cierra la tienda"""
        await interaction.response.edit_message(
            content="*La tienda ha sido cerrada.*",
            embed=None,
            view=None
        )
        self.stop()
    
    def create_embed(self) -> discord.Embed:
        """Crea el embed de la tienda"""
        embed = discord.Embed(
            title=f"🏪 {self.npc_name}",
            description=f"*{self.npc_data['dialogo']}*",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        if self.npc_data.get("imagen"):
            embed.set_thumbnail(url=self.npc_data["imagen"])
        
        # Calcular items a mostrar
        start_idx = self.page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.npc_data["items"]))
        
        if self.npc_data["items"]:
            items_text = ""
            for i, item in enumerate(self.npc_data["items"][start_idx:end_idx], start=start_idx + 1):
                items_text += f"**{i}. {item['nombre']}**\n"
                items_text += f"   💰 Precio: {item['precio']}\n"
                if item.get("imagen"):
                    items_text += f"   🔗 [Ver imagen]({item['imagen']})\n"
                items_text += "\n"
            
            embed.add_field(
                name="📦 Items Disponibles",
                value=items_text or "No hay items disponibles",
                inline=False
            )
        else:
            embed.add_field(
                name="📦 Items Disponibles",
                value="*Esta tienda no tiene items en este momento*",
                inline=False
            )
        
        embed.set_footer(text=f"Página {self.page + 1} de {self.max_pages}")
        return embed
    
    async def on_timeout(self):
        """Cuando la vista expira"""
        for item in self.children:
            item.disabled = True

# Cog para los comandos
class NPCCommands(commands.Cog):
    def __init__(self, bot: NPCShopBot):
        self.bot = bot
    
    @app_commands.command(name="crear_npc", description="Crea un NPC tienda personalizado")
    @app_commands.describe(
        nombre="Nombre del NPC",
        dialogo="Mensaje o diálogo del NPC",
        imagen="URL de la imagen que representa al NPC",
        items="Lista de ítems: nombre,precio,url;nombre,precio,url (URL opcional)"
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def crear_npc(self, interaction: discord.Interaction, nombre: str, dialogo: str, imagen: str, items: str):
        """Crea un nuevo NPC"""
        await interaction.response.defer(ephemeral=True)
        
        # Validar nombre
        if len(nombre) > 50:
            await interaction.followup.send("❌ El nombre del NPC no puede tener más de 50 caracteres.", ephemeral=True)
            return
        
        # Validar si ya existe
        if npc_manager.get_npc(nombre):
            await interaction.followup.send(f"❌ Ya existe un NPC llamado '{nombre}'.", ephemeral=True)
            return
        
        # Parsear items
        lista_items = []
        try:
            if items.strip():
                for entrada in items.split(";"):
                    partes = [x.strip() for x in entrada.split(",")]
                    if len(partes) < 2:
                        raise ValueError("Formato incorrecto")
                    
                    item_data = {
                        "nombre": partes[0],
                        "precio": partes[1],
                        "imagen": partes[2] if len(partes) > 2 else None
                    }
                    lista_items.append(item_data)
        except Exception as e:
            await interaction.followup.send(
                "❌ Error al procesar los ítems. Formato: nombre,precio[,url];...",
                ephemeral=True
            )
            return
        
        # Crear NPC
        if npc_manager.create_npc(nombre, dialogo, imagen, lista_items):
            embed = discord.Embed(
                title="✅ NPC Creado Exitosamente",
                description=f"**Nombre:** {nombre}\n**Items:** {len(lista_items)}",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=imagen)
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"NPC '{nombre}' creado por {interaction.user}")
        else:
            await interaction.followup.send("❌ Error al crear el NPC.", ephemeral=True)
    
    @app_commands.command(name="editar_npc", description="Edita un NPC existente")
    @app_commands.describe(
        nombre="Nombre del NPC a editar",
        nuevo_dialogo="Nuevo diálogo (opcional)",
        nueva_imagen="Nueva URL de imagen (opcional)",
        nuevos_items="Nuevos items (opcional, mismo formato que crear_npc)"
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def editar_npc(self, interaction: discord.Interaction, nombre: str, 
                         nuevo_dialogo: Optional[str] = None,
                         nueva_imagen: Optional[str] = None,
                         nuevos_items: Optional[str] = None):
        """Edita un NPC existente"""
        await interaction.response.defer(ephemeral=True)
        
        if not npc_manager.get_npc(nombre):
            await interaction.followup.send(f"❌ No existe un NPC llamado '{nombre}'.", ephemeral=True)
            return
        
        kwargs = {}
        if nuevo_dialogo:
            kwargs["dialogo"] = nuevo_dialogo
        if nueva_imagen:
            kwargs["imagen"] = nueva_imagen
        if nuevos_items:
            try:
                lista_items = []
                for entrada in nuevos_items.split(";"):
                    partes = [x.strip() for x in entrada.split(",")]
                    if len(partes) < 2:
                        raise ValueError("Formato incorrecto")
                    
                    item_data = {
                        "nombre": partes[0],
                        "precio": partes[1],
                        "imagen": partes[2] if len(partes) > 2 else None
                    }
                    lista_items.append(item_data)
                kwargs["items"] = lista_items
            except Exception:
                await interaction.followup.send(
                    "❌ Error al procesar los nuevos ítems.",
                    ephemeral=True
                )
                return
        
        if npc_manager.edit_npc(nombre, **kwargs):
            await interaction.followup.send(f"✅ NPC '{nombre}' editado exitosamente.", ephemeral=True)
            logger.info(f"NPC '{nombre}' editado por {interaction.user}")
        else:
            await interaction.followup.send("❌ Error al editar el NPC.", ephemeral=True)
    
    @app_commands.command(name="asignar_npc", description="Asigna un NPC a un canal específico")
    @app_commands.describe(
        nombre="Nombre del NPC",
        canal="Canal donde estará disponible el NPC"
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def asignar_npc(self, interaction: discord.Interaction, nombre: str, canal: discord.TextChannel):
        """Asigna un NPC a un canal"""
        await interaction.response.defer(ephemeral=True)
        
        if not npc_manager.get_npc(nombre):
            await interaction.followup.send(f"❌ No existe un NPC llamado '{nombre}'.", ephemeral=True)
            return
        
        if npc_manager.assign_channel(nombre, canal.id):
            embed = discord.Embed(
                title="✅ NPC Asignado",
                description=f"**NPC:** {nombre}\n**Canal:** {canal.mention}",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"NPC '{nombre}' asignado a canal {canal.name} por {interaction.user}")
        else:
            await interaction.followup.send("❌ Error al asignar el NPC.", ephemeral=True)
    
    @app_commands.command(name="llamar_npc", description="Invoca un NPC en el canal actual")
    @app_commands.describe(nombre="Nombre del NPC a invocar (opcional, muestra lista si no se especifica)")
    async def llamar_npc(self, interaction: discord.Interaction, nombre: Optional[str] = None):
        """Invoca un NPC en el canal actual"""
        await interaction.response.defer()
        
        canal_id = interaction.channel_id
        
        # Si no se especifica nombre, mostrar NPCs disponibles
        if not nombre:
            npcs_disponibles = npc_manager.get_npcs_by_channel(canal_id)
            
            if not npcs_disponibles:
                await interaction.followup.send("❌ No hay NPCs asignados a este canal.")
                return
            
            embed = discord.Embed(
                title="🏪 NPCs Disponibles en este Canal",
                description="Usa `/llamar_npc nombre:NombreDelNPC` para invocar uno.",
                color=discord.Color.blue()
            )
            
            for npc_name in npcs_disponibles:
                npc_data = npc_manager.get_npc(npc_name)
                embed.add_field(
                    name=npc_name,
                    value=f"_{npc_data['dialogo'][:50]}..._" if len(npc_data['dialogo']) > 50 else f"_{npc_data['dialogo']}_",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            return
        
        # Verificar si el NPC existe
        npc_data = npc_manager.get_npc(nombre)
        if not npc_data:
            await interaction.followup.send(f"❌ No existe un NPC llamado '{nombre}'.")
            return
        
        # Verificar si el NPC está asignado a este canal
        if npc_data.get("canal_id") != canal_id:
            await interaction.followup.send(f"❌ El NPC '{nombre}' no está disponible en este canal.")
            return
        
        # Crear y mostrar la tienda
        view = ShopView(npc_data, nombre)
        embed = view.create_embed()
        
        await interaction.followup.send(embed=embed, view=view)
        logger.info(f"NPC '{nombre}' invocado por {interaction.user} en canal {interaction.channel.name}")
    
    @app_commands.command(name="lista_npcs", description="Muestra todos los NPCs creados")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lista_npcs(self, interaction: discord.Interaction):
        """Lista todos los NPCs"""
        await interaction.response.defer(ephemeral=True)
        
        npcs = npc_manager.npcs
        if not npcs:
            await interaction.followup.send("❌ No hay NPCs creados.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📋 Lista de NPCs",
            description=f"Total: {len(npcs)} NPCs",
            color=discord.Color.blue()
        )
        
        for nombre, data in list(npcs.items())[:25]:  # Discord limit
            canal_text = f"<#{data['canal_id']}>" if data.get('canal_id') else "Sin asignar"
            items_count = len(data.get('items', []))
            embed.add_field(
                name=nombre,
                value=f"**Canal:** {canal_text}\n**Items:** {items_count}",
                inline=True
            )
        
        if len(npcs) > 25:
            embed.set_footer(text=f"Mostrando 25 de {len(npcs)} NPCs")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="eliminar_npc", description="Elimina un NPC")
    @app_commands.describe(nombre="Nombre del NPC a eliminar")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def eliminar_npc(self, interaction: discord.Interaction, nombre: str):
        """Elimina un NPC"""
        await interaction.response.defer(ephemeral=True)
        
        if not npc_manager.get_npc(nombre):
            await interaction.followup.send(f"❌ No existe un NPC llamado '{nombre}'.", ephemeral=True)
            return
        
        # Confirmación
        embed = discord.Embed(
            title="⚠️ Confirmar Eliminación",
            description=f"¿Estás seguro de que quieres eliminar el NPC '{nombre}'?",
            color=discord.Color.orange()
        )
        
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.value = None
            
            @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
            async def confirm(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.value = True
                self.stop()
            
            @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
            async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.value = False
                self.stop()
        
        view = ConfirmView()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        await view.wait()
        
        if view.value:
            if npc_manager.delete_npc(nombre):
                await interaction.edit_original_response(
                    content=f"✅ NPC '{nombre}' eliminado exitosamente.",
                    embed=None,
                    view=None
                )
                logger.info(f"NPC '{nombre}' eliminado por {interaction.user}")
            else:
                await interaction.edit_original_response(
                    content="❌ Error al eliminar el NPC.",
                    embed=None,
                    view=None
                )
        else:
            await interaction.edit_original_response(
                content="Eliminación cancelada.",
                embed=None,
                view=None
            )

# Eventos del bot
@bot.event
async def on_ready():
    logger.info(f"Bot conectado como {bot.user} (ID: {bot.user.id})")
    logger.info(f"En {len(bot.guilds)} servidores")
    
    # Sincronizar comandos
    try:
        synced = await bot.tree.sync()
        logger.info(f"Sincronizados {len(synced)} comandos slash")
    except Exception as e:
        logger.error(f"Error al sincronizar comandos: {e}")
    
    # Establecer presencia
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="las tiendas del reino"
        )
    )

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ No tienes permisos para usar este comando.")
    else:
        logger.error(f"Error en comando: {error}")

if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Error al iniciar el bot: {e}")