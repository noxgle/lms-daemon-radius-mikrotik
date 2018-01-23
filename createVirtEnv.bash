#!/bin/bash
# 
# Script start in project folder.
DIR=`pwd`

if ! [ -x "$(command -v pip)" ]; then
  echo 'Error: pip is not installed.' >&2
  exit 1
fi

if ! [ -x "$(command -v virtualenv)" ]; then
  echo 'Error: virtualenv is not installed.' >&2
  exit 1
fi

virtualenv --no-site-packages venv

source $DIR/venv/bin/activate
pip install pip --upgrade
pip install -r requirements.txt
deactivate
