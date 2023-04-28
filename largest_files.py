#!/usr/bin/env python3

import os

search_path = os.path.dirname(__file__)


def get_data():
    for curdir, folders, files in os.walk(search_path, topdown=True, followlinks=True):
        for file in files:
            if file.endswith(".py"):
                fpath = os.path.join(curdir, file)
                with open(fpath, "rb") as fp:
                    f_bytes = fp.read()
                num_lines = f_bytes.splitlines(False)
                num_words = [item for item in f_bytes.replace(b"\n", b" ").split(b" ") if item]
                yield fpath, len(f_bytes), len(num_lines), len(num_words)


def main():
    for filename, len_bytes, len_lines, len_words in sorted(get_data(), key=lambda obj: obj[2], reverse=True):
        filename = filename.replace(search_path + "/", "")
        print(f"{filename}: {len_lines} lines • {len_words} words • {len_bytes} bytes")


if __name__ == '__main__':
    main()
