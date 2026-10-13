"""Painel administrativo em /admin (equivalente ao Django Admin)."""
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_wtf import FlaskForm

from .extensions import db
from .models import Inscricao, Jogador, Partida, Torneio, Usuario


class BaseView(ModelView):
    form_base_class = FlaskForm  # usa o mesmo CSRF do restante da aplicação
    page_size = 50


class TorneioView(BaseView):
    column_list = ['nome', 'data_torneio', 'local', 'formato', 'status', 'organizador']
    column_searchable_list = ['nome', 'local']
    column_filters = ['status', 'formato']
    form_excluded_columns = ['inscricoes', 'partidas', 'criado_em']


class JogadorView(BaseView):
    column_searchable_list = ['nome']
    form_excluded_columns = ['inscricoes']


class PartidaView(BaseView):
    column_list = ['torneio', 'rodada', 'grupo', 'posicao', 'inscricao_1', 'inscricao_2', 'placar', 'status']
    column_filters = ['rodada', 'status']


def init_app(app):
    admin = Admin(app, name='Torneio · Admin')
    admin.add_view(TorneioView(Torneio, db, name='Torneios'))
    admin.add_view(JogadorView(Jogador, db, name='Jogadores'))
    admin.add_view(BaseView(Inscricao, db, name='Inscrições'))
    admin.add_view(PartidaView(Partida, db, name='Partidas'))
    admin.add_view(BaseView(Usuario, db, name='Organizadores'))
