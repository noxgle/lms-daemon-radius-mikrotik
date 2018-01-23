#!/bin/bash
# 
# Script start in project folder.
DIR=`pwd`

#pigar -P $DIR
virtualenv --no-site-packages venv

source $DIR/venv/bin/activate
pip install pip --upgrade
pip install -r requirements.txt
deactivate
