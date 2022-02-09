import string
from sqlite3 import Error
import models
import discord
import sqlite3
import os


def load_token():
    token_file = open('token.txt', 'r')
    token = token_file.read()
    token_file.close()
    return token


TOKEN = load_token()
BOT_CMD_INDICATOR = '!rgr '
DB_PATH = 'ranger_db'

client = discord.Client()


def create_conn():
    conn = None
    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            return conn
        new_db_file = open(DB_PATH, 'w')
        new_db_file.close()
        conn = sqlite3.connect(DB_PATH, 'r')
        return conn
    except Error as e:
        print(e)
        return None


@client.event
async def on_ready():
    db_conn = create_conn()
    if db_conn is None:
        return
    # Create tables if they are non-existent
    db_cursor = db_conn.cursor()
    init_sql_file = open('ranger_db_init.sql', 'r')
    init_sql_comm = init_sql_file.read()
    init_sql_file.close()
    db_cursor.execute(init_sql_comm)


@client.event
async def on_guild_join(guild):
    db_conn = create_conn()
    if db_conn is None:
        return
    db_cursor = db_conn.cursor()
    db_cursor.execute(f"""
        INSERT INTO Servers (guild_id, guild_name) VALUES({guild.id}, '{guild.name}')
    """)
    db_conn.commit()
    db_cursor.close()


@client.event
async def on_guild_remove(guild):
    db_conn = create_conn()
    if db_conn is None:
        return
    db_cursor = db_conn.cursor()
    db_cursor.execute(f"""
        DELETE FROM Servers WHERE guild_id = {guild.id}
    """)
    db_conn.commit()
    db_cursor.close()


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(BOT_CMD_INDICATOR):
        full_command = message.content.split(BOT_CMD_INDICATOR, 1)[1];
        params = full_command.split(' ')
        command = params.pop(0)
        await interpret_command(command, params, message)


client.run(TOKEN)


async def interpret_command(command, params, message):
    match command:
        case 'conf':
            configure_bot(params, message)
        case 'help':
            send_help(message)
        case _:
            await message.channel.send('ERROR: Unknown Command!')


def send_help(message):
    help_text = 'bot still in development'
    message.channel.send(help_text)


def configure_bot(params, message):
    sub_comm = params.pop(0)
    match sub_comm:
        case 'addreqrg': add_required_rolegroup(params, message)


def add_required_rolegroup(params, message):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    db_cursor.execute(f"""
        INSERT INTO RoleGroups 
    """)
    db_conn.commit()
    db_cursor.close()
