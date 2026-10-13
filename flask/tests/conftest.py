import pytest
from flask import template_rendered

from torneio import create_app
from torneio.config import TestConfig
from torneio.extensions import db


@pytest.fixture
def app(tmp_path):
    class Config(TestConfig):
        UPLOAD_FOLDER = str(tmp_path / 'uploads')

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def templates(app):
    """Lista de (template, contexto) renderizados — equivalente ao response.context do Django."""
    renderizados = []

    def registrar(_app, template, context, **_extra):
        renderizados.append((template, context))

    template_rendered.connect(registrar, app)
    yield renderizados
    template_rendered.disconnect(registrar, app)
