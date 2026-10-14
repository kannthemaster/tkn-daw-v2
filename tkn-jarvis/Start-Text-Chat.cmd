@echo off
py -3 -B "%~dp0text_chat.py" %*
if errorlevel 1 pause
