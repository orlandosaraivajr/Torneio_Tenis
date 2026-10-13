from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
csrf = CSRFProtect()


@event.listens_for(Engine, 'connect')
def _ativar_chaves_estrangeiras(conexao, _registro):
    """O SQLite só respeita FOREIGN KEY / ON DELETE com este pragma ligado."""
    if conexao.__class__.__module__.startswith('sqlite3'):
        cursor = conexao.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()
