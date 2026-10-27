# Automação Slides

Aplicativo desktop (Tkinter) que aplica uma imagem de fundo em todos os slides de todos os arquivos `.pptx` de uma pasta e salva as cópias numa pasta de saída.

- Pasta de origem (fixa no código): `M:\SLIDES_2024`
- Imagem de fundo e pasta de saída: escolhidas na interface

> Código recuperado a partir do executável `Automação_Slides.exe` (PyInstaller, Python 3.12).

## Rodar

```bash
pip install -r requirements.txt
python automacao_slides.py
```

## Gerar o .exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "Automação_Slides" automacao_slides.py
```
