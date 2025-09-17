import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from datetime import datetime
import asyncio
import logging
from threading import Thread
from flask import Flask
import time
import json

# Configuration du logging sécurisé
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Serveur web optimisé pour uptime
app = Flask('')

# Variables pour le monitoring
start_time = time.time()
ping_count = 0

@app.route('/')
def home():
    return "Bot Discord Arrivées/Départ est en ligne !"

@app.route('/ping')
def ping():
    """Endpoint ultra-rapide pour uptime monitoring"""
    global ping_count
    ping_count += 1
    return {"pong": True, "timestamp": int(time.time()), "ping_count": ping_count}

@app.route('/status')
def status():
    """Endpoint détaillé avec informations complètes"""
    global ping_count
    ping_count += 1
    uptime = int(time.time() - start_time)
    
    # Vérifier l'état du bot
    bot_status = "online" if bot.is_ready() else "connecting"
    guild_count = len(bot.guilds) if bot.is_ready() else 0
    
    return {
        "status": bot_status,
        "bot": "discord-arrivees-depart", 
        "uptime_seconds": uptime,
        "uptime_formatted": f"{uptime // 3600}h {(uptime % 3600) // 60}m {uptime % 60}s",
        "ping_count": ping_count,
        "guilds": guild_count,
        "timestamp": int(time.time()),
        "user_id": str(bot.user.id) if bot.user else None,
        "latency_ms": round(bot.latency * 1000, 2) if bot.is_ready() else None
    }

@app.route('/health')
def health():
    """Vérification de santé détaillée"""
    try:
        is_healthy = bot.is_ready() and len(bot.guilds) > 0
        
        response_data = {
            "healthy": is_healthy,
            "bot_ready": bot.is_ready(),
            "guilds_connected": len(bot.guilds) if bot.is_ready() else 0,
            "latency_ms": round(bot.latency * 1000, 2) if bot.is_ready() else None,
            "timestamp": int(time.time()),
            "uptime_seconds": int(time.time() - start_time)
        }
        
        return response_data, 200 if is_healthy else 503
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {"healthy": False, "error": "Health check failed", "timestamp": int(time.time())}, 503

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    # Désactiver les logs Flask pour éviter le spam
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)
    
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# Charger les variables d'environnement
load_dotenv()

# Configuration SÉCURISÉE - Jamais de tokens en dur !
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')

# Validation des variables d'environnement
if not TOKEN:
    logger.error("❌ ERREUR CRITIQUE: DISCORD_TOKEN non trouvé dans les variables d'environnement!")
    logger.error("Créez un fichier .env avec: DISCORD_TOKEN=votre_token_ici")
    exit(1)

if not GUILD_ID:
    logger.error("❌ ERREUR CRITIQUE: GUILD_ID non trouvé dans les variables d'environnement!")
    logger.error("Ajoutez dans .env: GUILD_ID=votre_id_serveur")
    exit(1)

try:
    GUILD_ID = int(GUILD_ID)
except ValueError:
    logger.error("❌ ERREUR: GUILD_ID doit être un nombre!")
    exit(1)

# Configuration des intents
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True

# Créer le bot avec configuration sécurisée
bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    help_command=None,  # Désactiver la commande help par défaut
    max_messages=1000   # Limiter le cache des messages
)

def validate_guild(guild_id):
    """Valide que l'ID du serveur est autorisé"""
    return guild_id == GUILD_ID

def validate_category(category_name):
    """Valide que la catégorie est autorisée"""
    return category_name == "「 Salons vocaux 」"

def find_text_channel_for_voice(voice_channel):
    """Trouve le salon où envoyer les notifications - utilise directement le salon vocal"""
    if not voice_channel or not voice_channel.guild:
        return None
    
    guild = voice_channel.guild
    
    # Validation de sécurité
    if not validate_guild(guild.id):
        logger.warning(f"⚠️ Tentative d'accès depuis un serveur non autorisé: {guild.id}")
        return None
    
    # Vérifier que le salon vocal est bien dans la catégorie autorisée
    if not voice_channel.category or not validate_category(voice_channel.category.name):
        return None
    
    # Vérifier que le bot peut envoyer des messages dans ce salon vocal
    if voice_channel.permissions_for(guild.me).send_messages:
        logger.info(f"✅ Utilisation directe du salon vocal: {voice_channel.name} (ID: {voice_channel.id})")
        return voice_channel
    else:
        logger.warning(f"❌ Pas de permission d'écrire dans le salon vocal: {voice_channel.name}")
        return None

@bot.event
async def on_ready():
    """Événement déclenché quand le bot est prêt"""
    logger.info(f'✅ {bot.user} est connecté et prêt!')
    logger.info(f'📊 Serveurs connectés: {len(bot.guilds)}')
    logger.info(f'🔗 URL du bot: https://discord-bot-arrivees-depart.onrender.com')
    logger.info(f'⚡ Latence: {round(bot.latency * 1000, 2)}ms')
    
    # Validation de sécurité : vérifier qu'on est sur le bon serveur
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        logger.error(f'❌ ERREUR SÉCURITÉ: Serveur avec l\'ID {GUILD_ID} non trouvé!')
        logger.error('Le bot va se déconnecter pour des raisons de sécurité.')
        await bot.close()
        return
    
    logger.info(f'🎯 Serveur cible trouvé: {guild.name}')
    logger.info(f'👥 Membres: {guild.member_count}')
    
    # Trouver la catégorie autorisée
    voice_category = None
    target_category_name = "「 Salons vocaux 」"
    
    for category in guild.categories:
        if category.name == target_category_name:
            voice_category = category
            break
    
    if voice_category:
        logger.info(f'✅ Catégorie vocal trouvée: "{voice_category.name}"')
        voice_channels_count = len(voice_category.voice_channels)
        logger.info(f'🔊 Salons vocaux surveillés: {voice_channels_count}')
        
        # Test de connectivité (sans envoyer de message public)
        for vc in voice_category.voice_channels:
            can_write = vc.permissions_for(guild.me).send_messages
            status = "✅" if can_write else "❌"
            logger.info(f'   🔊 {vc.name} (ID: {vc.id}) → {status} Peut écrire')
    else:
        logger.warning(f'❌ Catégorie "「 Salons vocaux 」" non trouvée !')
    
    # Log des endpoints disponibles
    logger.info("🌐 Endpoints disponibles:")
    logger.info("   📍 / → Page d'accueil")
    logger.info("   📍 /ping → Monitoring rapide")
    logger.info("   📍 /status → Statut détaillé")
    logger.info("   📍 /health → Vérification santé")

@bot.event
async def on_voice_state_update(member, before, after):
    """Événement déclenché lors des changements d'état vocal"""
    
    # Validation de sécurité
    if not member or not member.guild:
        return
    
    if not validate_guild(member.guild.id):
        logger.warning(f"⚠️ Tentative d'utilisation depuis un serveur non autorisé: {member.guild.id}")
        return

    # Ne traiter QUE les salons vocaux de la catégorie autorisée
    voice_category_name = "「 Salons vocaux 」"
    
    # Vérifier si le changement concerne la catégorie autorisée
    is_relevant_change = False
    
    if before.channel and before.channel.category and validate_category(before.channel.category.name):
        is_relevant_change = True
    
    if after.channel and after.channel.category and validate_category(after.channel.category.name):
        is_relevant_change = True
    
    # Si le changement ne concerne pas la catégorie autorisée, ignorer
    if not is_relevant_change:
        return
    
    # Sanitize le nom d'utilisateur pour les logs
    safe_username = member.display_name.replace('\n', '').replace('\r', '')[:50]
    
    # Cas 1: Connexion à un salon vocal autorisé
    if (before.channel is None and 
        after.channel is not None and 
        after.channel.category and 
        validate_category(after.channel.category.name)):
        
        logger.info(f"🎯 CONNEXION: {safe_username} → {after.channel.name}")
        
        # Message simple et sécurisé
        try:
            # Escape les caractères spéciaux dans le nom d'utilisateur
            safe_display_name = discord.utils.escape_markdown(member.display_name)
            simple_message = f"🔗 **{safe_display_name}** a rejoint le salon"
            
            await after.channel.send(simple_message)
            logger.info(f"✅ Message envoyé: connexion de {safe_username}")
            
        except discord.HTTPException as e:
            logger.error(f"❌ Erreur envoi message connexion: {e}")
        except Exception as e:
            logger.error(f"❌ Erreur générale connexion: {e}")
    
    # Cas 2: Déconnexion d'un salon vocal autorisé
    elif (before.channel is not None and 
          before.channel.category and 
          validate_category(before.channel.category.name) and
          after.channel is None):
        
        logger.info(f"🎯 DÉCONNEXION: {safe_username} ← {before.channel.name}")
        
        try:
            safe_display_name = discord.utils.escape_markdown(member.display_name)
            simple_message = f"❌ **{safe_display_name}** a quitté le salon"
            
            await before.channel.send(simple_message)
            logger.info(f"✅ Message envoyé: déconnexion de {safe_username}")
            
        except discord.HTTPException as e:
            logger.error(f"❌ Erreur envoi message déconnexion: {e}")
        except Exception as e:
            logger.error(f"❌ Erreur générale déconnexion: {e}")
    
    # Cas 3: Changement entre salons vocaux autorisés
    elif (before.channel is not None and after.channel is not None and 
          before.channel != after.channel):
        
        logger.info(f"🎯 CHANGEMENT: {safe_username} {before.channel.name} → {after.channel.name}")
        
        # Notification de départ (si c'était dans un salon autorisé)
        if (before.channel.category and validate_category(before.channel.category.name)):
            try:
                safe_display_name = discord.utils.escape_markdown(member.display_name)
                safe_channel_name = discord.utils.escape_markdown(after.channel.name)
                leave_message = f"📤 **{safe_display_name}** est parti vers #{safe_channel_name}"
                
                await before.channel.send(leave_message)
                logger.info(f"✅ Message départ envoyé pour {safe_username}")
                
            except discord.HTTPException as e:
                logger.error(f"❌ Erreur envoi message départ: {e}")
            except Exception as e:
                logger.error(f"❌ Erreur générale départ: {e}")
        
        # Notification d'arrivée (si c'est dans un salon autorisé)
        if (after.channel.category and validate_category(after.channel.category.name)):
            try:
                safe_display_name = discord.utils.escape_markdown(member.display_name)
                safe_channel_name = discord.utils.escape_markdown(before.channel.name)
                arrive_message = f"📥 **{safe_display_name}** est arrivé depuis #{safe_channel_name}"
                
                await after.channel.send(arrive_message)
                logger.info(f"✅ Message arrivée envoyé pour {safe_username}")
                
            except discord.HTTPException as e:
                logger.error(f"❌ Erreur envoi message arrivée: {e}")
            except Exception as e:
                logger.error(f"❌ Erreur générale arrivée: {e}")

@bot.command(name='status')
async def status_command(ctx):
    """Commande pour vérifier le statut du bot"""
    # Validation de sécurité
    if not validate_guild(ctx.guild.id):
        logger.warning(f"⚠️ Tentative d'utilisation de !status depuis un serveur non autorisé")
        return
    
    guild = bot.get_guild(GUILD_ID)
    
    # Trouver la catégorie autorisée
    voice_category = None
    for category in guild.categories:
        if validate_category(category.name):
            voice_category = category
            break
    
    voice_channels_count = 0
    total_voice_users = 0
    
    if voice_category:
        voice_channels_count = len(voice_category.voice_channels)
        for vc in voice_category.voice_channels:
            total_voice_users += len(vc.members)
    
    # Calculer l'uptime
    uptime_seconds = int(time.time() - start_time)
    uptime_formatted = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
    
    embed = discord.Embed(
        title="📊 Statut du bot Arrivées/Départ",
        color=0x0099ff,
        timestamp=datetime.now()
    )
    embed.add_field(name="🤖 Bot", value=f"{bot.user.mention}", inline=True)
    embed.add_field(name="🏠 Serveur", value=f"{guild.name}", inline=True)
    embed.add_field(name="📁 Catégorie surveillée", value="「 Salons vocaux 」", inline=True)
    embed.add_field(name="🔊 Salons vocaux", value=f"{voice_channels_count}", inline=True)
    embed.add_field(name="👥 Utilisateurs en vocal", value=f"{total_voice_users}", inline=True)
    embed.add_field(name="⚡ Latence", value=f"{round(bot.latency * 1000, 2)}ms", inline=True)
    embed.add_field(name="⏱️ Uptime", value=uptime_formatted, inline=True)
    embed.add_field(name="📊 Pings reçus", value=f"{ping_count}", inline=True)
    embed.add_field(name="🔒 Sécurité", value="✅ Activée", inline=True)
    
    embed.add_field(
        name="🌐 Endpoints", 
        value="• [/ping](https://discord-bot-arrivees-depart.onrender.com/ping)\n• [/status](https://discord-bot-arrivees-depart.onrender.com/status)\n• [/health](https://discord-bot-arrivees-depart.onrender.com/health)", 
        inline=False
    )
    
    await ctx.send(embed=embed)
    logger.info(f"📊 Commande status exécutée par {ctx.author.display_name}")

@bot.command(name='channels')
async def list_channels(ctx):
    """Commande pour lister tous les salons vocaux surveillés"""
    # Validation de sécurité
    if not validate_guild(ctx.guild.id):
        logger.warning(f"⚠️ Tentative d'utilisation de !channels depuis un serveur non autorisé")
        return
    
    guild = bot.get_guild(GUILD_ID)
    
    # Trouver la catégorie autorisée
    voice_category = None
    for category in guild.categories:
        if validate_category(category.name):
            voice_category = category
            break
    
    if not voice_category:
        embed = discord.Embed(
            title="❌ Erreur",
            description="Catégorie autorisée non trouvée !",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(
        title="🔊 Salons vocaux surveillés",
        description=f"Catégorie: **{voice_category.name}**\nMessages sécurisés dans chaque salon vocal",
        color=0x0099ff,
        timestamp=datetime.now()
    )
    
    for vc in voice_category.voice_channels:
        member_count = len(vc.members)
        status = "🟢" if member_count > 0 else "⚫"
        
        can_write = vc.permissions_for(guild.me).send_messages
        chat_status = "✅ Notifications actives" if can_write else "❌ Pas de permission"
        
        embed.add_field(
            name=f"{status} {vc.name}",
            value=f"👥 {member_count} membre(s)\n💬 {chat_status}",
            inline=True
        )
    
    await ctx.send(embed=embed)
    logger.info(f"📋 Commande channels exécutée par {ctx.author.display_name}")

@bot.command(name='uptime')
async def uptime_command(ctx):
    """Commande pour vérifier l'uptime et les statistiques"""
    # Validation de sécurité
    if not validate_guild(ctx.guild.id):
        logger.warning(f"⚠️ Tentative d'utilisation de !uptime depuis un serveur non autorisé")
        return
    
    uptime_seconds = int(time.time() - start_time)
    uptime_formatted = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
    
    embed = discord.Embed(
        title="⏱️ Statistiques d'uptime",
        color=0x00ff00,
        timestamp=datetime.now()
    )
    
    embed.add_field(name="🚀 Démarrage", value=f"<t:{int(start_time)}:F>", inline=True)
    embed.add_field(name="⏱️ Uptime", value=uptime_formatted, inline=True)
    embed.add_field(name="📊 Pings reçus", value=f"{ping_count}", inline=True)
    embed.add_field(name="⚡ Latence", value=f"{round(bot.latency * 1000, 2)}ms", inline=True)
    embed.add_field(name="🔗 URL", value="[discord-bot-arrivees-depart.onrender.com](https://discord-bot-arrivees-depart.onrender.com)", inline=True)
    embed.add_field(name="📡 Status", value="[/status endpoint](https://discord-bot-arrivees-depart.onrender.com/status)", inline=True)
    
    await ctx.send(embed=embed)
    logger.info(f"⏱️ Commande uptime exécutée par {ctx.author.display_name}")

@bot.event
async def on_command_error(ctx, error):
    """Gestion sécurisée des erreurs de commandes"""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignorer les commandes inexistantes
    
    # Log l'erreur sans exposer d'informations sensibles
    logger.error(f"Erreur de commande: {type(error).__name__}")
    
    # Message générique à l'utilisateur
    if hasattr(ctx, 'send'):
        await ctx.send("❌ Une erreur s'est produite lors de l'exécution de la commande.")

@bot.event
async def on_error(event, *args, **kwargs):
    """Gestion sécurisée des erreurs générales"""
    logger.error(f"Erreur dans l'événement {event}")

# Point d'entrée sécurisé
if __name__ == "__main__":
    logger.info("🚀 Démarrage du bot sécurisé avec optimisations uptime...")
    logger.info("🌐 Endpoints configurés: /, /ping, /status, /health")
    
    # Démarrer le serveur web pour Render
    keep_alive()
    
    try:
        bot.run(TOKEN, log_handler=None)  # Désactiver les logs Discord par défaut
    except discord.LoginFailure:
        logger.error("❌ ERREUR CRITIQUE: Token Discord invalide!")
        logger.error("Vérifiez votre token dans le fichier .env")
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt du bot demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ ERREUR CRITIQUE: {e}")
        logger.error("Le bot va s'arrêter pour des raisons de sécurité")
