#!/bin/bash
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11 or 3.12をインストールしてください: https://www.python.org/downloads/"
  read -p "Enterで終了"
  exit 1
fi
PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$PYVER" != "3.11" && "$PYVER" != "3.12" && "$PYVER" != "3.13" ]]; then
  echo "Python 3.11〜3.13が必要です。現在: $PYVER"
  read -p "Enterで終了"
  exit 1
fi
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || exit 1
echo "セットアップ完了。次回から start_mac.command を実行してください。"
read -p "Enterで終了"
