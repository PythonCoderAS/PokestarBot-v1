#!/usr/bin/env pipenv run python

import os
import pprint
import sqlite3
import time
import traceback
import tqdm


def main():
    try:
        db_name = os.path.abspath(os.path.join(__file__, "..", "..", "bot_data", "database.db"))
        with sqlite3.connect(db_name) as conn, tqdm.tqdm(total=6, desc="Porting data...", leave=None) as progress_bar:
            progress_bar.set_description("Setting Foreign Keys PRAGMA to on")
            conn.execute("""PRAGMA foreign_keys = ON""")
            progress_bar.set_description("Retrieving vote data...")
            progress_bar.update()
            vote_data = conn.execute("""SELECT USER_ID, BRACKET, DIVISION, CHOICE FROM VOTES""").fetchall()
            progress_bar.set_description("Dropping vote table...")
            progress_bar.update()
            conn.execute("""DROP TABLE VOTES""")
            progress_bar.set_description("Creating new tables...")
            progress_bar.update()
            conn.execute("""CREATE TABLE IF NOT EXISTS BRACKET_DATA(ID INTEGER PRIMARY KEY, RANK INTEGER NOT NULL,
                        BRACKET_ID INTEGER NOT NULL REFERENCES BRACKETS(ID) ON UPDATE CASCADE ON DELETE CASCADE,
                        GID INTEGER NOT NULL REFERENCES WAIFUS(ID) ON UPDATE CASCADE ON DELETE CASCADE, UNIQUE (BRACKET_ID, GID))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS VOTES(ID INTEGER PRIMARY KEY, USER_ID BIGINT NOT NULL,
                        BRACKET_ID INTEGER NOT NULL REFERENCES BRACKETS(ID) ON UPDATE CASCADE ON DELETE CASCADE,
                        GID INTEGER REFERENCES WAIFUS(ID) ON UPDATE CASCADE ON DELETE CASCADE, UNIQUE (USER_ID, BRACKET_ID, GID))""")
            brackets = [bracket_id for bracket_id, in conn.execute("""SELECT ID FROM BRACKETS""").fetchall()]
            conn.execute("""UPDATE BRACKETS SET STATUS=8 WHERE STATUS==4""")
            conn.execute("""UPDATE BRACKETS SET STATUS=4 WHERE STATUS==3""")
            progress_bar.set_description("Modifying bracket data...")
            progress_bar.update()
            for bracket in tqdm.tqdm(brackets, desc="Working on brackets...", leave=None):
                conn.execute(
                    f"""INSERT INTO BRACKET_DATA(BRACKET_ID, RANK, GID) SELECT {bracket}, BRACKET_{bracket}.ID, W.ID FROM BRACKET_{bracket} INNER 
                    JOIN WAIFUS W on BRACKET_{bracket}.NAME = W.NAME""").fetchall()
                conn.execute(f"""DROP TABLE BRACKET_{bracket}""")
            progress_bar.set_description("Porting vote data...")
            progress_bar.update()
            for user_id, bracket_id, divison, choice in tqdm.tqdm(vote_data, desc="Moving vote entries...", leave=None):
                if bracket_id not in brackets:
                    continue
                rank = divison * 2 - int(choice)
                gid, = conn.execute("""SELECT GID FROM BRACKET_DATA WHERE RANK==? AND BRACKET_ID==? LIMIT 1""", [rank, bracket_id]).fetchone()
                conn.execute("""INSERT INTO VOTES(USER_ID, BRACKET_ID, GID) VALUES (?, ?, ?)""", [user_id, bracket_id, gid])
            progress_bar.set_description("Complete!")
            progress_bar.update()
    except Exception:
        tqdm.tqdm.write("Exception occurred!")
        time.sleep(2)
        print("\n" * 5)
        traceback.print_exc()
        print("\n" * 5)
        pprint.pprint(locals())
        return


if __name__ == '__main__':
    main()
