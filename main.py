from sqlite3 import Error, IntegrityError
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
DB_PATH = 'ranger_db.db'

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
        if conn:
            conn.close()
        return None


async def interpret_command(command, params, message):
    match command:
        case 'conf':
            await configure_bot(params, message)
        case 'help':
            await send_help(message)
        case 'viewreqrg':
            await view_required_rolegroups(message)
        case _:
            await message.channel.send('ERROR: Unknown Command!')


async def send_help(message):
    help_file = open('help_doc.txt', 'r')
    help_text = help_file.read()
    help_file.close()
    await message.channel.send(help_text)


async def configure_bot(params, message):
    sub_comm = params.pop(0)
    match sub_comm:
        case 'addreqrg': await add_required_rolegroup(params, message)


async def add_required_rolegroup(params, message):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    try:
        db_cursor.execute(f"""
            INSERT INTO RoleGroups (group_name, group_required, guild_id) VALUES('{params[0]}', 1, {message.guild.id})
        """)
        db_conn.commit()
        await message.channel.send(f'Successful addition of role group: {params[0]}')
    except IntegrityError as e:
        await message.channel.send(f'ERROR: Role Group - {params[0]} already exists!')
        print(e)
    db_cursor.close()
    db_conn.close()


async def view_required_rolegroups(message):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    rows = None
    try:
        db_cursor.execute(f"""
                SELECT * FROM RoleGroups WHERE guild_id = {message.guild.id} AND group_required = 1
            """)
        rows = db_cursor.fetchall()
    except Error as e:
        await message.channel.send('ERROR: Failed to retrieve role groups for this server!')
        print(e)
    if rows is not None:
        role_groups = []
        message_content = ''
        for row in rows:
            role_group = models.RoleGroup(row[0], row[1], row[2], row[3])
            role_groups.append(role_group)
        item_number = 1
        for role_group in role_groups:
            if item_number != 1:
                message_content += '\n'
            group_required_text = 'Yes' if role_group.group_required == 1 else 'No'
            message_content += f'{item_number}. Name: {role_group.group_name}, IsRequired: {group_required_text}'
            item_number += 1
        await message.channel.send(message_content)
    else:
        await message.channel.send('NOTE: This server has no required role groups')
    db_cursor.close()
    db_conn.close()


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
    db_cursor.executescript(init_sql_comm)
    db_cursor.close()
    db_conn.close()


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
    db_conn.close()


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
    db_conn.close()


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(BOT_CMD_INDICATOR):
        full_command = message.content.split(BOT_CMD_INDICATOR, 1)[1]
        params = full_command.split(' ')
        command = params.pop(0)
        await interpret_command(command, params, message)


client.run(TOKEN)
