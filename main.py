import string
import discord
import random
import sqlite3

TOKEN = "OTI5OTk2NjAwNzQ1NTMzNDQw.Ydvc1A.oqFn08asLY_hwKU0lu7ogeMyz6E"
BOT_CMD_INDICATOR = '!rgr '

client = discord.Client()


@client.event
async def on_ready():
    return


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(BOT_CMD_INDICATOR):
        full_command = message.content.split(BOT_CMD_INDICATOR, 1)[1];
        params = full_command.split(' ')
        command = params.pop(0)
        await interpret_command(command, params, message)


async def interpret_command(command, params, message):
    match command:
        case 'conf': configure_bot(params)
        case 'help': send_help(message)
        case _: await message.channel.send('ERROR: Unknown Command!')


def send_help(message):
    help_text = 'bot still in development'
    message.channel.send(help_text)


def configure_bot(params):
    sub_comm = params.pop(0)
    match sub_comm:
        case 'addreqrg': add_required_rolegroup(params)
    return


def add_required_rolegroup(params):
    return


client.run(TOKEN)
