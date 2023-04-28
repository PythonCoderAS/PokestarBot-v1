#!/usr/bin/env bash

cd ..

rsync -avz --exclude ".git" --exclude ".idea" --exclude "*.lock" --update "PokestarFan@40.71.90.1:PokestarBot" ./
