import os
import uuid

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


def salvar_upload(arquivo, pasta):
    """Grava o arquivo enviado em UPLOAD_FOLDER/pasta e devolve o caminho relativo (ou None)."""
    if not isinstance(arquivo, FileStorage) or not arquivo.filename:
        return None
    nome = f'{uuid.uuid4().hex[:8]}_{secure_filename(arquivo.filename)}'
    destino = os.path.join(current_app.config['UPLOAD_FOLDER'], pasta)
    os.makedirs(destino, exist_ok=True)
    arquivo.save(os.path.join(destino, nome))
    return f'{pasta}/{nome}'
