from django.db import IntegrityError
from django.test import TestCase

from torneios.models import Inscricao, Jogador
from torneios.tests.helpers import criar_torneio


class InscricaoModelTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio()
        self.jogador = Jogador.objects.create(nome='Gustavo Kuerten')
        self.inscricao = Inscricao.objects.create(torneio=self.torneio, jogador=self.jogador)

    def test_inscricao_criada_com_sucesso(self):
        self.assertEqual(self.inscricao.torneio, self.torneio)
        self.assertEqual(self.inscricao.jogador, self.jogador)
        self.assertIsNotNone(self.inscricao.data_inscricao)

    def test_campos_opcionais(self):
        self.assertIsNone(self.inscricao.cabeca_de_chave)
        self.assertEqual(self.inscricao.grupo, '')

    def test_str_sem_cabeca_de_chave(self):
        self.assertEqual(str(self.inscricao), 'Gustavo Kuerten')

    def test_str_com_cabeca_de_chave(self):
        self.inscricao.cabeca_de_chave = 1
        self.assertEqual(str(self.inscricao), 'Gustavo Kuerten [1]')

    def test_jogador_nao_pode_se_inscrever_duas_vezes(self):
        with self.assertRaises(IntegrityError):
            Inscricao.objects.create(torneio=self.torneio, jogador=self.jogador)

    def test_mesmo_jogador_em_torneios_diferentes(self):
        outro = criar_torneio(nome='Outro torneio')
        Inscricao.objects.create(torneio=outro, jogador=self.jogador)
        self.assertEqual(self.jogador.inscricoes.count(), 2)

    def test_excluir_torneio_remove_inscricoes(self):
        self.torneio.delete()
        self.assertFalse(Inscricao.objects.exists())

    def test_excluir_jogador_remove_inscricoes(self):
        self.jogador.delete()
        self.assertFalse(Inscricao.objects.exists())

    def test_ordenacao_por_cabeca_de_chave(self):
        cabeca = Inscricao.objects.create(
            torneio=self.torneio, jogador=Jogador.objects.create(nome='Zeca'), cabeca_de_chave=1
        )
        self.assertEqual(self.torneio.inscricoes.first(), cabeca)
