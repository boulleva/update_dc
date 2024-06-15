import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import logging
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import config
from nextcord import File, ButtonStyle, Embed, Color, SelectOption, Intents, Interaction, SlashOption, Member
from nextcord.ui import Button, View, Select

# Change logging level from DEBUG to INFO
logging.basicConfig(level=logging.INFO)

intents = Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='^', intents=intents)

# AFK dictionary to store user AFK status and message
afk_users = {}

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}
ffmpeg_options = {'options': '-vn'}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            return [cls(discord.FFmpegPCMAudio(ytdl.prepare_filename(entry), **ffmpeg_options), data=entry) for entry in data['entries']]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return [cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)]

queues = {}

def get_queue(ctx):
    if ctx.guild.id not in queues:
        queues[ctx.guild.id] = []
    return queues[ctx.guild.id]

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')

    activity = discord.Streaming(name="OFFICIAL DISCORD ACA NATASHA", url="https://twitch.tv/fal0_")
    await bot.change_presence(status=discord.Status.online, activity=activity)

@bot.command()
async def ping(ctx):
    await ctx.send('Ada kak!')

@bot.command(name="profile")
async def profile(ctx, user: Member=None):
    if user is None:
        user = ctx.message.author
    inline = True
    embed = Embed(title=f"{user.name}#{user.discriminator}", color=0x0080ff)
    userData = {
        "Mention": user.mention,
        "Nick": user.nick,
        "Created at": user.created_at.strftime("%b %d, %Y, %T"),
        "Joined at": user.joined_at.strftime("%b %d, %Y, %T"),
        "Server": user.guild,
        "Top role": user.top_role
    }
    for fieldName, fieldVal in userData.items():
        embed.add_field(name=fieldName + ":", value=fieldVal, inline=inline)
    embed.set_footer(text=f"id: {user.id}")

    embed.set_thumbnail(url=user.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="server")
async def server(ctx):
    guild = ctx.message.author.guild
    embed = Embed(title=guild.name, color=0x0080ff)
    serverData = {
        "Owner": guild.owner.mention,
        "Channels": len(guild.channels),
        "Members": guild.member_count,
        "Created at": guild.created_at.strftime("%b %d, %Y, %T"),
        "Description": guild.description,
    }
    for fieldName, fieldVal in serverData.items():
        embed.add_field(name=fieldName + ":", value=fieldVal, inline=True)
    embed.set_footer(text=f"id: {guild.id}")

    embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)

@bot.command()
async def support(ctx):
    embed = discord.Embed(
        title="Support Us!", 
        description="Hi!, Support server ini dengan meramaikannya yaa!\n[Join our Discord Server](https://discord.gg/heavenlyaca)", 
        color=discord.Color.blue()
    )
    embed.add_field(name="Komunitas kita!", value="Games,Events,Komunitas", inline=False)
    embed.set_footer(text="Teimakasih sudah menggunakan Official Bot Aca Natasha!")
    await ctx.send(embed=embed)

@bot.command()
async def developer(ctx):
    embed = discord.Embed(
        title="Developer", 
        description="Hi!, Support developer ini dengan link dibawah ini!\n[Orang Orang Baik](https://saweria.co/NoufalZaidan)", 
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command()
async def join(ctx):
    """Joins a voice channel"""
    if ctx.voice_client is not None:
        return await ctx.send("Bot is already in a voice channel.")
    
    if not ctx.message.author.voice:
        await ctx.send(f'{ctx.message.author.name}, you need to join a voice channel first.')
        return

    channel = ctx.message.author.voice.channel
    await channel.connect()

@bot.command()
async def leave(ctx):
    """Leaves a voice channel"""
    if ctx.voice_client:
        await ctx.guild.voice_client.disconnect()
        queues.pop(ctx.guild.id, None)
    else:
        await ctx.send("The bot is not in a voice channel.")

@bot.command()
async def play(ctx, *, url):
    """Plays from a url (almost anything yt_dlp supports)"""
    queue = get_queue(ctx)

    async with ctx.typing():
        try:
            players = await YTDLSource.from_url(url, loop=bot.loop)
            queue.extend(players)
            await ctx.send(f'Added to queue: {len(players)} tracks')

            if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                await play_next(ctx)
        except Exception as e:
            await ctx.send(f'An error occurred: {str(e)}')
            logging.error(f'Error playing audio: {str(e)}')

async def play_next(ctx):
    queue = get_queue(ctx)
    if queue:
        player = queue.pop(0)
        ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop).result())
        await ctx.send(f'Now playing: {player.title}')
    else:
        await asyncio.sleep(300)
        if not get_queue(ctx) and not ctx.voice_client.is_playing():
            await ctx.voice_client.disconnect()

@bot.command()
async def skip(ctx):
    """Skips the current song"""
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped the current song.")

@bot.command()
async def queue(ctx):
    """Shows the current queue"""
    queue = get_queue(ctx)
    if queue:
        message = 'Current queue:\n' + '\n'.join([f'{idx + 1}. {player.title}' for idx, player in enumerate(queue)])
        await ctx.send(message)
    else:
        await ctx.send("The queue is empty.")

@bot.command()
async def clear(ctx):
    """Clears the current queue"""
    queue = get_queue(ctx)
    queue.clear()
    await ctx.send("Cleared the queue.")

@bot.command()
async def pause(ctx):
    """Pauses the current song"""
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused the current song.")
    else:
        await ctx.send("No song is currently playing.")

@bot.command()
async def resume(ctx):
    """Resumes the current song"""
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed the current song.")
    else:
        await ctx.send("The song is not paused.")

@bot.command()
async def stop(ctx):
    """Stops the current song and clears the queue"""
    if ctx.voice_client:
        ctx.voice_client.stop()
        queue = get_queue(ctx)
        queue.clear()
        await ctx.send("Stopped the current song and cleared the queue.")
    else:
        await ctx.send("The bot is not in a voice channel.")

@bot.command()
async def about(ctx):
    """Provides information about the bot"""
    embed = discord.Embed(title="Tentang Aku!~", description="Hi!, aku adalah Official Bot Discord untuk server Aca Natasha!.", color=discord.Color.blue())
    embed.add_field(name="Developer", value="boullevard", inline=False)
    embed.add_field(name="Purpose", value="Untuk menemanimu dalam keseharianmu!", inline=False)
    embed.add_field(name="Commands", value="""
    ^ping - Untuk check apakah aku sudah nyala?!.
    ^join - Join Voice yang ada kamunya!.
    ^leave - Aku pergi dari voicenya ya!~.
    ^play [url] - Play music dari URL Kamu!.
    ^skip - Skip musik yang lagi diputar!.
    ^queue - Memperlihatkan antrian music kamu!.
    ^clear - Membersihkan antrian music kamu!.
    ^pause - Memberhentikan lagu kamu!.
    ^resume - Melanjutkan lagu kamu!.
    ^stop - bot nya berhenti dan membersihkan antrian lagu!.
    ^about - Show this message.
    ^support - Support server ini dengan meramaikannya!.
    ^love - Seberapa love sih kalian xixi   
    ^developer - Support developernya dengan https://saweria.co/NoufalZaidan.
    """, inline=False)
    embed.set_footer(text="Teimakasih sudah menggunakan Official Bot Aca Natasha!")
    await ctx.send(embed=embed)

@bot.command()
async def afk(ctx, *, message="I'm currently AFK."):
    """Sets the user as AFK with a custom message"""
    afk_users[ctx.author.id] = message
    await ctx.send(f'{ctx.author.mention} is now AFK: {message}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.author.id in afk_users:
        afk_users.pop(message.author.id)
        await message.channel.send(f'Selamat datang kembali! {message.author.mention}, kamu sudah kembali hidup!.')

    if message.mentions:
        for user in message.mentions:
            if user.id in afk_users:
                await message.channel.send(f'{user.mention} Orangnya lagi afk kak: {afk_users[user.id]}')

    await bot.process_commands(message)

@join.before_invoke
@play.before_invoke
async def ensure_voice(ctx):
    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("Join dulu voice nya kaka!")
            raise commands.CommandError("Author not connected to a voice channel.")
    elif ctx.voice_client.is_playing():
        ctx.voice_client.stop()

# Run the bot with your token
bot.run(config.BOT_TOKEN)
