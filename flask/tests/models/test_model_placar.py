import pytest

from torneio.models import Formato, parse_placar


class TestParsePlacar:

    def test_placar_em_dois_sets(self):
        assert parse_placar('6-4 6-3') == [(6, 4, None), (6, 3, None)]

    def test_placar_com_tiebreak(self):
        assert parse_placar('6-4 3-6 7-6(5)') == [(6, 4, None), (3, 6, None), (7, 6, 5)]

    def test_placar_com_super_tiebreak(self):
        assert parse_placar('4-6 6-3 10-8') == [(4, 6, None), (6, 3, None), (10, 8, None)]

    def test_espacos_extras_sao_ignorados(self):
        assert parse_placar('  6-4    6-3 ') == [(6, 4, None), (6, 3, None)]

    @pytest.mark.parametrize('vazio', ['', None])
    def test_placar_vazio(self, vazio):
        assert parse_placar(vazio) == []

    @pytest.mark.parametrize('invalido', ['6x4', '6-4-3', '100-4', 'abc'])
    def test_formato_invalido(self, invalido):
        with pytest.raises(ValueError):
            parse_placar(invalido)

    def test_mensagem_indica_set_invalido(self):
        with pytest.raises(ValueError, match='Set inválido: "abc"'):
            parse_placar('6-4 abc')


class TestChoices:

    def test_lista_de_opcoes(self):
        assert ('ELIM', 'Eliminatória simples') in Formato.choices()

    def test_rotulo(self):
        assert Formato.label('GRUPOS') == 'Grupos + mata-mata'

    def test_rotulo_desconhecido_devolve_valor(self):
        assert Formato.label('XPTO') == 'XPTO'
