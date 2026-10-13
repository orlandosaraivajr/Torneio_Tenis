"""Funções de apoio compartilhadas pelos testes."""
import datetime

from torneio import services
from torneio.extensions import db
from torneio.models import Formato, Inscricao, Jogador, Partida, StatusPartida, StatusTorneio, Torneio


def criar_torneio(formato=Formato.ELIMINATORIA, jogadores=0, **campos):
    """Cria um torneio com inscrições abertas e N jogadores (cabeças de chave 1..N)."""
    dados = {
        'nome': 'Open de Primavera',
        'data_torneio': datetime.date(2026, 11, 1),
        'local': 'Clube Central',
        'formato': formato,
        'status': StatusTorneio.INSCRICOES,
    }
    dados.update(campos)
    torneio = Torneio(**dados)
    db.session.add(torneio)
    for i in range(jogadores):
        jogador = Jogador(nome=f'Jogador {i + 1:02d}')
        torneio.inscricoes.append(Inscricao(jogador=jogador, cabeca_de_chave=i + 1))
    db.session.commit()
    return torneio


def criar_jogador(nome='Gustavo Kuerten'):
    jogador = Jogador(nome=nome)
    db.session.add(jogador)
    db.session.commit()
    return jogador


def partidas(torneio, **filtros):
    return Partida.query.filter_by(torneio_id=torneio.id, **filtros).order_by(Partida.posicao)


def jogar(partida, vence_1=True, placar=None):
    """Registra uma vitória simples do jogador 1 (ou do 2)."""
    placar = placar or ('6-4 6-3' if vence_1 else '4-6 3-6')
    vencedor = partida.inscricao_1 if vence_1 else partida.inscricao_2
    services.registrar_resultado(partida, StatusPartida.FINALIZADA, placar, vencedor, None)


def jogar_favorito(partida):
    """O jogador com melhor cabeça de chave (menor número) vence."""
    jogar(partida, partida.inscricao_1.cabeca_de_chave < partida.inscricao_2.cabeca_de_chave)


def jogar_todas(torneio, **filtros):
    for partida in partidas(torneio, **filtros).all():
        jogar_favorito(partida)


def jogar_rodada(torneio, rodada):
    for partida in partidas(torneio, rodada=rodada).filter(Partida.placar != 'BYE').all():
        jogar(partida)
