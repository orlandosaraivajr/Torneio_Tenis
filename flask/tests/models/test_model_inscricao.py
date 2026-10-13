import pytest
from sqlalchemy.exc import IntegrityError

from torneio.extensions import db
from torneio.models import Inscricao
from tests.helpers import criar_jogador, criar_torneio


@pytest.fixture
def inscricao(app):
    inscricao = Inscricao(torneio=criar_torneio(), jogador=criar_jogador())
    db.session.add(inscricao)
    db.session.commit()
    return inscricao


class TestInscricaoModel:

    def test_inscricao_criada_com_sucesso(self, inscricao):
        assert inscricao.torneio.nome == 'Open de Primavera'
        assert inscricao.jogador.nome == 'Gustavo Kuerten'
        assert inscricao.data_inscricao is not None

    def test_campos_opcionais(self, inscricao):
        assert inscricao.cabeca_de_chave is None
        assert inscricao.grupo == ''

    def test_str_sem_cabeca_de_chave(self, inscricao):
        assert str(inscricao) == 'Gustavo Kuerten'

    def test_str_com_cabeca_de_chave(self, inscricao):
        inscricao.cabeca_de_chave = 1
        assert str(inscricao) == 'Gustavo Kuerten [1]'

    def test_jogador_nao_pode_se_inscrever_duas_vezes(self, inscricao):
        db.session.add(Inscricao(torneio=inscricao.torneio, jogador=inscricao.jogador))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_mesmo_jogador_em_torneios_diferentes(self, inscricao):
        db.session.add(Inscricao(torneio=criar_torneio(nome='Outro'), jogador=inscricao.jogador))
        db.session.commit()
        assert len(inscricao.jogador.inscricoes) == 2

    def test_excluir_torneio_remove_inscricoes(self, inscricao):
        db.session.delete(inscricao.torneio)
        db.session.commit()
        assert Inscricao.query.count() == 0

    def test_excluir_jogador_remove_inscricoes(self, inscricao):
        db.session.delete(inscricao.jogador)
        db.session.commit()
        assert Inscricao.query.count() == 0
