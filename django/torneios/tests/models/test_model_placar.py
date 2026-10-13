from django.test import SimpleTestCase

from torneios.models import parse_placar


class ParsePlacarTest(SimpleTestCase):

    def test_placar_em_dois_sets(self):
        self.assertEqual(parse_placar('6-4 6-3'), [(6, 4, None), (6, 3, None)])

    def test_placar_com_tiebreak(self):
        self.assertEqual(
            parse_placar('6-4 3-6 7-6(5)'),
            [(6, 4, None), (3, 6, None), (7, 6, 5)]
        )

    def test_placar_com_super_tiebreak(self):
        self.assertEqual(parse_placar('4-6 6-3 10-8'), [(4, 6, None), (6, 3, None), (10, 8, None)])

    def test_espacos_extras_sao_ignorados(self):
        self.assertEqual(parse_placar('  6-4    6-3 '), [(6, 4, None), (6, 3, None)])

    def test_placar_vazio(self):
        self.assertEqual(parse_placar(''), [])

    def test_placar_none(self):
        self.assertEqual(parse_placar(None), [])

    def test_separador_invalido(self):
        with self.assertRaises(ValueError):
            parse_placar('6x4')

    def test_set_com_tres_numeros(self):
        with self.assertRaises(ValueError):
            parse_placar('6-4-3')

    def test_games_com_tres_digitos(self):
        with self.assertRaises(ValueError):
            parse_placar('100-4')

    def test_mensagem_indica_set_invalido(self):
        with self.assertRaisesMessage(ValueError, 'Set inválido: "abc"'):
            parse_placar('6-4 abc')
