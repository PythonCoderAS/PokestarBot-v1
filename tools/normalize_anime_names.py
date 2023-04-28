#!/usr/bin/env pipenv run python

import os
import sqlite3


def main():
    db_name = os.path.abspath(os.path.join(__file__, "..", "..", "bot_data", "database.db"))
    with sqlite3.connect(db_name) as conn:
        data = [anime for anime, in conn.execute("""SELECT DISTINCT ANIME FROM WAIFUS""").fetchall()]
    processed = []
    for item in data.copy():
        l = item.lower()
        if l in processed:
            data.remove(item)
        else:
            processed.append(l)
    for item in data:
        conn.execute("""UPDATE WAIFUS SET ANIME=? WHERE ANIME==? COLLATE NOCASE""", [item, item])
    print("Data normalized!")


if __name__ == '__main__':
    main()
