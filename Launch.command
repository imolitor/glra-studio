#!/bin/zsh
set -eu
cd "$(dirname "$0")"
if [[ -x ../venv/bin/python ]]; then
  task_python=../venv/bin/python
else
  if [[ ! -x .venv/bin/python ]]; then
    if ! command -v python3.13 >/dev/null 2>&1; then
      print 'Python 3.13 is required. See README.md for installation.'
      read '?Press Return to close.'
      exit 1
    fi
    python3.13 -m venv .venv
  fi
  task_python=.venv/bin/python
fi
if ! "$task_python" -c 'import PySide6, hid' >/dev/null 2>&1; then
  "$task_python" -m pip install -r requirements.txt
fi
exec "$task_python" -m macropad.gui "$@"
