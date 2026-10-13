import pytest

from torneio.models import Jogador
from tests.helpers import criar_jogador


class TestJogadorModel:

    def test_jogador_criado_com_sucesso(self, app):
        jogador = criar_jogador()
        assert Jogador.query.count() == 1
        assert jogador.nome == 'Gustavo Kuerten'

    def test_foto_opcional(self, app):
        assert criar_jogador().foto == ''

    def test_str_retorna_nome(self, app):
        assert str(criar_jogador()) == 'Gustavo Kuerten'

    def test_url(self, app):
        jogador = criar_jogador()
        with app.test_request_context():
            assert jogador.url == f'/jogadores/{jogador.id}/'


class TestIniciais:

    @pytest.mark.parametrize('nome, iniciais', [
        ('Gustavo Kuerten', 'GK'),
        ('Guga', 'G'),
        ('Bia Haddad Maia', 'BH'),
        ('joão fonseca', 'JF'),
    ])
    def test_iniciais(self, nome, iniciais):
        assert Jogador(nome=nome).iniciais == iniciais
