#!/usr/bin/env bash
pip install -r requirements.txt
python datenbank_setup.py
python update_db.py