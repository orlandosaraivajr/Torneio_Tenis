"""Funções de apoio compartilhadas pelos testes."""
import datetime

from torneios import services
from torneios.models import Inscricao, Jogador, Partida, Torneio


def criar_torneio(formato=Torneio.Formato.ELIMINATORIA, jogadores=0, **campos):
    """Cria um torneio com inscrições abertas e N jogadores (cabeças de chave 1..N)."""
    dados = {
        'nome': 'Open de Primavera',
        'data_torneio': datetime.date(2026, 11, 1),
        'local': 'Clube Central',
        'formato': formato,
        'status': Torneio.Status.INSCRICOES,
    }
    dados.update(campos)
    torneio = Torneio.objects.create(**dados)
    for i in range(jogadores):
        jogador = Jogador.objects.create(nome=f'Jogador {i + 1:02d}')
        Inscricao.objects.create(torneio=torneio, jogador=jogador, cabeca_de_chave=i + 1)
    return torneio


def jogar(partida, vence_1=True, placar=None):
    """Registra uma vitória simples do jogador 1 (ou do 2)."""
    placar = placar or ('6-4 6-3' if vence_1 else '4-6 3-6')
    vencedor = partida.inscricao_1 if vence_1 else partida.inscricao_2
    services.registrar_resultado(partida, Partida.Status.FINALIZADA, placar, vencedor, None)


def jogar_favorito(partida):
    """O jogador com melhor cabeça de chave (menor número) vence."""
    jogar(partida, partida.inscricao_1.cabeca_de_chave < partida.inscricao_2.cabeca_de_chave)


def jogar_rodada(torneio, rodada):
    for partida in torneio.partidas.filter(rodada=rodada).exclude(placar='BYE').order_by('posicao'):
        jogar(Partida.objects.get(pk=partida.pk))
