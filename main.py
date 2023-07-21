from discord import Intents
from discord.ext.commands import Bot
from config import *
import sys
from logs import log_last_traceback

sys.excepthook = log_last_traceback

initial_extensions = ['manager']

bot = Bot(command_prefix='>>>', intents = Intents.all(), sync_commands=True, sync_on_cog_reload=True, help_command=None)

for extension in initial_extensions:
    bot.load_extension(f'cogs.{extension}')

@bot.event
async def on_ready():
    print(bot.user.name + " is ready.")

bot.run(TOKEN)