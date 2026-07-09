@echo off
echo Building ScreenMirror...
pip install -r requirements.txt
pyinstaller --onefile --icon=NONE --name=ScreenMirror screenmirror.py
echo Build complete! Check the dist/ folder for ScreenMirror.exe
pause
