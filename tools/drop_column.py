#!/usr/bin/env python3

import os
import re
import sqlite3


def drop_column(table_name: str, column_name: str):
    columns = []
    creation_command = f"CREATE TABLE IF NOT EXISTS _{table_name}("
    db_name = os.path.abspath(os.path.join(__file__, "..", "..", "bot_data", "database.db"))
    with sqlite3.connect(db_name) as conn:
        cursor = conn.execute(f"""PRAGMA table_info({table_name})""")
        data = cursor.fetchall()
        cursor = conn.execute("""SELECT SQL FROM sqlite_master WHERE tbl_name==? COLLATE NOCASE""", [table_name])
        formation_statement, = cursor.fetchone()
        autoincrement_columns = [match.group(1).lower() for match in
                                 re.finditer(r"([\S]+) ([^,)]+) AUTOINCREMENT", formation_statement, flags=re.IGNORECASE)]
        for num, col_name, col_type, is_not_null, default_value, is_primary_key in data:
            if col_name.lower() != column_name.lower():
                columns.append(col_name)
                col_creation_str = f"{col_name} {col_type} "
                if is_primary_key:
                    col_creation_str += "PRIMARY KEY "
                if is_not_null:
                    col_creation_str += "NOT NULL "
                if default_value is not None:
                    col_creation_str += "DEFAULT " + str(default_value) + " "
                if col_name.lower() in autoincrement_columns:
                    col_creation_str += "AUTOINCREMENT "
                col_creation_str += ","
                creation_command += col_creation_str
            else:
                continue
        creation_command = creation_command.rstrip(",") + ")"
        conn.execute(creation_command)
        col_str = ", ".join(columns)
        print("Created backup table...")
        cursor = conn.execute(f"""INSERT INTO _{table_name}({col_str}) SELECT {col_str} FROM {table_name}""")
        cursor.fetchall()
        print("Inserted data...")
        conn.execute(f"""DROP TABLE {table_name}""")
        print("Dropped table...")
        conn.execute(f"""ALTER TABLE _{table_name} RENAME TO {table_name}""")
        print("Renamed table...")
        print("Complete. Exiting.")
        return
