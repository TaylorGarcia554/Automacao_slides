"""Configurações do usuário, salvas em JSON entre uma execução e outra.

No Windows o arquivo fica em %APPDATA%\\AutomacaoSlides\\config.json.
Para incluir uma nova opção basta adicionar um campo em `Settings`
(com valor padrão): arquivos antigos continuam carregando normalmente.
"""

import json
import os
from dataclasses import asdict, dataclass, fields

CONFIG_DIR_NAME = "AutomacaoSlides"


def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    path = os.path.join(base, CONFIG_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


def log_path() -> str:
    return os.path.join(config_dir(), "automacao_slides.log")


@dataclass
class Settings:
    source_folder: str = ""
    image_path: str = ""
    output_folder: str = ""
    include_subfolders: bool = False
    replace_previous_background: bool = True
    open_output_when_done: bool = False
    window_geometry: str = ""

    @classmethod
    def load(cls) -> "Settings":
        try:
            with open(config_path(), encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> None:
        path = config_path()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
