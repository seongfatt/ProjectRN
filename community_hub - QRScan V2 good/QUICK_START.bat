@echo off
title Community Hub - Quick Start
call venv\Scripts\activate.bat
streamlit run app.py --server.headless true
call venv\Scripts\deactivate.bat
