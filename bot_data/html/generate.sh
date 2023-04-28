#!/usr/bin/env zsh
cd "$(dirname "$0")" || exit 1
pipenv run python generate.py
for file in data/html/**/*.html
do
minify-html --css --js -s "$file" -o "$file"
done
