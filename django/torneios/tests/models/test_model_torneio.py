import datetime

from django.contrib.auth.models import User
from django.test import TestCase

from torneios.models import Partida, Torneio
from torneios.tests.helpers import criar_torneio


class TorneioModelTest(TestCase):

    def setUp(self):
        self.organizador = User.objects.create_user('orlando', password='senha-segura-123')
        self.torneio = Torneio.objects.create(
            nome='Open de Primavera',
            descricao='Torneio de abertura da temporada.',
            data_torneio=datetime.date(2026, 11, 1),
            local='Clube Central',
            premiacao='Troféu',
            regulamento='Melhor de 3 sets.',
            organizador=self.organizador,
        )

    def test_torneio_criado_com_sucesso(self):
        self.assertTrue(Torneio.objects.exists())
        self.assertEqual(self.torneio.nome, 'Open de Primavera')
        self.assertEqual(self.torneio.local, 'Clube Central')
        self.assertEqual(self.torneio.organizador, self.organizador)

    def test_valores_padrao(self):
        self.assertEqual(self.torneio.formato, Torneio.Formato.ELIMINATORIA)
        self.assertEqual(self.torneio.status, Torneio.Status.RASCUNHO)
        self.assertIsNotNone(self.torneio.criado_em)

    def test_str_retorna_nome(self):
        self.assertEqual(str(self.torneio), 'Open de Primavera')

    def test_get_absolute_url(self):
        self.assertEqual(self.torneio.get_absolute_url(), f'/torneios/{self.torneio.pk}/')

    def test_campos_opcionais_podem_ficar_em_branco(self):
        torneio = Torneio.objects.create(nome='Simples', data_torneio=datetime.date(2026, 1, 1), local='Clube')
        self.assertEqual(torneio.descricao, '')
        self.assertIsNone(torneio.organizador)
        self.assertFalse(torneio.regulamento_arquivo)

    def test_excluir_organizador_mantem_torneio(self):
        self.organizador.delete()
        self.torneio.refresh_from_db()
        self.assertIsNone(self.torneio.organizador)

    def test_ordenacao_mais_recente_primeiro(self):
        antigo = Torneio.objects.create(nome='Antigo', data_torneio=datetime.date(2020, 1, 1), local='Clube')
        self.assertEqual(list(Torneio.objects.all()), [self.torneio, antigo])


class TorneioAceitaInscricoesTest(TestCase):

    def test_rascunho_aceita(self):
        self.assertTrue(criar_torneio(status=Torneio.Status.RASCUNHO).aceita_inscricoes)

    def test_inscricoes_abertas_aceita(self):
        self.assertTrue(criar_torneio(status=Torneio.Status.INSCRICOES).aceita_inscricoes)

    def test_em_andamento_nao_aceita(self):
        self.assertFalse(criar_torneio(status=Torneio.Status.EM_ANDAMENTO).aceita_inscricoes)

    def test_cancelado_nao_aceita(self):
        self.assertFalse(criar_torneio(status=Torneio.Status.CANCELADO).aceita_inscricoes)

    def test_com_partidas_nao_aceita(self):
        torneio = criar_torneio()
        Partida.objects.create(torneio=torneio, rodada=Partida.Rodada.F)
        self.assertFalse(torneio.aceita_inscricoes)
