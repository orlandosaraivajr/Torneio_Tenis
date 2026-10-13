from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from torneios.models import Jogador, Partida, Torneio


class PopularDemoTest(TestCase):

    def setUp(self):
        self.saida = StringIO()
        call_command('popular_demo', stdout=self.saida)

    def test_mensagem_de_sucesso(self):
        self.assertIn('Dados de demonstração criados.', self.saida.getvalue())

    def test_cria_tres_torneios(self):
        self.assertEqual(
            set(Torneio.objects.values_list('formato', flat=True)),
            {Torneio.Formato.ELIMINATORIA, Torneio.Formato.GRUPOS, Torneio.Formato.ROUND_ROBIN},
        )

    def test_cria_jogadores(self):
        self.assertEqual(Jogador.objects.count(), 16)

    def test_torneio_de_grupos_ja_tem_mata_mata(self):
        grupos = Torneio.objects.get(formato=Torneio.Formato.GRUPOS)
        self.assertTrue(grupos.partidas.filter(rodada=Partida.Rodada.F).exists())

    def test_pode_rodar_duas_vezes_sem_duplicar_jogadores(self):
        call_command('popular_demo', stdout=StringIO())
        self.assertEqual(Jogador.objects.count(), 16)
        self.assertEqual(Torneio.objects.count(), 6)
