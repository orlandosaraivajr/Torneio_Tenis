from django.test import TestCase

from torneios.models import Jogador


class JogadorModelTest(TestCase):

    def setUp(self):
        self.jogador = Jogador.objects.create(nome='Gustavo Kuerten')

    def test_jogador_criado_com_sucesso(self):
        self.assertTrue(Jogador.objects.exists())
        self.assertEqual(self.jogador.nome, 'Gustavo Kuerten')

    def test_foto_opcional(self):
        self.assertFalse(self.jogador.foto)

    def test_str_retorna_nome(self):
        self.assertEqual(str(self.jogador), 'Gustavo Kuerten')

    def test_get_absolute_url(self):
        self.assertEqual(self.jogador.get_absolute_url(), f'/jogadores/{self.jogador.pk}/')

    def test_verbose_name_plural(self):
        self.assertEqual(Jogador._meta.verbose_name_plural, 'jogadores')

    def test_ordenacao_por_nome(self):
        ana = Jogador.objects.create(nome='Ana Souza')
        self.assertEqual(list(Jogador.objects.all()), [ana, self.jogador])


class JogadorIniciaisTest(TestCase):

    def test_nome_e_sobrenome(self):
        self.assertEqual(Jogador(nome='Gustavo Kuerten').iniciais, 'GK')

    def test_apenas_primeiro_nome(self):
        self.assertEqual(Jogador(nome='Guga').iniciais, 'G')

    def test_usa_no_maximo_duas_letras(self):
        self.assertEqual(Jogador(nome='Bia Haddad Maia').iniciais, 'BH')

    def test_iniciais_maiusculas(self):
        self.assertEqual(Jogador(nome='joão fonseca').iniciais, 'JF')
