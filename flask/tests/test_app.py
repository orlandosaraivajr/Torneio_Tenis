import os

from torneio import create_app
from torneio.config import Config


class TestCreateApp:

    def test_caminhos_padrao_na_pasta_instance(self, monkeypatch):
        monkeypatch.setattr(Config, 'SQLALCHEMY_DATABASE_URI', None)
        monkeypatch.setattr(Config, 'UPLOAD_FOLDER', None)
        app = create_app(Config)
        assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///' + os.path.join(app.instance_path, 'torneio.db')
        assert app.config['UPLOAD_FOLDER'] == os.path.join(app.instance_path, 'uploads')

    def test_csrf_ativo_fora_dos_testes(self, monkeypatch):
        monkeypatch.setattr(Config, 'SQLALCHEMY_DATABASE_URI', 'sqlite://')
        app = create_app(Config)
        assert app.config.get('WTF_CSRF_ENABLED', True) is True
        resposta = app.test_client().post('/torneios/1/excluir')
        assert resposta.status_code == 400  # sem token CSRF
