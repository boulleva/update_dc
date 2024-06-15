import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import os
import asyncio

import logging
logging.basicConfig(level=logging.DEBUG)

# Create a bot instance with a command prefix
intents = discord.Intents.default()
intents.message_content = True  # Enable the message content intent if needed
bot = commands.Bot(command_prefix='?', intents=intents)

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
ffmpeg_options = {
    'options': '-vn'
}
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

@bot.command()
async def join(ctx):
    """Joins a voice channel"""
    if not ctx.message.author.voice:
        await ctx.send(f'{ctx.message.author.name} bot nya belum join voice kak')
        return
    else:
        channel = ctx.message.author.voice.channel
    await channel.connect()

@bot.command()
async def leave(ctx):
    """Leaves a voice channel"""
    if ctx.voice_client:
        await ctx.guild.voice_client.disconnect()
        queues.pop(ctx.guild.id, None)
    else:
        await ctx.send("Bot nya engga masuk voice kak.")

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
        # Wait for a bit before disconnecting to allow for queueing more songs
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
        await ctx.send("Paused the current song!.")
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
    ctx.voice_client.stop()
    queue = get_queue(ctx)
    queue.clear()
    await ctx.send("Stopped the current song and cleared the queue.")

@join.before_invoke
@play.before_invoke
async def ensure_voice(ctx):
    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You are not connected to a voice channel.")
            raise commands.CommandError("Author not connected to a voice channel.")
    elif ctx.voice_client.is_playing():
        ctx.voice_client.stop()

# Run the bot with your token
bot.run('')