from django.test import TestCase

from torneios import services
from torneios.models import Partida, Torneio
from torneios.tests.helpers import criar_torneio, jogar


class VencedorPeloPlacarTest(TestCase):

    def setUp(self):
        torneio = criar_torneio(jogadores=2)
        self.ins_1, self.ins_2 = torneio.inscricoes.all()
        self.partida = Partida(torneio=torneio, rodada=Partida.Rodada.F, inscricao_1=self.ins_1, inscricao_2=self.ins_2)

    def test_jogador_1_vence(self):
        self.assertEqual(services.vencedor_pelo_placar(self.partida, '6-4 6-3'), self.ins_1)

    def test_jogador_2_vence_em_tres_sets(self):
        self.assertEqual(services.vencedor_pelo_placar(self.partida, '6-4 3-6 8-10'), self.ins_2)

    def test_empate_em_sets(self):
        self.assertIsNone(services.vencedor_pelo_placar(self.partida, '6-4 4-6'))

    def test_placar_vazio(self):
        self.assertIsNone(services.vencedor_pelo_placar(self.partida, ''))

    def test_set_empatado_nao_conta(self):
        self.assertEqual(services.vencedor_pelo_placar(self.partida, '6-6 6-3'), self.ins_1)


class ClassificacaoTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio(Torneio.Formato.ROUND_ROBIN, jogadores=3)
        services.gerar_chave(self.torneio)
        self.a, self.b, self.c = self.torneio.inscricoes.order_by('cabeca_de_chave')

    def resultado(self, vencedor, perdedor, placar):
        partida = self.torneio.partidas.get(inscricao_1__in=[vencedor, perdedor], inscricao_2__in=[vencedor, perdedor])
        if partida.inscricao_1 != vencedor:
            placar = ' '.join('-'.join(reversed(s.split('-'))) for s in placar.split())
        services.registrar_resultado(partida, Partida.Status.FINALIZADA, placar, vencedor, None)

    def tabela(self):
        return services.classificacao(self.torneio.inscricoes.all(), self.torneio.partidas.all())

    def test_tabela_vazia_antes_dos_jogos(self):
        for linha in self.tabela():
            self.assertEqual(linha['jogos'], 0)
            self.assertEqual(linha['vitorias'], 0)

    def test_contagem_de_vitorias_sets_e_games(self):
        self.resultado(self.a, self.b, '6-4 6-3')
        linha_a = next(l for l in self.tabela() if l['inscricao'] == self.a)
        self.assertEqual(linha_a['vitorias'], 1)
        self.assertEqual(linha_a['sets_pro'], 2)
        self.assertEqual(linha_a['games_pro'], 12)
        self.assertEqual(linha_a['games_contra'], 7)
        self.assertEqual(linha_a['saldo_games'], 5)

    def test_ordem_por_vitorias(self):
        self.resultado(self.c, self.a, '6-0 6-0')
        self.resultado(self.c, self.b, '6-0 6-0')
        self.assertEqual(self.tabela()[0]['inscricao'], self.c)

    def test_desempate_por_saldo_de_sets(self):
        self.resultado(self.a, self.b, '6-4 6-4')
        self.resultado(self.b, self.c, '6-4 6-4')
        self.resultado(self.c, self.a, '4-6 6-4 6-4')
        # Todos com 1 vitória. Saldo de sets: A +1 (3-2), B 0 (2-2), C -1 (2-3).
        self.assertEqual([l['inscricao'] for l in self.tabela()], [self.a, self.b, self.c])

    def test_desempate_por_saldo_de_games(self):
        self.resultado(self.a, self.b, '6-0 6-0')
        self.resultado(self.b, self.c, '6-4 6-4')
        self.resultado(self.c, self.a, '6-4 6-4')
        self.assertEqual(self.tabela()[0]['inscricao'], self.a)

    def test_wo_conta_vitoria_sem_games(self):
        partida = self.torneio.partidas.get(inscricao_1__in=[self.a, self.b], inscricao_2__in=[self.a, self.b])
        services.registrar_resultado(partida, Partida.Status.WO, '', self.b, None)
        linha_b = next(l for l in self.tabela() if l['inscricao'] == self.b)
        self.assertEqual(linha_b['vitorias'], 1)
        self.assertEqual(linha_b['games_pro'], 0)

    def test_partidas_nao_encerradas_ignoradas(self):
        partida = self.torneio.partidas.first()
        services.registrar_resultado(partida, Partida.Status.EM_ANDAMENTO, '6-4 2-1', None, None)
        self.assertTrue(all(l['jogos'] == 0 for l in self.tabela()))


class CampeaoTest(TestCase):

    def test_sem_chave(self):
        self.assertIsNone(services.campeao(criar_torneio(jogadores=2)))

    def test_round_robin_sem_partidas(self):
        self.assertIsNone(services.campeao(criar_torneio(Torneio.Formato.ROUND_ROBIN, jogadores=2)))

    def test_final_sem_resultado(self):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        self.assertIsNone(services.campeao(torneio))

    def test_vencedor_da_final(self):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        final = torneio.partidas.get()
        jogar(final, vence_1=False)
        self.assertEqual(services.campeao(torneio), final.inscricao_2)
