#!/usr/bin/env bash

cd ..
rsync -avz  --exclude "*.lock" --exclude ".git" --exclude ".idea"  --update PokestarBot/ "PokestarFan@40.71.90.1:PokestarBot"
