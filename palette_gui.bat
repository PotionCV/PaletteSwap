@echo off
rem Palette Swap launcher - double-click to open the GUI window
rem Drop a png/jpg/gif onto this .bat to open it straight away
cd /d "%~dp0"
python "palette_swap.py" --gui %*
if errorlevel 1 py -3 "palette_swap.py" --gui %*
if errorlevel 1 pause
