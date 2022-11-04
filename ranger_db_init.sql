BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "Servers" (
	"guild_id"	INTEGER NOT NULL UNIQUE,
	"guild_name"	TEXT,
	PRIMARY KEY("guild_id")
);
CREATE TABLE IF NOT EXISTS "RoleInfo" (
	"role_id"	INTEGER NOT NULL UNIQUE,
	"role_name"	TEXT,
	"role_grouped"	INTEGER,
	"group_id"	INTEGER,
	FOREIGN KEY("group_id") REFERENCES "RoleGroups"("group_id") ON DELETE CASCADE,
	PRIMARY KEY("role_id")
);
CREATE TABLE IF NOT EXISTS "Configuration" (
	"var_id"	INTEGER NOT NULL UNIQUE,
	"var_name"	TEXT,
	"value"	TEXT,
	"value_type"	INTEGER,
	"guild_id"	INTEGER,
	FOREIGN KEY("guild_id") REFERENCES "Servers"("guild_id") ON DELETE CASCADE,
	PRIMARY KEY("var_id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "RoleGroups" (
	"group_id"	INTEGER NOT NULL UNIQUE,
	"group_name"	TEXT,
	"group_required"	INTEGER,
	"guild_id"	INTEGER,
	FOREIGN KEY("guild_id") REFERENCES "Servers"("guild_id") ON UPDATE CASCADE,
	PRIMARY KEY("group_id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "HelpCommands" (
	"command_id" INTEGER NOT NULL UNIQUE,
	"command" TEXT,
	"command_desc" TEXT,
	"command_type" INTEGER,
	PRIMARY KEY("command_id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "PunishmentReports"(
	"report_id" INT NOT NULL UNIQUE,
	"guild_id" INT,
	"date_produced" datetime,
	"punishment_type" INTEGER,
	FOREIGN KEY("guild_id") REFERENCES "Servers"("guild_id") ON DELETE CASCADE
	PRIMARY KEY("report_id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS PunishmentReportEntries(
	"user_id" INT NOT NULL UNIQUE,
	"report_id" INT,
	"user_name" TEXT,
	FOREIGN KEY("report_id") REFERENCES "PunishmentReports"("report_id") ON DELETE CASCADE
	PRIMARY KEY("user_id")
);
COMMIT;
