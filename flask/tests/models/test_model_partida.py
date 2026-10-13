import pytest

from torneio import services
from torneio.extensions import db
from torneio.models import Formato, Partida, Rodada, StatusPartida, StatusTorneio
from tests.helpers import criar_torneio, jogar, jogar_todas, partidas


@pytest.fixture
def partida(app):
    torneio = criar_torneio(jogadores=2)
    ins_1, ins_2 = torneio.inscritos
    partida = Partida(torneio=torneio, rodada=Rodada.F, inscricao_1=ins_1, inscricao_2=ins_2,
                      placar='6-4 6-7(5) 10-8')
    db.session.add(partida)
    db.session.commit()
    return partida


class TestPartidaModel:

    def test_valores_padrao(self, partida):
        assert partida.status == StatusPartida.AGENDADA
        assert partida.posicao == 0
        assert partida.vencedor is None
        assert partida.data_hora is None
        assert partida.proxima_partida is None

    def test_str(self, partida):
        assert str(partida) == 'Final: Jogador 01 x Jogador 02'

    def test_rotulos(self, partida):
        assert partida.rodada_label == 'Final'
        assert partida.status_label == 'Agendada'

    def test_nomes_dos_jogadores(self, partida):
        assert (partida.nome_1, partida.nome_2) == ('Jogador 01', 'Jogador 02')

    def test_nome_a_definir(self, partida):
        vazia = Partida(torneio=partida.torneio, rodada=Rodada.SF)
        assert (vazia.nome_1, vazia.nome_2) == ('A definir', 'A definir')

    def test_nome_bye(self, partida):
        bye = Partida(torneio=partida.torneio, rodada=Rodada.SF, inscricao_1=partida.inscricao_1, placar='BYE')
        assert bye.nome_2 == 'BYE'
        assert bye.is_bye

    def test_sets_lidos_do_placar(self, partida):
        assert partida.sets == [(6, 4, None), (6, 7, 5), (10, 8, None)]

    def test_sets_de_placar_invalido(self, partida):
        partida.placar = 'placar ruim'
        assert partida.sets == []

    def test_sets_de_bye(self, partida):
        partida.placar = 'BYE'
        assert partida.sets == []

    def test_sets_vencidos(self, partida):
        assert partida.sets_vencidos == (2, 1)

    def test_sets_vencidos_ao_vivo_ignora_set_em_disputa(self, partida):
        partida.status = StatusPartida.EM_ANDAMENTO
        partida.placar = '6-4 3-2'
        assert partida.sets_vencidos == (1, 0)


class TestPartidaEncerrada:

    @pytest.mark.parametrize('status, esperado', [
        (StatusPartida.AGENDADA, False),
        (StatusPartida.EM_ANDAMENTO, False),
        (StatusPartida.FINALIZADA, True),
        (StatusPartida.WO, True),
        (StatusPartida.ABANDONO, True),
    ])
    def test_encerrada(self, status, esperado):
        assert Partida(status=status).encerrada is esperado


class TestPartidaEditavel:

    def test_agendada_editavel(self, app):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        assert partidas(torneio, rodada='SF').first().editavel

    def test_bye_nao_editavel(self, app):
        torneio = criar_torneio(jogadores=3)
        services.gerar_chave(torneio)
        assert not partidas(torneio, placar='BYE').first().editavel

    def test_torneio_cancelado(self, app):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        torneio.status = StatusTorneio.CANCELADO
        db.session.commit()
        assert not partidas(torneio).first().editavel

    def test_editavel_enquanto_proxima_nao_encerrada(self, app):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        semi = partidas(torneio, rodada='SF').first()
        jogar(semi)
        assert semi.editavel

    def test_bloqueada_quando_proxima_encerrada(self, app):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        for semi in partidas(torneio, rodada='SF').all():
            jogar(semi)
        jogar(partidas(torneio, rodada='F').one())
        assert not partidas(torneio, rodada='SF').first().editavel

    def test_grupo_editavel_antes_do_mata_mata(self, app):
        torneio = criar_torneio(Formato.GRUPOS, jogadores=4)
        services.gerar_chave(torneio)
        assert partidas(torneio).first().editavel

    def test_grupo_bloqueado_depois_do_mata_mata(self, app):
        torneio = criar_torneio(Formato.GRUPOS, jogadores=4)
        services.gerar_chave(torneio)
        jogar_todas(torneio)
        services.gerar_mata_mata_dos_grupos(torneio)
        assert not partidas(torneio, rodada='GR').first().editavel
