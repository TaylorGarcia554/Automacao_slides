# Automação Slides

Aplicativo desktop (Tkinter) que aplica uma imagem de fundo em todos os slides de todos os arquivos `.pptx` de uma pasta e salva as cópias numa pasta de saída. Os arquivos originais nunca são alterados.

## Funcionalidades

- **Pasta dos slides, imagem e pasta de saída escolhidas na própria tela.** Ficam salvas para a próxima vez em `%APPDATA%\AutomacaoSlides\config.json`.
- Contador de arquivos `.pptx` encontrados assim que a pasta é escolhida.
- Opção de **incluir subpastas**. A estrutura de pastas é mantida na saída.
- **Substituir fundo anterior:** rodar de novo sobre um arquivo já processado troca a imagem em vez de empilhar outra.
- Barra de progresso, registro colorido (✓/✗), botão **Cancelar** e janela que não trava durante o processamento.
- Aviso antes de sobrescrever arquivos já existentes na pasta de saída. Bloqueia saída igual à origem.
- Um arquivo com erro (corrompido, aberto no PowerPoint) não interrompe o lote. Mostra um resumo no final.
- Log detalhado em `%APPDATA%\AutomacaoSlides\automacao_slides.log`.
- Layout responsivo: campos, progresso e registro crescem com a janela. O tamanho da janela é lembrado.
- Aceita PNG, JPG, BMP, GIF e TIFF.

## Estrutura

```
automacao_slides.py   # ponto de entrada
app/
  processor.py        # lógica de processamento (sem interface; reutilizável)
  config.py           # configurações persistentes
  ui.py               # janela Tkinter
build_exe.bat         # gera o .exe com PyInstaller
```

Para incluir novas operações nos slides, crie uma função ao lado de `apply_background` em `app/processor.py`. Para uma nova opção salva, adicione um campo em `Settings` (`app/config.py`).

## Rodar

```bash
pip install -r requirements.txt
python automacao_slides.py
```

## Gerar o .exe (Windows)

Execute `build_exe.bat`. O executável é gerado em `dist\Automacao_Slides.exe`.
