import asyncio
from sqlite3 import IntegrityError
import models
import discord
import sqlite3
import os
import apputil


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
            conn.cursor().execute('PRAGMA foreign_keys = ON')
            return conn
        new_db_file = open(DB_PATH, 'w')
        new_db_file.close()
        conn = sqlite3.connect(DB_PATH)
        conn.cursor().execute('PRAGMA foreign_keys = ON')
        return conn
    except Exception as e:
        print(e)
        if conn:
            conn.close()
        return None


async def interpret_command(command, params, message):
    match command:
        case 'conf':
            await configure_bot(params, message)
        case 'help':
            await send_help(message, 'help_doc.txt')
        case 'viewreqrg':
            await view_required_role_groups(message)
        case 'leaveguild':
            await leave_guild(message)
        case _:
            await message.channel.send('ERROR: Unknown Command!')


async def send_help(message, filename):
    try:
        help_file = open(filename, 'r')
        help_text = help_file.read()
        help_file.close()
        await message.channel.send(help_text)
    except Exception as e:
        await message.channel.send('ERROR: Unable to display help file!')
        print(e)


async def configure_bot(params, message):
    sub_comm = params.pop(0)
    match sub_comm:
        case 'addreqrg': await add_required_role_group(params, message)
        case 'editrg': await edit_role_group(params, message)
        case 'deleterg': await delete_role_group(params, message)
        case 'addrolestorg': await add_roles_to_role_group(params, message)
        case 'addrolestorgbyid': await add_roles_to_role_group_by_id(params, message)
        case 'reassrlestorg': await reassign_roles_to_role_group(params, message)
        case 'reassrlestorgbyid': await reassign_roles_to_role_group_by_id(params, message)
        case 'delroles': await delete_roles(message)
        case 'delrolesbyid': await delete_roles_by_id(params, message)
        case 'help': await send_help(message, 'conf_help_doc.txt')


async def add_required_role_group(params, message):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    try:
        # Check if the name is defined (null or whitespace names not allowed)
        if apputil.is_null_or_whitespace(params[0]):
            await message.channel.send('ERROR: In command addreqrg [name], the field [name] has to be defined!')
            return
        rows = db_cursor.execute(f"""
            SELECT * FROM RoleGroups WHERE group_name = '{params[0]}' AND guild_id = {message.guild.id}
        """).fetchall()
        if len(rows) == 0:
            db_cursor.execute(f"""
                INSERT INTO RoleGroups (group_name, group_required, guild_id) 
                VALUES('{params[0]}', 1, {message.guild.id})
            """)
            db_conn.commit()
            await message.channel.send(f'Successful addition of role group: {params[0]}')
        else:
            await message.channel.send(f"""
                ERROR: Role Group named: '{params[0]}' already exists!
            """)
    except IndexError as e:
        await message.channel.send("""
            Please make sure command is in the following format: addreqrg [name]
        """)
        print(e)
    except Exception as e:
        await message.channel.send('ERROR: Unable to add new role group record!')
        print(e)
    db_cursor.close()
    db_conn.close()


async def view_required_role_groups(message):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    rows = None
    try:
        db_cursor.execute(f"""
                SELECT * FROM RoleGroups WHERE guild_id = {message.guild.id} AND group_required = 1
            """)
        rows = db_cursor.fetchall()
    except Exception as e:
        await message.channel.send('ERROR: Failed to retrieve role groups for this server!')
        print(e)
    if len(rows) == 0:
        await message.channel.send('NOTE: No role groups to show!')
        db_cursor.close()
        db_conn.close()
        return
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


async def edit_role_group(params, message):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    try:
        # All required parameters must be passed even if they are not to be edited
        if apputil.is_null_or_whitespace(params[0]):
            await message.channel.send("""
                ERROR: In command editrg [name] [new name] [group required], the field [new name] has to be defined!
            """)
            return
        # Check if the user is trying to change the name of an existing role group to one that already
        # exists for that server
        rows = db_cursor.execute(f"""
            SELECT * FROM RoleGroups WHERE group_name = '{params[1]}' AND guild_id = {message.guild.id}
        """).fetchall()
        # Check if the new name corresponds to an existing role group if the new name is different
        if len(rows) == 0 or params[0] == params[1]:
            if params[2] == 'yes' or params[2] == 'no':
                group_required_param = 1 if params[2] == 'yes' else 0
                db_cursor.execute(f"""
                    UPDATE RoleGroups SET group_name = '{params[1]}', group_required = {group_required_param} 
                    WHERE group_name = '{params[0]}' AND guild_id = {message.guild.id}
                """)
                db_conn.commit()
                await message.channel.send(f'Successful edition of role group: {params[0]}')
            else:
                await message.channel.send(
                    """ERROR: For the command, editrg [name] [new name] [group required], 
                    the group required parameter should either be 'yes' or 'no' """
                )
        else:
            await message.channel.send(f"""
                ERROR: Role Group named: '{params[1]}' already exists!
            """)
    except IndexError as e:
        await message.channel.send("""
            Please make sure command is in the following format: editrg [name] [new name] [group_required].
        """)
        print(e)
    except Exception as e:
        await message.channel.send('ERROR: Unable to edit record!')
        print(e)
    db_cursor.close()
    db_conn.close()


async def delete_role_group(params, message):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    try:
        # Check if the user is trying to delete an existing role group for that server
        rows = db_cursor.execute(f"""
                SELECT * FROM RoleGroups WHERE group_name = '{params[0]}' AND guild_id = {message.guild.id}
            """).fetchall()
        if len(rows) != 0:
            db_cursor.execute(f"""
                DELETE FROM RoleGroups WHERE group_name = '{params[0]}' AND guild_id = {message.guild.id}
            """)
            db_conn.commit()
            await message.channel.send(f'Successful deletion of role group: {params[0]}')
        else:
            await message.channel.send(f"""
                NOTE: You attempted to delete a non-existent role group - '{params[0]}'
            """)
    except IndexError as e:
        await message.channel.send("""
            ERROR: Please make sure command is in the following format: deleterg [group name]
        """)
        print(e)
    except Exception as e:
        await message.channel.send('ERROR: Unexpected Error occurred while trying to delete this record')
        print(e)
    db_cursor.close()
    db_conn.close()


async def add_roles_to_role_group(params, message):
    if len(params) == 0:
        await message.channel.send('ERROR: Command must be in the following form: addrolestorg [role group name]'
                                   ' @role1 @role2 ...')
        return
    role_group_name = params.pop(0)
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    role_group = db_cursor.execute(f"""
        SELECT * FROM RoleGroups WHERE group_name = '{role_group_name}' AND guild_id = {message.guild.id}
    """).fetchone()
    if role_group is None:
        await message.channel.send(f'ERROR: Could not find role group - {role_group_name}')
        db_cursor.close()
        db_conn.close()
        return
    message_content = ''
    # The remaining operations are pointless if there are no roles to relocate
    # Also this code prevents an HTTP error that occurs when trying to post an empty body
    if len(message.role_mentions) == 0:
        await message.channel.send('ERROR: No pinged roles to add to role group found!')
        db_cursor.close()
        db_conn.close()
        return
    for role in message.role_mentions:
        try:
            db_cursor.execute(f"""
                INSERT INTO RoleInfo (role_id, role_name, role_grouped, group_id) 
                VALUES({role.id}, '{role.name}', 1, {role_group[0]})
            """)
            message_content += f'Successful addition of role: {role.name} to role group: {role_group[1]}\n'
        except IntegrityError as e:
            message_content += f'ERROR: Cannot add the same role (Role Name: {role.name}) ' \
                               + 'twice to various role groups!\n'
            print(e)
        except Exception as e:
            message_content += f'ERROR: Failed to add role with id: {role.id}\n'
            print(e)
    try:
        db_conn.commit()
        await message.channel.send(message_content)
    except Exception as e:
        await message.channel.send('ERROR: Database error occurred during commitment of database changes!')
        print(e)
    db_cursor.close()
    db_conn.close()


async def add_roles_to_role_group_by_id(params, message):
    if len(params) == 0:
        await message.channel.send('ERROR: Command must be in the following form: addrolestorgbyid [role group name]'
                                   ' [role id 1] [role id 2] ...')
        return
    role_group_name = params.pop(0)
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    role_group = db_cursor.execute(f"""
            SELECT * FROM RoleGroups WHERE group_name = '{role_group_name}' AND guild_id = {message.guild.id}
        """).fetchone()
    if role_group is None:
        await message.channel.send(f'ERROR: Could not find role group - {role_group_name}')
        db_cursor.close()
        db_conn.close()
        return
    if len(params) == 0:
        await message.channel.send(f'ERROR: No role ids have been specified!')
        db_cursor.close()
        db_conn.close()
        return
    message_content = ''
    for role_id in params:
        try:
            role = message.guild.get_role(int(role_id))
            # A client CANNOT add a role from another guild!
            if role is not None:
                db_cursor.execute(f"""
                    INSERT INTO RoleInfo (role_id, role_name, role_grouped, group_id)
                    VALUES({role_id}, '{role.name}', 1, {role_group[0]})
                """)
                message_content += f'Successful addition of role id: {role_id}\n'
            else:
                message_content += f'ERROR: The following role does not exist in this guild: {role_id}\n'
        except ValueError as e:
            message_content += f'ERROR: For Command: addrolestorgbyid [group name] [role id 1] [role id 2] ...' \
                            + f'Each role id MUST be an integer. Failed to add role id: {role_id}\n'
            print(e)
        except IntegrityError as e:
            message_content += f'ERROR: Cannot add the same role (Role Id: {role_id}) ' \
                               + 'twice to various role groups!\n'
            print(e)
        except Exception as e:
            message_content += f'ERROR: Failed to add role with id: {role_id}\n'
            print(e)
    try:
        db_conn.commit()
        await message.channel.send(message_content)
    except Exception as e:
        await message.channel.send('ERROR: Database error occurred during commitment of database changes!')
        print(e)
    db_cursor.close()
    db_conn.close()


async def reassign_roles_to_role_group(params, message):
    try:
        role_group_name = params.pop(0)
        db_conn = create_conn()
        db_cursor = db_conn.cursor()
        role_group = db_cursor.execute(f"""
            SELECT * FROM RoleGroups WHERE group_name = '{role_group_name}' AND guild_id = {message.guild.id}
        """).fetchone()
        # Cannot reassign a role to a non-existent role group
        if role_group is None:
            await message.channel.send(f'ERROR: Role Group: {role_group_name} does not exist!')
            db_cursor.close()
            db_conn.close()
            return
        message_content = ''
        # The remaining operations are pointless if there are no roles to relocate
        # Also this code prevents an HTTP error that occurs when trying to post an empty body
        if len(message.role_mentions) == 0:
            await message.channel.send('ERROR: No pinged roles to add to role group found!')
            db_cursor.close()
            db_conn.close()
            return
        for mention in message.role_mentions:
            try:
                role = db_cursor.execute(f"""
                    SELECT * FROM RoleInfo WHERE role_id = {mention.id}
                """).fetchone()
                if role is None:
                    message_content += f'ERROR: Role with id: {mention.id} has not been registered in a role group!\n'
                else:
                    db_cursor.execute(f"""
                        UPDATE RoleInfo SET group_id = {role_group[0]} WHERE role_id = {mention.id}
                    """)
                    message_content += f'Successful reassignment of role with id: {mention.id} ' \
                                       f'to role group: {role_group[1]}\n'
            except Exception as e:
                await message.channel.send('ERROR: Unknown Error occurred during update operation!')
                print(e)
        try:
            db_conn.commit()
            await message.channel.send(message_content)
        except Exception as e:
            await message.channel.send('ERROR: Unknown error occurred when saving changes to database!')
            print(e)
    except IndexError as e:
        await message.channel.send("""
            ERROR: Command must be in this format: reassrlestorg [group name] @role 1 @role 2 ...
        """)
        print(e)
    except Exception as e:
        await message.channel.send('ERROR: Unknown error occurred!')
        print(e)
    db_cursor.close()
    db_conn.close()


async def reassign_roles_to_role_group_by_id(params, message):
    try:
        role_group_name = params.pop(0)
        db_conn = create_conn()
        db_cursor = db_conn.cursor()
        role_group = db_cursor.execute(f"""
                    SELECT * FROM RoleGroups WHERE group_name = '{role_group_name}' AND guild_id = {message.guild.id}
                """).fetchone()
        # Cannot reassign a role to a non-existent role group
        if role_group is None:
            await message.channel.send(f'ERROR: Role Group: {role_group_name} does not exist!')
            db_cursor.close()
            db_conn.close()
            return
        message_content = ''
        if len(params) == 0:
            await message.channel.send('ERROR: No roles ids specified to add to role group found!')
            db_cursor.close()
            db_conn.close()
            return
        for role_id in params:
            try:
                role = db_cursor.execute(f"""
                    SELECT * FROM RoleInfo WHERE role_id = {role_id}
                """).fetchone()
                if role is None:
                    message_content += f'ERROR: Role with id: {role_id} has not been registered in a role group!\n'
                else:
                    guild_role = message.guild.get_role(int(role_id))
                    if guild_role is None:
                        message_content += f'ERROR: Role with id {role_id} does not exist in this guild!\n'
                    else:
                        db_cursor.execute(f"""
                            UPDATE RoleInfo SET group_id = {role_group[0]} WHERE role_id = {role_id}
                        """)
                        message_content += f'Successful reassignment of role with id: {role_id} ' \
                                           f'to role group: {role_group[1]}\n'
            except Exception as e:
                await message.channel.send('ERROR: Unknown Error occurred during update operation!')
                print(e)
        try:
            db_conn.commit()
            await message.channel.send(message_content)
        except Exception as e:
            await message.channel.send('ERROR: Unknown error occurred when saving changes to database!')
            print(e)
    except IndexError as e:
        await message.channel.send("""
            ERROR: Command must be in this format: reassrlestorgbyid [group name] [role id 1] [role id 2] ...
        """)
        print(e)
    except Exception as e:
        await message.channel.send('ERROR: Unknown error occurred!')
        print(e)
    db_cursor.close()
    db_conn.close()


async def delete_roles(message):
    try:
        db_conn = create_conn()
        db_cursor = db_conn.cursor()
        message_content = ''
        if len(message.role_mentions) == 0:
            await message.channel.send('ERROR: No pinged roles specified for deletion!')
            return
        for mentions in message.role_mentions:
            try:
                role = db_cursor.execute(f"""
                    SELECT * FROM RoleInfo WHERE role_id = {mentions.id}
                """).fetchone()
                if role is None:
                    message_content += f'ERROR: Role with id: {mentions.id} has not been registered in this system!'
                else:
                    db_cursor.execute(f"""
                        DELETE FROM RoleInfo WHERE role_id = {mentions.id}
                    """)
                    message_content += f'Successful deletion of role with id: {mentions.id}\n'
            except Exception as e:
                message_content += f'ERROR: Unknown error occurred when trying to delete role with id: {mentions.id}\n'
                print(e)
        try:
            db_conn.commit()
            await message.channel.send(message_content)
        except Exception as e:
            await message.channel.send('ERROR: Unknown error occurred when saving changes to database!')
            print(e)
    except Exception as e:
        await message.channel.send('ERROR: Unknown Error occurred during delete operation!')
        print(e)
    db_cursor.close()
    db_conn.close()


async def delete_roles_by_id(params, message):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    try:
        message_content = ''
        for param in params:
            try:
                role_id = int(param)
                role = db_cursor.execute(f"""
                    SELECT * FROM RoleInfo WHERE role_id = {role_id}
                """).fetchone()
                if role is None:
                    message_content += f'ERROR: Role with id: {role_id} does not exist in the system!\n'
                else:
                    guild_role = message.guild.get_role(int(role_id))
                    if guild_role is None:
                        message_content += f'ERROR: Role with id: {role_id} has not been registered in a role group!\n'
                    else:
                        db_cursor.execute(f"""
                            DELETE FROM RoleInfo WHERE role_id = {role_id}
                        """)
                        message_content += f'Successful deletion of role with id: {role_id}\n'
            except ValueError as e:
                message_content += f'ERROR: Role with id: {param} is NOT Numeric!\n'
                print(e)
            except Exception as e:
                message_content += f'ERROR: Unknown Error when adding role id: {role_id}\n'
                print(e)
        try:
            db_conn.commit()
            await message.channel.send(message_content)
        except Exception as e:
            await message.channel.send('ERROR: Unknown database error occurred when saving changes!')
            print(e)
    except IndexError as e:
        await message.channel.send("""
            ERROR: Ensure that the command is in the following format: delrolesbyid [role id 1] [role id 2] ...
        """)
        print(e)
    db_cursor.close()
    db_conn.close()


async def leave_guild(message):
    await message.channel.send("""
        NOTE: The bot will leave this server, all role group configurations will be wiped... 
        Are you sure you want to leave? (Type '--confirm' to ensure this bot leaves or type '--rollback'
        to cancel this process)
    """)
    try:
        resp_text = ''

        # Ensures that the bot will ONLY listen to the original poster for their answer
        def check(msg):
            return msg.author.id == message.author.id

        while resp_text != '--confirm' and resp_text != '--rollback':
            response_message = await client.wait_for("message", check=check, timeout=60)
            resp_text = response_message.content
            if resp_text == '--confirm':
                await message.channel.send('NOTE: The Ranger bot has left the server!')
                await message.guild.leave()
            elif resp_text == '--rollback':
                await message.channel.send('NOTE: Leave Guild operation cancelled')
            else:
                await message.channel.send("""
                    NOTE: Please type --confirm or --rollback to continue
                """)
    except asyncio.TimeoutError as e:
        await message.channel.send('ERROR: The operation has been cancelled due to timeout!')
        print(e)


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
    try:
        db_cursor.execute(f"""
            INSERT INTO Servers (guild_id, guild_name) VALUES({guild.id}, '{guild.name}')
        """)
        db_conn.commit()
    # Useful code in case the server id happens to already be in the database for any reason
    except IntegrityError as e:
        print(e)
    db_cursor.close()
    db_conn.close()


@client.event
async def on_guild_remove(guild):
    db_conn = create_conn()
    if db_conn is None:
        return
    db_cursor = db_conn.cursor()
    db_cursor.executescript(f"""
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
