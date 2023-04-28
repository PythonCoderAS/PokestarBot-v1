#!/usr/bin/env bash
my_app_path="$(dirname $(readlink -f "$0"))";
cd $my_app_path;
pipenv run zsh -c "python bot.py |& ts '[%Y-%m-%d %H:%M:%S]' >> logs/log.log"
