#!/bin/bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install soundfile
echo "Installed dependencies from requirements.txt (FLAC support enabled)"
echo "Environment ready. Run with:"
echo "source .venv/bin/activate && python stream_tone.py --freq 528 --iso --pulse 40"
echo "Example save: python stream_tone.py --freq 528 --iso --pulse 40 --save-audio"