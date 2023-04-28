#!/usr/bin/env python3

import os

version_file = os.path.abspath(os.path.join(__file__, "..", "..", "bot_data", "version.py"))
with open(version_file, "r") as file:
    exec(file.read())
os.system(f'git tag -a v{__version__} -m "Version {__version__}"')
