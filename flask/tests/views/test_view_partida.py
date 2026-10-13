from http import HTTPStatus

import pytest

from torneio import services
from torneio.extensions import db
from torneio.models import Partida, StatusPartida, StatusTorneio, Torneio
from tests.helpers import criar_torneio, jogar, partidas


@pytest.fixture
def torneio(app):
    torneio = criar_torneio(jogadores=4)
    services.gerar_chave(torneio)
    return torneio


@pytest.fixture
def semi(torneio):
    return partidas(torneio, rodada='SF').first()


def post(client, partida, **kwargs):
    dados = dict(status='FINALIZADA', placar='6-4 6-3', vencedor='None', data_hora='', voltar='chave')
    dados.update(kwargs)
    return client.post(f'/partidas/{partida.id}/', data=dados)


class TestPartidaResultadoGet:

    def test_status_code(self, client, semi):
        assert client.get(f'/partidas/{semi.id}/').status_code == HTTPStatus.OK

    def test_exibe_confronto_e_formulario(self, client, semi):
        pagina = client.get(f'/partidas/{semi.id}/').get_data(as_text=True)
        assert semi.nome_1 in pagina and semi.nome_2 in pagina
        assert 'name="placar"' in pagina

    def test_voltar_para_partidas(self, client, semi, torneio):
        pagina = client.get(f'/partidas/{semi.id}/?voltar=partidas').get_data(as_text=True)
        assert f'/torneios/{torneio.id}/?aba=partidas' in pagina

    def test_voltar_invalido_usa_chave(self, client, semi, torneio):
        pagina = client.get(f'/partidas/{semi.id}/?voltar=https://evil.com').get_data(as_text=True)
        assert 'evil.com' not in pagina
        assert f'/torneios/{torneio.id}/?aba=chave' in pagina

    def test_partida_inexistente(self, client):
        assert client.get('/partidas/9999/').status_code == HTTPStatus.NOT_FOUND


class TestPartidaResultadoPost:

    def test_redireciona_para_chave(self, client, semi, torneio):
        resposta = post(client, semi)
        assert resposta.location.endswith(f'/torneios/{torneio.id}/?aba=chave')

    def test_salva_resultado(self, client, semi):
        post(client, semi)
        partida = db.session.get(Partida, semi.id)
        assert partida.status == StatusPartida.FINALIZADA
        assert partida.placar == '6-4 6-3'
        assert partida.vencedor == partida.inscricao_1

    def test_vencedor_avanca(self, client, semi, torneio):
        post(client, semi)
        assert partidas(torneio, rodada='F').one().inscricao_1 == semi.inscricao_1

    def test_volta_para_aba_partidas(self, client, semi):
        assert post(client, semi, voltar='partidas').location.endswith('aba=partidas')

    def test_post_invalido_reexibe_formulario(self, client, semi):
        resposta = post(client, semi, placar='seis a quatro')
        assert resposta.status_code == HTTPStatus.OK
        assert 'Set inválido' in resposta.get_data(as_text=True)
        assert db.session.get(Partida, semi.id).status == StatusPartida.AGENDADA

    def test_agendar_horario(self, client, semi):
        post(client, semi, status='AGENDADA', placar='', data_hora='2026-11-01T14:30')
        partida = db.session.get(Partida, semi.id)
        assert partida.data_hora is not None
        assert partida.vencedor is None

    def test_finalizar_torneio(self, client, torneio):
        for semi in partidas(torneio, rodada='SF').all():
            jogar(semi)
        post(client, partidas(torneio, rodada='F').one(), placar='3-6 4-6')
        assert db.session.get(Torneio, torneio.id).status == StatusTorneio.FINALIZADO


class TestPartidaBloqueada:

    def test_redireciona_com_mensagem(self, client, torneio):
        for semi in partidas(torneio, rodada='SF').all():
            jogar(semi)
        jogar(partidas(torneio, rodada='F').one())
        semi = partidas(torneio, rodada='SF').first()
        resposta = client.get(f'/partidas/{semi.id}/', follow_redirects=True)
        assert 'Esta partida não pode mais ser alterada' in resposta.get_data(as_text=True)

    def test_post_nao_altera(self, client, torneio):
        for semi in partidas(torneio, rodada='SF').all():
            jogar(semi)
        jogar(partidas(torneio, rodada='F').one())
        semi = partidas(torneio, rodada='SF').first()
        post(client, semi, placar='0-6 0-6')
        assert db.session.get(Partida, semi.id).placar == '6-4 6-3'

    def test_bye_bloqueado(self, app, client):
        torneio = criar_torneio(nome='Com bye', jogadores=3)
        services.gerar_chave(torneio)
        bye = partidas(torneio, placar='BYE').one()
        assert client.get(f'/partidas/{bye.id}/').status_code == HTTPStatus.FOUND
