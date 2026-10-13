"""Filtros e variáveis globais dos templates Jinja."""
from .models import StatusTorneio, Torneio


def data_br(valor):
    return valor.strftime('%d/%m/%Y') if valor else ''


def data_hora_br(valor, formato='%d/%m/%Y %H:%M'):
    return valor.strftime(formato) if valor else ''


def init_app(app):
    app.add_template_filter(data_br, 'data')
    app.add_template_filter(data_hora_br, 'datahora')

    @app.context_processor
    def menu_lateral():
        def torneios_menu():
            return Torneio.query.filter(Torneio.status != StatusTorneio.CANCELADO).order_by(
                Torneio.data_torneio.desc(), Torneio.nome
            ).limit(12).all()
        return {'torneios_menu': torneios_menu}
