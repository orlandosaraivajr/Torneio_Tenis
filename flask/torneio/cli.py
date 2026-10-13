"""Comandos de terminal: `flask --app app <comando>`."""
import datetime
import random

import click

from . import services
from .extensions import db
from .models import Formato, Inscricao, Jogador, Partida, Rodada, StatusPartida, StatusTorneio, Torneio, Usuario

NOMES = [
    'Gustavo Kuerten', 'Fernando Meligeni', 'Thomaz Bellucci', 'João Fonseca', 'Bia Haddad Maia',
    'Marcelo Melo', 'Bruno Soares', 'Thiago Monteiro', 'Luisa Stefani', 'Rafael Matos',
    'Felipe Meligeni', 'Thiago Wild', 'Laura Pigossi', 'Carolina Alves', 'Orlando Silva', 'Ana Souza',
]
PLACARES = ['6-4 6-3', '7-6(4) 6-2', '4-6 6-3 10-7', '3-6 4-6', '6-7(5) 6-4 8-10', '2-6 6-7(3)']


def _torneio(nome, formato, jogadores):
    torneio = Torneio(
        nome=nome, formato=formato, status=StatusTorneio.INSCRICOES,
        data_torneio=datetime.date.today() + datetime.timedelta(days=random.randint(1, 60)),
        local='Clube de Tênis Central', premiacao='Troféu + R$ 1.000 ao campeão',
        descricao=f'Torneio de demonstração no formato {Formato.label(formato).lower()}.',
        regulamento='Partidas em melhor de 3 sets com super tiebreak no terceiro.',
    )
    for i, jogador in enumerate(jogadores):
        torneio.inscricoes.append(Inscricao(jogador=jogador, cabeca_de_chave=i + 1 if i < 4 else None))
    db.session.add(torneio)
    db.session.commit()
    return torneio


def _jogar(torneio, rodadas, limite=None):
    pendentes = Partida.query.filter(
        Partida.torneio_id == torneio.id, Partida.rodada.in_(rodadas), Partida.status == StatusPartida.AGENDADA,
    ).order_by(Partida.posicao).all()
    for partida in pendentes[:limite]:
        placar = random.choice(PLACARES)
        vencedor = services.vencedor_pelo_placar(partida, placar)
        services.registrar_resultado(partida, StatusPartida.FINALIZADA, placar, vencedor, None)


def popular_demo():
    random.seed(42)
    jogadores = []
    for nome in NOMES:
        jogador = Jogador.query.filter_by(nome=nome).first() or Jogador(nome=nome)
        db.session.add(jogador)
        jogadores.append(jogador)
    db.session.commit()

    elim = _torneio('Open de Primavera', Formato.ELIMINATORIA, jogadores[:13])
    services.gerar_chave(elim)
    _jogar(elim, [Rodada.R16])
    _jogar(elim, [Rodada.QF], limite=2)
    semi = Partida.query.filter_by(torneio_id=elim.id, rodada=Rodada.QF, status=StatusPartida.AGENDADA).first()
    services.registrar_resultado(semi, StatusPartida.EM_ANDAMENTO, '6-4 3-2', None, None)

    grupos = _torneio('Copa dos Clubes', Formato.GRUPOS, jogadores[:8])
    services.gerar_chave(grupos)
    _jogar(grupos, [Rodada.GRUPOS])
    services.gerar_mata_mata_dos_grupos(grupos)

    rr = _torneio('Desafio Round-robin', Formato.ROUND_ROBIN, jogadores[8:13])
    services.gerar_chave(rr)
    _jogar(rr, [Rodada.TODOS], limite=6)


def init_app(app):
    @app.cli.command('popular-demo')
    def popular_demo_comando():
        """Cria torneios de exemplo (eliminatória, grupos + mata-mata e round-robin)."""
        popular_demo()
        click.echo('Dados de demonstração criados.')

    @app.cli.command('criar-organizador')
    @click.argument('nome')
    def criar_organizador(nome):
        """Cadastra um organizador para ser escolhido nos torneios."""
        db.session.add(Usuario(nome=nome))
        db.session.commit()
        click.echo(f'Organizador "{nome}" criado.')
