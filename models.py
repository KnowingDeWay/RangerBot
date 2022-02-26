from enum import Enum


class Server:
    def __init__(self, guild_id, guild_name):
        self.guild_id = guild_id
        self.guild_name = guild_name


class RoleGroup:
    def __init__(self, group_id, group_name, group_required, guild_id):
        self.group_id = group_id
        self.group_name = group_name
        self.group_required = group_required
        self.guild_id = guild_id


class RoleInfo:
    def __init__(self, role_id, role_name, role_grouped, group_id):
        self.role_id = role_id
        self.role_name = role_name
        self.role_grouped = role_grouped
        self.group_id = group_id


class DataType(Enum):
    INTEGER = 0
    REAL = 1
    TEXT = 2
    BOOLEAN = 3
    DATE = 4


class ModAction(Enum):
    KICK = 0
    BAN = 1
    MUTE = 2
    WARN = 3

