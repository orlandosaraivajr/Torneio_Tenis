import os

from flask import Flask

from .config import Config
from .extensions import csrf, db, migrate


def create_app(config=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config)
    os.makedirs(app.instance_path, exist_ok=True)
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'torneio.db')
    if not app.config.get('UPLOAD_FOLDER'):
        app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, 'uploads')

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from .views import jogadores, main, partidas, torneios
    app.register_blueprint(main.bp)
    app.register_blueprint(torneios.bp)
    app.register_blueprint(jogadores.bp)
    app.register_blueprint(partidas.bp)

    from . import admin, cli, filtros
    admin.init_app(app)
    cli.init_app(app)
    filtros.init_app(app)
    return app
