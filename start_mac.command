#!/bin/bash
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "先に setup_mac.command を実行してください。"
  read -p "Enterで終了"
  exit 1
fi
source .venv/bin/activate
python app.py
