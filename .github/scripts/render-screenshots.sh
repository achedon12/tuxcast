#!/bin/sh
# Re-renders the terminal screenshots of the README and the website from real output.
# usage: .github/scripts/render-screenshots.sh   (from the repository, with `make install` done)
set -eu
python=.venv/bin/python
render=.github/scripts/render-terminal.py
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

RENDER_PROMPT="tuxcast doctor" \
    $python $render docs/assets/terminal-doctor-full.svg "tuxcast doctor" -- .venv/bin/tuxcast doctor
RENDER_PROMPT="tuxcast doctor --only streamdeck,discord,spotify,network" \
    $python $render .github/assets/terminal-doctor.svg "tuxcast doctor" -- \
    .venv/bin/tuxcast doctor --only streamdeck,discord,spotify,network
cp .github/assets/terminal-doctor.svg docs/assets/terminal-doctor.svg

$python .github/scripts/demo-profile.py "$work/Streaming.streamDeckProfile"
RENDER_PROMPT="tuxcast convert Streaming.streamDeckProfile" \
    $python $render docs/assets/terminal-convert.svg "tuxcast convert" -- \
    .venv/bin/tuxcast convert "$work/Streaming.streamDeckProfile" \
    --pages-dir "$work/pages" --assets-dir "$work/assets" --layout fr
sed -i "s#$work/pages#~/.var/app/com.core447.StreamController/data/pages#g" docs/assets/terminal-convert.svg
cp docs/assets/terminal-convert.svg .github/assets/terminal-convert.svg
