#!/usr/bin/env sh

APP_ROOT="$(dirname "$(dirname "$0")")"

PID="$1"
while true
do
  if ps -p $PID > /dev/null
  then
    sleep 1
  else
    break
  fi
done
cd "$APP_ROOT" || exit
pipenv run python bot.py
