import pytest

from torneio import services
from torneio.extensions import db
from torneio.models import Formato, Inscricao, Jogador, Partida, StatusPartida, StatusTorneio, Torneio
from tests.helpers import criar_torneio, jogar, jogar_rodada, jogar_todas, partidas


class TestOrdemCabecasDeChave:

    @pytest.mark.parametrize('tamanho, ordem', [
        (2, [1, 2]),
        (4, [1, 4, 2, 3]),
        (8, [1, 8, 4, 5, 2, 7, 3, 6]),
    ])
    def test_ordem(self, tamanho, ordem):
        assert services.ordem_cabecas_de_chave(tamanho) == ordem

    def test_chave_de_32_contem_todas_as_sementes(self):
        assert sorted(services.ordem_cabecas_de_chave(32)) == list(range(1, 33))


class TestOrdenarPorSemente:

    def test_cabecas_primeiro(self):
        inscricoes = [Inscricao(jogador=Jogador(nome=n), cabeca_de_chave=s)
                      for n, s in [('A', None), ('B', 2), ('C', None), ('D', 1)]]
        ordenadas = services.ordenar_por_semente(inscricoes)
        assert [i.jogador.nome for i in ordenadas[:2]] == ['D', 'B']
        assert {i.jogador.nome for i in ordenadas[2:]} == {'A', 'C'}


class TestParesTodosContraTodos:

    @pytest.mark.parametrize('n, jogos', [(2, 1), (4, 6), (5, 10), (6, 15)])
    def test_quantidade_de_jogos(self, n, jogos):
        assert len(services.pares_todos_contra_todos(range(n))) == jogos

    def test_sem_confrontos_repetidos(self):
        pares = {frozenset((a, b)) for _, a, b in services.pares_todos_contra_todos(range(6))}
        assert len(pares) == 15

    def test_jogador_joga_uma_vez_por_rodada(self):
        jogos = services.pares_todos_contra_todos(range(6))
        for jornada in range(1, 6):
            jogadores = [x for j, a, b in jogos if j == jornada for x in (a, b)]
            assert len(jogadores) == len(set(jogadores))

    @pytest.mark.parametrize('n, rodadas', [(4, 3), (5, 5)])
    def test_numero_de_rodadas(self, n, rodadas):
        assert max(j for j, _, _ in services.pares_todos_contra_todos(range(n))) == rodadas


class TestGerarChaveEliminatoria:

    def test_quatro_jogadores(self, app):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        assert partidas(torneio, rodada='SF').count() == 2
        assert partidas(torneio, rodada='F').count() == 1
        assert torneio.status == StatusTorneio.EM_ANDAMENTO

    def test_partidas_ligadas_a_proxima(self, app):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        final = partidas(torneio, rodada='F').one()
        assert all(semi.proxima_partida == final for semi in partidas(torneio, rodada='SF'))
        assert final.proxima_partida is None

    def test_cabecas_1_e_2_em_lados_opostos(self, app):
        torneio = criar_torneio(jogadores=8)
        services.gerar_chave(torneio)
        quartas = partidas(torneio, rodada='QF').all()
        assert (quartas[0].inscricao_1.cabeca_de_chave, quartas[0].inscricao_2.cabeca_de_chave) == (1, 8)
        assert quartas[2].inscricao_1.cabeca_de_chave == 2

    def test_byes_para_os_cabecas(self, app):
        torneio = criar_torneio(jogadores=6)
        services.gerar_chave(torneio)
        assert partidas(torneio, placar='BYE').count() == 2
        semis = partidas(torneio, rodada='SF').all()
        assert [s.inscricao_1.cabeca_de_chave for s in semis] == [1, 2]

    def test_chave_de_32(self, app):
        torneio = criar_torneio(jogadores=32)
        services.gerar_chave(torneio)
        assert partidas(torneio, rodada='R32').count() == 16
        assert partidas(torneio).count() == 31

    def test_campeao_ao_fim(self, app):
        torneio = criar_torneio(jogadores=6)
        services.gerar_chave(torneio)
        for rodada in ['QF', 'SF', 'F']:
            jogar_rodada(torneio, rodada)
        assert torneio.status == StatusTorneio.FINALIZADO
        assert services.campeao(torneio).cabeca_de_chave == 1


class TestGerarChaveErros:

    def test_chave_ja_gerada(self, app):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        with pytest.raises(services.FluxoError, match='já foi gerada'):
            services.gerar_chave(torneio)

    @pytest.mark.parametrize('status', [StatusTorneio.CANCELADO, StatusTorneio.FINALIZADO])
    def test_torneio_encerrado(self, app, status):
        with pytest.raises(services.FluxoError):
            services.gerar_chave(criar_torneio(jogadores=2, status=status))

    @pytest.mark.parametrize('formato, jogadores, mensagem', [
        (Formato.ELIMINATORIA, 1, 'pelo menos 2 jogadores'),
        (Formato.ELIMINATORIA, 33, 'no máximo 32'),
        (Formato.ROUND_ROBIN, 1, 'pelo menos 2 jogadores'),
        (Formato.GRUPOS, 2, 'pelo menos 3'),
        (Formato.GRUPOS, 68, 'Jogadores demais'),
    ])
    def test_limites(self, app, formato, jogadores, mensagem):
        torneio = criar_torneio(formato, jogadores=jogadores)
        with pytest.raises(services.FluxoError, match=mensagem):
            services.gerar_chave(torneio)
        assert Partida.query.count() == 0
        assert db.session.get(Torneio, torneio.id).status == StatusTorneio.INSCRICOES


class TestRoundRobin:

    def test_todos_contra_todos_e_campeao(self, app):
        torneio = criar_torneio(Formato.ROUND_ROBIN, jogadores=5)
        services.gerar_chave(torneio)
        assert partidas(torneio).count() == 10
        assert services.campeao(torneio) is None
        jogar_todas(torneio)
        assert torneio.status == StatusTorneio.FINALIZADO
        assert services.campeao(torneio).cabeca_de_chave == 1


class TestGrupos:

    @pytest.fixture
    def torneio(self, app):
        torneio = criar_torneio(Formato.GRUPOS, jogadores=8)
        services.gerar_chave(torneio)
        return torneio

    def test_distribuicao(self, torneio):
        grupos = [i.grupo for i in torneio.inscricoes]
        assert grupos.count('A') == 4 and grupos.count('B') == 4

    def test_cabecas_em_grupos_diferentes(self, torneio):
        assert {i.grupo for i in torneio.inscricoes if i.cabeca_de_chave in (1, 2)} == {'A', 'B'}

    def test_jogos_por_grupo(self, torneio):
        assert partidas(torneio, grupo='A').count() == 6

    def test_nao_finaliza_so_com_grupos(self, torneio):
        jogar_todas(torneio)
        assert torneio.status == StatusTorneio.EM_ANDAMENTO

    def test_mata_mata_antes_de_terminar(self, torneio):
        with pytest.raises(services.FluxoError, match='Finalize todas as partidas'):
            services.gerar_mata_mata_dos_grupos(torneio)

    def test_mata_mata_cruza_grupos(self, torneio):
        jogar_todas(torneio)
        services.gerar_mata_mata_dos_grupos(torneio)
        for semi in partidas(torneio, rodada='SF'):
            assert semi.inscricao_1.grupo != semi.inscricao_2.grupo

    def test_mata_mata_duas_vezes(self, torneio):
        jogar_todas(torneio)
        services.gerar_mata_mata_dos_grupos(torneio)
        with pytest.raises(services.FluxoError, match='já foi gerado'):
            services.gerar_mata_mata_dos_grupos(torneio)

    def test_campeao_depois_do_mata_mata(self, torneio):
        jogar_todas(torneio)
        services.gerar_mata_mata_dos_grupos(torneio)
        jogar_rodada(torneio, 'SF')
        jogar_rodada(torneio, 'F')
        assert torneio.status == StatusTorneio.FINALIZADO
        assert services.campeao(torneio) is not None

    def test_torneio_sem_grupos(self, app):
        with pytest.raises(services.FluxoError, match='não tem fase de grupos'):
            services.gerar_mata_mata_dos_grupos(criar_torneio(jogadores=4))

    def test_tres_jogadores_vao_direto_a_final(self, app):
        torneio = criar_torneio(Formato.GRUPOS, jogadores=3)
        services.gerar_chave(torneio)
        jogar_todas(torneio)
        services.gerar_mata_mata_dos_grupos(torneio)
        final = partidas(torneio, rodada='F').one()
        assert {final.inscricao_1.cabeca_de_chave, final.inscricao_2.cabeca_de_chave} == {1, 2}


class TestRefazerChave:

    def test_apaga_partidas_e_grupos(self, app):
        torneio = criar_torneio(Formato.GRUPOS, jogadores=4)
        services.gerar_chave(torneio)
        services.refazer_chave(torneio)
        assert partidas(torneio).count() == 0
        assert all(i.grupo == '' for i in torneio.inscricoes)
        assert torneio.status == StatusTorneio.INSCRICOES
        assert torneio.aceita_inscricoes


class TestAtualizarStatus:

    def test_sem_partidas_mantem_status(self, app):
        torneio = criar_torneio()
        services.atualizar_status_torneio(torneio)
        assert torneio.status == StatusTorneio.INSCRICOES


class TestRegistrarResultado:

    @pytest.fixture
    def torneio(self, app):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        return torneio

    def test_vencedor_ocupa_vaga_1(self, torneio):
        semi = partidas(torneio, rodada='SF').first()
        jogar(semi, vence_1=False)
        assert partidas(torneio, rodada='F').one().inscricao_1 == semi.inscricao_2

    def test_segunda_semi_ocupa_vaga_2(self, torneio):
        semi_2 = partidas(torneio, rodada='SF').all()[1]
        jogar(semi_2)
        final = partidas(torneio, rodada='F').one()
        assert final.inscricao_1 is None
        assert final.inscricao_2 == semi_2.inscricao_1

    def test_corrigir_resultado_troca_vencedor(self, torneio):
        semi = partidas(torneio, rodada='SF').first()
        jogar(semi)
        jogar(semi, vence_1=False)
        assert partidas(torneio, rodada='F').one().inscricao_1 == semi.inscricao_2

    def test_reabrir_partida_limpa_vaga(self, torneio):
        semi = partidas(torneio, rodada='SF').first()
        jogar(semi)
        services.registrar_resultado(semi, StatusPartida.AGENDADA, '', semi.inscricao_1, None)
        assert semi.vencedor is None
        assert partidas(torneio, rodada='F').one().inscricao_1 is None

    def test_cancelado_nao_volta_para_andamento(self, torneio):
        torneio.status = StatusTorneio.CANCELADO
        db.session.commit()
        jogar(partidas(torneio, rodada='SF').first())
        assert torneio.status == StatusTorneio.CANCELADO

    def test_erro_desfaz_alteracoes(self, torneio, monkeypatch):
        semi = partidas(torneio, rodada='SF').first()

        def falhar(_partida):
            raise RuntimeError('falha simulada')

        monkeypatch.setattr(services, 'avancar_vencedor', falhar)
        with pytest.raises(RuntimeError):
            jogar(semi)
        assert db.session.get(Partida, semi.id).status == StatusPartida.AGENDADA
