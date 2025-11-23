#!/bin/bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "Environment ready. Run with:"
echo "source .venv/bin/activate && python stream_tone.py"