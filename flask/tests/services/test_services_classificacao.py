import pytest

from torneio import services
from torneio.models import Formato, Partida, Rodada, StatusPartida
from tests.helpers import criar_torneio, jogar, partidas


class TestVencedorPeloPlacar:

    @pytest.fixture
    def partida(self, app):
        torneio = criar_torneio(jogadores=2)
        ins_1, ins_2 = torneio.inscritos
        return Partida(torneio=torneio, rodada=Rodada.F, inscricao_1=ins_1, inscricao_2=ins_2)

    @pytest.mark.parametrize('placar, vencedor', [
        ('6-4 6-3', 1),
        ('6-4 3-6 8-10', 2),
        ('6-4 4-6', None),
        ('', None),
        ('6-6 6-3', 1),
    ])
    def test_vencedor(self, partida, placar, vencedor):
        esperado = {1: partida.inscricao_1, 2: partida.inscricao_2, None: None}[vencedor]
        assert services.vencedor_pelo_placar(partida, placar) == esperado


class TestClassificacao:

    @pytest.fixture
    def torneio(self, app):
        torneio = criar_torneio(Formato.ROUND_ROBIN, jogadores=3)
        services.gerar_chave(torneio)
        return torneio

    @staticmethod
    def resultado(torneio, vencedor, perdedor, placar, status=StatusPartida.FINALIZADA):
        partida = next(p for p in partidas(torneio) if {p.inscricao_1, p.inscricao_2} == {vencedor, perdedor})
        if partida.inscricao_1 != vencedor:
            placar = ' '.join('-'.join(reversed(s.split('-'))) for s in placar.split())
        services.registrar_resultado(partida, status, placar, vencedor, None)

    @staticmethod
    def tabela(torneio):
        return services.classificacao(torneio.inscricoes, partidas(torneio).all())

    def test_vazia_antes_dos_jogos(self, torneio):
        assert all(l['jogos'] == 0 and l['vitorias'] == 0 for l in self.tabela(torneio))

    def test_contagem(self, torneio):
        a, b, _ = torneio.inscritos
        self.resultado(torneio, a, b, '6-4 6-3')
        linha = next(l for l in self.tabela(torneio) if l['inscricao'] == a)
        assert (linha['vitorias'], linha['sets_pro'], linha['games_pro'], linha['games_contra']) == (1, 2, 12, 7)
        assert linha['saldo_games'] == 5

    def test_ordem_por_vitorias(self, torneio):
        a, b, c = torneio.inscritos
        self.resultado(torneio, c, a, '6-0 6-0')
        self.resultado(torneio, c, b, '6-0 6-0')
        assert self.tabela(torneio)[0]['inscricao'] == c

    def test_desempate_por_saldo_de_sets(self, torneio):
        a, b, c = torneio.inscritos
        self.resultado(torneio, a, b, '6-4 6-4')
        self.resultado(torneio, b, c, '6-4 6-4')
        self.resultado(torneio, c, a, '4-6 6-4 6-4')
        # Todos com 1 vitória. Saldo de sets: A +1 (3-2), B 0 (2-2), C -1 (2-3).
        assert [l['inscricao'] for l in self.tabela(torneio)] == [a, b, c]

    def test_desempate_por_saldo_de_games(self, torneio):
        a, b, c = torneio.inscritos
        self.resultado(torneio, a, b, '6-0 6-0')
        self.resultado(torneio, b, c, '6-4 6-4')
        self.resultado(torneio, c, a, '6-4 6-4')
        assert self.tabela(torneio)[0]['inscricao'] == a

    def test_wo_conta_vitoria_sem_games(self, torneio):
        a, b, _ = torneio.inscritos
        self.resultado(torneio, b, a, '', status=StatusPartida.WO)
        linha = next(l for l in self.tabela(torneio) if l['inscricao'] == b)
        assert (linha['vitorias'], linha['games_pro']) == (1, 0)

    def test_partidas_nao_encerradas_ignoradas(self, torneio):
        services.registrar_resultado(partidas(torneio).first(), StatusPartida.EM_ANDAMENTO, '6-4 2-1', None, None)
        assert all(l['jogos'] == 0 for l in self.tabela(torneio))


class TestCampeao:

    def test_sem_chave(self, app):
        assert services.campeao(criar_torneio(jogadores=2)) is None

    def test_round_robin_sem_partidas(self, app):
        assert services.campeao(criar_torneio(Formato.ROUND_ROBIN, jogadores=2)) is None

    def test_final_sem_resultado(self, app):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        assert services.campeao(torneio) is None

    def test_vencedor_da_final(self, app):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        final = partidas(torneio).one()
        jogar(final, vence_1=False)
        assert services.campeao(torneio) == final.inscricao_2
