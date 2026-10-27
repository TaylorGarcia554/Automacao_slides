@echo off
REM Gera o executavel em dist\Automacao_Slides.exe
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name "Automacao_Slides" --collect-data pptx automacao_slides.py
pause
