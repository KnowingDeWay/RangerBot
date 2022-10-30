import asyncio
import this
import threading
from sqlite3 import IntegrityError

import models
from models import RoleGroup, DataType, ModAction
import discord
import apputil
from apputil import create_conn
from threading import Thread
from datetime import datetime, timedelta


def load_token():
    token_file = open('token.txt', 'r')
    token = token_file.read()
    token_file.close()
    return token


TOKEN = load_token()
BOT_CMD_INDICATOR = '!rgr '
DB_PATH = 'ranger_db.db'
RESERVED_CONFIG_PREFIX = 'sys'
CONFIG_VAR_RG_MOD_ACTION = f'{RESERVED_CONFIG_PREFIX}_rg_mod_action'
CONFIG_VAR_RG_ENFORCEMENT_PERIOD = f'{RESERVED_CONFIG_PREFIX}_rg_enf_period'
CONFIG_VAR_RG_ENFORCEMENT_DEADLINE = f'{RESERVED_CONFIG_PREFIX}_rg_enf_deadline'
CONFIG_VAR_RG_PUNISH_MESSAGE = f'{RESERVED_CONFIG_PREFIX}_rg_punish_reason'

client = discord.Client(intents=discord.Intents.all())


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
        case 'viewroles':
            await view_registered_roles(message)
        case 'viewrolesrg':
            await view_roles_for_rolegroup(params, message)
        case 'enforcerg':
            await enforce_mod_action_required_roles(params, message)
        case 'sweepserver':
            await sweep_server(message)
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
        case 'setpunishmsg': await set_punish_message(params, message)
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
            role_group = RoleGroup(row[0], row[1], row[2], row[3])
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
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    try:
        role_group_name = params.pop(0)
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
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    try:
        role_group_name = params.pop(0)
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
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    try:
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
                message_content += f'ERROR: Unknown Error when adding role id: {param}\n'
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


async def view_registered_roles(message):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    message_content = ''
    role_no = 1
    try:
        roles = db_cursor.execute(f"""
            SELECT * FROM RoleInfo WHERE group_id IN (SELECT group_id FROM RoleGroups 
            WHERE guild_id = {message.guild.id})
        """).fetchall()
        for role in roles:
            role_grouped = 'Yes' if role[2] == 1 else 'No'
            message_content += f'{role_no}. Role Id: {role[0]}, Name: {role[1]}, Role Grouped: {role_grouped}\n'
            role_no += 1
        await message.channel.send(message_content)
    except Exception as e:
        await message.channel.send('ERROR: An error occurred while trying to view the registered roles of the guild')
        print(e)


async def view_roles_for_rolegroup(params, message):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    try:
        group_name = params.pop(0)
        message_content = ''
        role_no = 1
        role_group = db_cursor.execute(f"""
            SELECT * FROM RoleGroups WHERE group_name = '{group_name}' AND guild_id = {message.guild.id} 
        """).fetchone()
        if role_group is None:
            await message.channel.send(f'ERROR: Could not found role group: {group_name}')
            db_cursor.close()
            db_conn.close()
            return
        else:
            group_roles = db_cursor.execute(f"""
                SELECT * FROM RoleInfo WHERE group_id = {role_group[0]} 
            """).fetchall()
            if len(group_roles) == 0:
                await message.channel.send('NOTE: No role groups found for this role group')
                db_cursor.close()
                db_conn.close()
                return
            else:
                for role in group_roles:
                    message_content += f'{role_no}. Role Id: {role[0]}, Role Name: {role[1]}\n'
                    role_no += 1
                await message.channel.send(message_content)
    except IndexError as e:
        await message.channel.send('ERROR: Command must be in the form of: viewrolesrg [role group name]')
        db_cursor.close()
        db_conn.close()
        print(e)
    except Exception as e:
        await message.channel.send('ERROR: Unknown error occurred during this operation!')
        db_cursor.close()
        db_conn.close()
        print(e)


def interpret_mod_action(mod_action):
    match mod_action:
        case ModAction.BAN: return 'banned'
        case ModAction.KICK: return 'kicked'
        case ModAction.MUTE: return 'muted'
        case ModAction.WARN: return 'warned'


async def enforce_mod_action_required_roles(params, message):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    try:
        # Mod action can be 'kick', 'ban', 'mute' or 'warn'
        mod_action = params.pop(0)
        # Enforcement period is given in hours
        enforcement_period = params.pop(0)
        if hasattr(ModAction, mod_action.upper()):
            mod_action_enum = ModAction[mod_action.upper()]
            enf_period_num = float(enforcement_period)
            if apputil.get_config_var(CONFIG_VAR_RG_MOD_ACTION, message.guild.id) is None:
                db_cursor.execute(f"""
                    INSERT INTO Configuration (var_name, value, value_type, guild_id) 
                    VALUES('{CONFIG_VAR_RG_MOD_ACTION}', '{mod_action_enum.value}', {DataType.INTEGER.value}, 
                    {message.guild.id})
                """)
            else:
                db_cursor.execute(f"""
                    UPDATE Configuration SET value = {mod_action_enum.value} 
                    WHERE var_name = '{CONFIG_VAR_RG_MOD_ACTION}' AND guild_id = {message.guild.id}
                """)
            if apputil.get_config_var(CONFIG_VAR_RG_ENFORCEMENT_PERIOD, message.guild.id) is None:
                db_cursor.execute(f"""
                    INSERT INTO Configuration (var_name, value, value_type, guild_id) 
                    VALUES('{CONFIG_VAR_RG_ENFORCEMENT_PERIOD}', '{enf_period_num}', {DataType.REAL.value}, 
                    {message.guild.id})
                """)
            else:
                db_cursor.execute(f"""
                    UPDATE Configuration SET value = {enf_period_num} 
                    WHERE var_name = '{CONFIG_VAR_RG_ENFORCEMENT_PERIOD}' AND guild_id = {message.guild.id}
                """)
            if apputil.get_config_var(CONFIG_VAR_RG_ENFORCEMENT_DEADLINE, message.guild.id) is None:
                db_cursor.execute(f"""
                    INSERT INTO Configuration (var_name, value, value_type, guild_id)
                    VALUES('{CONFIG_VAR_RG_ENFORCEMENT_DEADLINE}', 
                    '{datetime.utcnow() + timedelta(hours=enf_period_num)}', {DataType.DATE.value}
                    , {message.guild.id})
                """)
            else:
                db_cursor.execute(f"""
                    UPDATE Configuration SET value = '{datetime.utcnow() + timedelta(hours=enf_period_num)}' 
                    WHERE var_name = '{CONFIG_VAR_RG_ENFORCEMENT_DEADLINE}' AND guild_id = {message.guild.id}
                """)
            try:
                db_conn.commit()
                await message.channel.send(f"""
                    Successfully created/updated enforcement rule for kicking members without required roles.
                    Members who DO NOT have the required roles will be {interpret_mod_action(mod_action_enum)}
                    every {enforcement_period} hours. You can change this at any time by re-running this command
                """)
            except Exception as e:
                await message.channel.send('ERROR: Error occurred while committing changes to database!')
                print(e)
        else:
            await message.channel.send("""
                ERROR: Invalid mod action, mod action must be: 'ban', 'kick', 'mute' or 'warn'
            """)
            db_cursor.close()
            db_conn.close()
            return
    except IndexError as e:
        await message.channel.send("""
            ERROR: Command must be in the form: enforcerg [mod action] [enforcement period (in hours)]
        """)
        db_cursor.close()
        db_conn.close()
        print(e)
    except ValueError as e:
        await message.channel.send('ERROR: Enforcement period MUST be numeric!')
        db_cursor.close()
        db_conn.close()
        print(e)
    except Exception as e:
        await message.channel.send('ERROR: Unknown error occurred during this operation!')
        db_cursor.close()
        db_conn.close()
        print(e)


def search_for_role_by_id(role_id, roles):
    for role in roles:
        if role.id == role_id:
            return role
    return None


async def execute_mod_action(guild_id, mod_action, member):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    try:
        punish_message_config = db_cursor.execute(f"""
            SELECT * FROM Configuration WHERE guild_id = {guild_id} AND var_name = '{CONFIG_VAR_RG_PUNISH_MESSAGE}'
        """).fetchone()
        guild = client.get_guild(guild_id)
        if mod_action != 3:
            await member.send(content=f"""
            You have been {interpret_mod_action(ModAction(mod_action))} from {guild.name}
            Reason: {punish_message_config[2]}
            """)
        match mod_action:
            case 0: await guild.kick(member, reason=f"{punish_message_config[2]}")
            case 1: await guild.ban(member, reason=f"{punish_message_config[2]}")
            case 2: await member.edit(reason=f"{punish_message_config[2]}", mute=True)
            case 3: await warn_member(member, f"{punish_message_config[2]}")
    except Exception as e:
        print(e)
    db_cursor.close()
    db_conn.close()


async def warn_member(member, warn_text):
    await member.send(warn_text)


async def create_embed_message(message_text, message_title, message):
    message_embed = discord.Embed(title=message_title)
    message_embed.description


async def sweep_server(message):
    server = models.Server(message.guild.id, message.guild.name)
    await enact_mod_action(server, message)


async def enact_mod_action(server, message):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    role_groups = db_cursor.execute(f"""
        SELECT * FROM RoleGroups WHERE guild_id = {server.guild_id}
    """).fetchall()
    mod_action = db_cursor.execute(f"""
        SELECT * FROM Configuration WHERE guild_id = {server.guild_id} AND var_name = '{CONFIG_VAR_RG_MOD_ACTION}'
    """).fetchone()
    enforcement_period = db_cursor.execute(f"""
        SELECT value FROM Configuration WHERE guild_id = {server.guild_id} AND 
        var_name = '{CONFIG_VAR_RG_ENFORCEMENT_PERIOD}'
    """).fetchone()
    enforcement_period = float(enforcement_period[0])
    server_entity = client.get_guild(server.guild_id)
    members = server_entity.fetch_members()
    async for member in members:
        if member.id is not server_entity.owner_id and member.id is not client.user.id:
            for group in role_groups:
                roles = db_cursor.execute(f"""
                SELECT * FROM RoleInfo WHERE group_id = {group[0]}""")
                has_role_in_group = False
                for role in roles:
                    discord_role = search_for_role_by_id(role[0], member.roles)
                    if discord_role is not None:
                        has_role_in_group = True
                if not has_role_in_group:
                    if member.joined_at <= datetime.utcnow() - timedelta(hours=enforcement_period):
                        await execute_mod_action(server.guild_id, int(mod_action[2]), member)
    db_cursor.close()
    db_conn.close()


async def set_punish_message(punish_message, message):
    config_msg = ''
    param_len = len(punish_message)
    for count in range(0, param_len):
        config_msg += punish_message[count]
        if count is not param_len - 1:
            config_msg += ' '
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    punish_message_config_var = db_cursor.execute(f"""
        SELECT * FROM Configuration WHERE guild_id = {message.guild.id} AND var_name = '{CONFIG_VAR_RG_PUNISH_MESSAGE}'
    """).fetchone()
    if punish_message_config_var is None:
        db_cursor.execute(f"""
            INSERT INTO Configuration (var_name, value, value_type, guild_id) 
            VALUES ('{CONFIG_VAR_RG_PUNISH_MESSAGE}', '{config_msg}', 2, {message.guild.id})
        """)
    else:
        db_cursor.execute(f"""
            UPDATE Configuration SET value = '{config_msg}' WHERE guild_id = {message.guild.id}
        """)
    try:
        db_conn.commit()
        await message.channel.send(f'Successfully added punish message: {config_msg}')
    except Exception as e:
        await message.channel.send('ERROR: Unable to set new config message!')
        print(e)
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
