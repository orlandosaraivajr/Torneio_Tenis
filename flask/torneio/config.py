import os


class Config:
    # MVP: chave fixa para desenvolvimento. Em produção, defina SECRET_KEY no ambiente.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-inseguro-troque-em-producao')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')  # padrão: instance/torneio.db
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # uploads de até 10 MB
    UPLOAD_FOLDER = None  # padrão: instance/uploads


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = 'teste'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    WTF_CSRF_ENABLED = False
