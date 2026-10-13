from django.test import TestCase

from torneios import services
from torneios.models import Partida, Torneio
from torneios.tests.helpers import criar_torneio, jogar, jogar_favorito


class PartidaModelTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio(jogadores=2)
        self.ins_1, self.ins_2 = self.torneio.inscricoes.all()
        self.partida = Partida.objects.create(
            torneio=self.torneio,
            rodada=Partida.Rodada.F,
            inscricao_1=self.ins_1,
            inscricao_2=self.ins_2,
            placar='6-4 6-7(5) 10-8',
        )

    def test_partida_criada_com_sucesso(self):
        self.assertEqual(self.partida.inscricao_1, self.ins_1)
        self.assertEqual(self.partida.inscricao_2, self.ins_2)

    def test_valores_padrao(self):
        self.assertEqual(self.partida.status, Partida.Status.AGENDADA)
        self.assertEqual(self.partida.posicao, 0)
        self.assertIsNone(self.partida.vencedor)
        self.assertIsNone(self.partida.data_hora)
        self.assertIsNone(self.partida.proxima_partida)

    def test_str(self):
        self.assertEqual(str(self.partida), 'Final: Jogador 01 x Jogador 02')

    def test_nomes_dos_jogadores(self):
        self.assertEqual(self.partida.nome_1, 'Jogador 01')
        self.assertEqual(self.partida.nome_2, 'Jogador 02')

    def test_nome_a_definir_sem_jogador(self):
        partida = Partida.objects.create(torneio=self.torneio, rodada=Partida.Rodada.SF)
        self.assertEqual(partida.nome_1, 'A definir')
        self.assertEqual(partida.nome_2, 'A definir')

    def test_nome_bye(self):
        partida = Partida(torneio=self.torneio, rodada=Partida.Rodada.SF, inscricao_1=self.ins_1, placar='BYE')
        self.assertEqual(partida.nome_2, 'BYE')
        self.assertTrue(partida.is_bye)

    def test_sets_lidos_do_placar(self):
        self.assertEqual(self.partida.sets, [(6, 4, None), (6, 7, 5), (10, 8, None)])

    def test_sets_de_placar_invalido_retorna_vazio(self):
        self.partida.placar = 'placar ruim'
        self.assertEqual(self.partida.sets, [])

    def test_sets_de_bye_retorna_vazio(self):
        self.partida.placar = 'BYE'
        self.assertEqual(self.partida.sets, [])

    def test_excluir_torneio_remove_partidas(self):
        self.torneio.delete()
        self.assertFalse(Partida.objects.exists())


class PartidaEncerradaTest(TestCase):

    def setUp(self):
        self.partida = Partida(torneio=criar_torneio(), rodada=Partida.Rodada.F)

    def assertEncerrada(self, status, esperado):
        self.partida.status = status
        self.assertEqual(self.partida.encerrada, esperado)

    def test_agendada_nao_encerrada(self):
        self.assertEncerrada(Partida.Status.AGENDADA, False)

    def test_em_andamento_nao_encerrada(self):
        self.assertEncerrada(Partida.Status.EM_ANDAMENTO, False)

    def test_finalizada_encerrada(self):
        self.assertEncerrada(Partida.Status.FINALIZADA, True)

    def test_wo_encerrada(self):
        self.assertEncerrada(Partida.Status.WO, True)

    def test_abandono_encerrada(self):
        self.assertEncerrada(Partida.Status.ABANDONO, True)


class PartidaEditavelTest(TestCase):

    def test_partida_agendada_editavel(self):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        self.assertTrue(torneio.partidas.filter(rodada='SF').first().editavel)

    def test_bye_nao_editavel(self):
        torneio = criar_torneio(jogadores=3)
        services.gerar_chave(torneio)
        self.assertFalse(torneio.partidas.get(placar='BYE').editavel)

    def test_torneio_cancelado_nao_editavel(self):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        Torneio.objects.filter(pk=torneio.pk).update(status=Torneio.Status.CANCELADO)
        self.assertFalse(Partida.objects.get(torneio=torneio).editavel)

    def test_editavel_enquanto_proxima_nao_encerrada(self):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        semi = torneio.partidas.filter(rodada='SF').first()
        jogar(semi)
        self.assertTrue(Partida.objects.get(pk=semi.pk).editavel)

    def test_bloqueada_quando_proxima_encerrada(self):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        for semi in torneio.partidas.filter(rodada='SF'):
            jogar(semi)
        jogar(torneio.partidas.get(rodada='F'))
        self.assertFalse(torneio.partidas.filter(rodada='SF').first().editavel)

    def test_grupo_editavel_antes_do_mata_mata(self):
        torneio = criar_torneio(Torneio.Formato.GRUPOS, jogadores=4)
        services.gerar_chave(torneio)
        self.assertTrue(torneio.partidas.first().editavel)

    def test_grupo_bloqueado_depois_do_mata_mata(self):
        torneio = criar_torneio(Torneio.Formato.GRUPOS, jogadores=4)
        services.gerar_chave(torneio)
        for partida in torneio.partidas.all():
            jogar_favorito(partida)
        services.gerar_mata_mata_dos_grupos(torneio)
        self.assertFalse(torneio.partidas.filter(rodada='GR').first().editavel)
