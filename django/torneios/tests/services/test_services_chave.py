from django.test import SimpleTestCase, TestCase

from torneios import services
from torneios.models import Inscricao, Jogador, Partida, Torneio
from torneios.tests.helpers import criar_torneio, jogar, jogar_favorito, jogar_rodada


class OrdemCabecasDeChaveTest(SimpleTestCase):

    def test_chave_de_2(self):
        self.assertEqual(services.ordem_cabecas_de_chave(2), [1, 2])

    def test_chave_de_4(self):
        self.assertEqual(services.ordem_cabecas_de_chave(4), [1, 4, 2, 3])

    def test_chave_de_8(self):
        self.assertEqual(services.ordem_cabecas_de_chave(8), [1, 8, 4, 5, 2, 7, 3, 6])

    def test_chave_de_32_contem_todas_as_sementes(self):
        self.assertEqual(sorted(services.ordem_cabecas_de_chave(32)), list(range(1, 33)))


class OrdenarPorSementeTest(TestCase):

    def test_cabecas_primeiro_e_demais_depois(self):
        torneio = criar_torneio()
        inscricoes = [
            Inscricao.objects.create(torneio=torneio, jogador=Jogador.objects.create(nome=nome), cabeca_de_chave=semente)
            for nome, semente in [('A', None), ('B', 2), ('C', None), ('D', 1)]
        ]
        ordenadas = services.ordenar_por_semente(inscricoes)
        self.assertEqual([i.jogador.nome for i in ordenadas[:2]], ['D', 'B'])
        self.assertEqual({i.jogador.nome for i in ordenadas[2:]}, {'A', 'C'})


class ParesTodosContraTodosTest(SimpleTestCase):

    def confrontos(self, n):
        return services.pares_todos_contra_todos(range(n))

    def test_quantidade_de_jogos_par(self):
        self.assertEqual(len(self.confrontos(4)), 6)

    def test_quantidade_de_jogos_impar(self):
        self.assertEqual(len(self.confrontos(5)), 10)

    def test_sem_confrontos_repetidos(self):
        pares = {frozenset((a, b)) for _, a, b in self.confrontos(6)}
        self.assertEqual(len(pares), 15)

    def test_jogador_joga_uma_vez_por_rodada(self):
        for jornada in range(1, 6):
            jogos = [(a, b) for j, a, b in self.confrontos(6) if j == jornada]
            jogadores = [x for par in jogos for x in par]
            self.assertEqual(len(jogadores), len(set(jogadores)))

    def test_numero_de_rodadas(self):
        self.assertEqual(max(j for j, _, _ in self.confrontos(4)), 3)
        self.assertEqual(max(j for j, _, _ in self.confrontos(5)), 5)


class GerarChaveEliminatoriaTest(TestCase):

    def test_quatro_jogadores(self):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        self.assertEqual(torneio.partidas.filter(rodada='SF').count(), 2)
        self.assertEqual(torneio.partidas.filter(rodada='F').count(), 1)

    def test_status_em_andamento(self):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        torneio.refresh_from_db()
        self.assertEqual(torneio.status, Torneio.Status.EM_ANDAMENTO)

    def test_partidas_ligadas_a_proxima(self):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        final = torneio.partidas.get(rodada='F')
        for semi in torneio.partidas.filter(rodada='SF'):
            self.assertEqual(semi.proxima_partida, final)
        self.assertIsNone(final.proxima_partida)

    def test_cabecas_1_e_2_em_lados_opostos(self):
        torneio = criar_torneio(jogadores=8)
        services.gerar_chave(torneio)
        quartas = list(torneio.partidas.filter(rodada='QF').order_by('posicao'))
        self.assertEqual(quartas[0].inscricao_1.cabeca_de_chave, 1)
        self.assertEqual(quartas[0].inscricao_2.cabeca_de_chave, 8)
        self.assertEqual(quartas[2].inscricao_1.cabeca_de_chave, 2)

    def test_byes_para_os_cabecas(self):
        torneio = criar_torneio(jogadores=6)
        services.gerar_chave(torneio)
        self.assertEqual(torneio.partidas.filter(placar='BYE').count(), 2)
        semis = list(torneio.partidas.filter(rodada='SF').order_by('posicao'))
        self.assertEqual(semis[0].inscricao_1.cabeca_de_chave, 1)
        self.assertEqual(semis[1].inscricao_1.cabeca_de_chave, 2)

    def test_chave_de_32(self):
        torneio = criar_torneio(jogadores=32)
        services.gerar_chave(torneio)
        self.assertEqual(torneio.partidas.filter(rodada='R32').count(), 16)
        self.assertEqual(torneio.partidas.count(), 31)

    def test_campeao_ao_fim(self):
        torneio = criar_torneio(jogadores=6)
        services.gerar_chave(torneio)
        for rodada in ['QF', 'SF', 'F']:
            jogar_rodada(torneio, rodada)
        torneio.refresh_from_db()
        self.assertEqual(torneio.status, Torneio.Status.FINALIZADO)
        self.assertEqual(services.campeao(torneio).cabeca_de_chave, 1)


class GerarChaveErrosTest(TestCase):

    def test_chave_ja_gerada(self):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        with self.assertRaisesMessage(services.FluxoError, 'já foi gerada'):
            services.gerar_chave(torneio)

    def test_torneio_cancelado(self):
        torneio = criar_torneio(jogadores=2, status=Torneio.Status.CANCELADO)
        with self.assertRaises(services.FluxoError):
            services.gerar_chave(torneio)

    def test_torneio_finalizado(self):
        torneio = criar_torneio(jogadores=2, status=Torneio.Status.FINALIZADO)
        with self.assertRaises(services.FluxoError):
            services.gerar_chave(torneio)

    def test_eliminatoria_com_um_jogador(self):
        with self.assertRaisesMessage(services.FluxoError, 'pelo menos 2 jogadores'):
            services.gerar_chave(criar_torneio(jogadores=1))

    def test_eliminatoria_com_mais_de_32(self):
        with self.assertRaisesMessage(services.FluxoError, 'no máximo 32'):
            services.gerar_chave(criar_torneio(jogadores=33))

    def test_round_robin_com_um_jogador(self):
        with self.assertRaises(services.FluxoError):
            services.gerar_chave(criar_torneio(Torneio.Formato.ROUND_ROBIN, jogadores=1))

    def test_grupos_com_dois_jogadores(self):
        with self.assertRaisesMessage(services.FluxoError, 'pelo menos 3'):
            services.gerar_chave(criar_torneio(Torneio.Formato.GRUPOS, jogadores=2))

    def test_grupos_com_classificados_demais(self):
        # 68 jogadores -> 17 grupos -> 34 classificados, acima do limite da chave.
        with self.assertRaisesMessage(services.FluxoError, 'Jogadores demais'):
            services.gerar_chave(criar_torneio(Torneio.Formato.GRUPOS, jogadores=68))

    def test_erro_nao_deixa_partidas(self):
        torneio = criar_torneio(jogadores=33)
        with self.assertRaises(services.FluxoError):
            services.gerar_chave(torneio)
        self.assertFalse(torneio.partidas.exists())


class RoundRobinTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio(Torneio.Formato.ROUND_ROBIN, jogadores=5)
        services.gerar_chave(self.torneio)

    def test_todos_contra_todos(self):
        self.assertEqual(self.torneio.partidas.count(), 10)
        self.assertFalse(self.torneio.partidas.exclude(rodada='RR').exists())

    def test_sem_campeao_antes_do_fim(self):
        self.assertIsNone(services.campeao(self.torneio))

    def test_finaliza_e_define_campeao(self):
        for partida in self.torneio.partidas.all():
            jogar_favorito(partida)
        self.torneio.refresh_from_db()
        self.assertEqual(self.torneio.status, Torneio.Status.FINALIZADO)
        self.assertEqual(services.campeao(self.torneio).cabeca_de_chave, 1)


class GruposTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio(Torneio.Formato.GRUPOS, jogadores=8)
        services.gerar_chave(self.torneio)

    def test_distribuicao_em_grupos(self):
        grupos = list(self.torneio.inscricoes.values_list('grupo', flat=True))
        self.assertEqual(grupos.count('A'), 4)
        self.assertEqual(grupos.count('B'), 4)

    def test_cabecas_1_e_2_em_grupos_diferentes(self):
        cabecas = self.torneio.inscricoes.filter(cabeca_de_chave__in=[1, 2])
        self.assertEqual({i.grupo for i in cabecas}, {'A', 'B'})

    def test_jogos_por_grupo(self):
        self.assertEqual(self.torneio.partidas.filter(grupo='A').count(), 6)
        self.assertEqual(self.torneio.partidas.filter(grupo='B').count(), 6)

    def test_nao_finaliza_so_com_grupos(self):
        for partida in self.torneio.partidas.all():
            jogar_favorito(partida)
        self.torneio.refresh_from_db()
        self.assertEqual(self.torneio.status, Torneio.Status.EM_ANDAMENTO)

    def test_mata_mata_antes_de_terminar_grupos(self):
        with self.assertRaisesMessage(services.FluxoError, 'Finalize todas as partidas'):
            services.gerar_mata_mata_dos_grupos(self.torneio)

    def test_mata_mata_cruza_grupos(self):
        for partida in self.torneio.partidas.all():
            jogar_favorito(partida)
        services.gerar_mata_mata_dos_grupos(self.torneio)
        semis = list(self.torneio.partidas.filter(rodada='SF').order_by('posicao'))
        for semi in semis:
            self.assertNotEqual(semi.inscricao_1.grupo, semi.inscricao_2.grupo)

    def test_mata_mata_gerado_duas_vezes(self):
        for partida in self.torneio.partidas.all():
            jogar_favorito(partida)
        services.gerar_mata_mata_dos_grupos(self.torneio)
        with self.assertRaisesMessage(services.FluxoError, 'já foi gerado'):
            services.gerar_mata_mata_dos_grupos(self.torneio)

    def test_campeao_depois_do_mata_mata(self):
        for partida in self.torneio.partidas.all():
            jogar_favorito(partida)
        services.gerar_mata_mata_dos_grupos(self.torneio)
        jogar_rodada(self.torneio, 'SF')
        jogar_rodada(self.torneio, 'F')
        self.torneio.refresh_from_db()
        self.assertEqual(self.torneio.status, Torneio.Status.FINALIZADO)
        self.assertIsNotNone(services.campeao(self.torneio))

    def test_mata_mata_em_torneio_sem_grupos(self):
        torneio = criar_torneio(jogadores=4)
        with self.assertRaisesMessage(services.FluxoError, 'não tem fase de grupos'):
            services.gerar_mata_mata_dos_grupos(torneio)


class GruposPequenosTest(TestCase):

    def test_tres_jogadores_um_grupo_e_final(self):
        torneio = criar_torneio(Torneio.Formato.GRUPOS, jogadores=3)
        services.gerar_chave(torneio)
        self.assertEqual(set(torneio.inscricoes.values_list('grupo', flat=True)), {'A'})
        for partida in torneio.partidas.all():
            jogar_favorito(partida)
        services.gerar_mata_mata_dos_grupos(torneio)
        final = torneio.partidas.get(rodada='F')
        self.assertEqual({final.inscricao_1.cabeca_de_chave, final.inscricao_2.cabeca_de_chave}, {1, 2})


class RefazerChaveTest(TestCase):

    def test_apaga_partidas_e_grupos(self):
        torneio = criar_torneio(Torneio.Formato.GRUPOS, jogadores=4)
        services.gerar_chave(torneio)
        services.refazer_chave(torneio)
        self.assertFalse(torneio.partidas.exists())
        self.assertFalse(torneio.inscricoes.exclude(grupo='').exists())
        self.assertEqual(torneio.status, Torneio.Status.INSCRICOES)


class AtualizarStatusTorneioTest(TestCase):

    def test_sem_partidas_mantem_status(self):
        torneio = criar_torneio(status=Torneio.Status.INSCRICOES)
        services.atualizar_status_torneio(torneio)
        torneio.refresh_from_db()
        self.assertEqual(torneio.status, Torneio.Status.INSCRICOES)


class RegistrarResultadoTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio(jogadores=4)
        services.gerar_chave(self.torneio)
        self.semi = self.torneio.partidas.filter(rodada='SF').order_by('posicao').first()

    def test_vencedor_ocupa_vaga_na_final(self):
        jogar(self.semi, vence_1=False)
        final = self.torneio.partidas.get(rodada='F')
        self.assertEqual(final.inscricao_1, self.semi.inscricao_2)

    def test_segunda_semi_ocupa_vaga_2(self):
        semi_2 = self.torneio.partidas.filter(rodada='SF').order_by('posicao').last()
        jogar(semi_2)
        final = self.torneio.partidas.get(rodada='F')
        self.assertIsNone(final.inscricao_1)
        self.assertEqual(final.inscricao_2, semi_2.inscricao_1)

    def test_corrigir_resultado_troca_vencedor_na_final(self):
        jogar(self.semi)
        jogar(self.semi, vence_1=False)
        final = self.torneio.partidas.get(rodada='F')
        self.assertEqual(final.inscricao_1, self.semi.inscricao_2)

    def test_reabrir_partida_limpa_vaga(self):
        jogar(self.semi)
        services.registrar_resultado(self.semi, Partida.Status.AGENDADA, '', self.semi.inscricao_1, None)
        self.semi.refresh_from_db()
        self.assertIsNone(self.semi.vencedor)
        self.assertIsNone(self.torneio.partidas.get(rodada='F').inscricao_1)

    def test_cancelado_nao_volta_para_andamento(self):
        Torneio.objects.filter(pk=self.torneio.pk).update(status=Torneio.Status.CANCELADO)
        self.semi.torneio.refresh_from_db()
        jogar(self.semi)
        self.torneio.refresh_from_db()
        self.assertEqual(self.torneio.status, Torneio.Status.CANCELADO)
