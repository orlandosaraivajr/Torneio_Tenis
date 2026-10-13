import datetime

import pytest

from torneio.extensions import db
from torneio.models import Formato, Partida, Rodada, StatusTorneio, Torneio, Usuario
from tests.helpers import criar_torneio


@pytest.fixture
def organizador(app):
    usuario = Usuario(nome='Orlando')
    db.session.add(usuario)
    db.session.commit()
    return usuario


@pytest.fixture
def torneio(app, organizador):
    torneio = Torneio(
        nome='Open de Primavera', descricao='Abertura da temporada.', data_torneio=datetime.date(2026, 11, 1),
        local='Clube Central', premiacao='Troféu', regulamento='Melhor de 3 sets.', organizador=organizador,
    )
    db.session.add(torneio)
    db.session.commit()
    return torneio


class TestTorneioModel:

    def test_torneio_criado_com_sucesso(self, torneio, organizador):
        assert Torneio.query.count() == 1
        assert torneio.nome == 'Open de Primavera'
        assert torneio.organizador == organizador

    def test_valores_padrao(self, torneio):
        assert torneio.formato == Formato.ELIMINATORIA
        assert torneio.status == StatusTorneio.RASCUNHO
        assert torneio.criado_em is not None

    def test_str_retorna_nome(self, torneio):
        assert str(torneio) == 'Open de Primavera'

    def test_url(self, app, torneio):
        with app.test_request_context():
            assert torneio.url == f'/torneios/{torneio.id}/'

    def test_rotulos(self, torneio):
        assert torneio.formato_label == 'Eliminatória simples'
        assert torneio.status_label == 'Rascunho'

    def test_campos_opcionais_em_branco(self, app):
        torneio = Torneio(nome='Simples', data_torneio=datetime.date(2026, 1, 1), local='Clube')
        db.session.add(torneio)
        db.session.commit()
        assert torneio.descricao == ''
        assert torneio.organizador is None
        assert torneio.regulamento_arquivo == ''

    def test_excluir_organizador_mantem_torneio(self, torneio, organizador):
        db.session.delete(organizador)
        db.session.commit()
        assert db.session.get(Torneio, torneio.id).organizador_id is None

    def test_str_do_organizador(self, organizador):
        assert str(organizador) == 'Orlando'

    def test_excluir_torneio_remove_inscricoes_e_partidas(self, app):
        from torneio import services
        from torneio.models import Inscricao
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        db.session.delete(torneio)
        db.session.commit()
        assert Inscricao.query.count() == 0
        assert Partida.query.count() == 0


class TestInscritosOrdenados:

    def test_cabecas_primeiro_e_demais_por_nome(self, app):
        from torneio.models import Inscricao, Jogador
        torneio = criar_torneio()
        for nome, semente in [('Zeca', None), ('Ana', None), ('Bruno', 2), ('Carlos', 1)]:
            torneio.inscricoes.append(Inscricao(jogador=Jogador(nome=nome), cabeca_de_chave=semente))
        db.session.commit()
        assert [i.jogador.nome for i in torneio.inscritos] == ['Carlos', 'Bruno', 'Ana', 'Zeca']


class TestAceitaInscricoes:

    @pytest.mark.parametrize('status, esperado', [
        (StatusTorneio.RASCUNHO, True),
        (StatusTorneio.INSCRICOES, True),
        (StatusTorneio.EM_ANDAMENTO, False),
        (StatusTorneio.CANCELADO, False),
        (StatusTorneio.FINALIZADO, False),
    ])
    def test_por_status(self, app, status, esperado):
        assert criar_torneio(status=status).aceita_inscricoes is esperado

    def test_com_partidas_nao_aceita(self, app):
        torneio = criar_torneio()
        db.session.add(Partida(torneio=torneio, rodada=Rodada.F))
        db.session.commit()
        assert torneio.aceita_inscricoes is False
