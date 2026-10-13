from torneio.models import Formato, Jogador, Partida, Rodada, StatusPartida, Torneio, Usuario


class TestPopularDemo:

    def test_cria_dados(self, app):
        resultado = app.test_cli_runner().invoke(args=['popular-demo'])
        assert 'Dados de demonstração criados.' in resultado.output
        assert {t.formato for t in Torneio.query} == {Formato.ELIMINATORIA, Formato.GRUPOS, Formato.ROUND_ROBIN}
        assert Jogador.query.count() == 16

    def test_grupos_ja_tem_mata_mata(self, app):
        app.test_cli_runner().invoke(args=['popular-demo'])
        grupos = Torneio.query.filter_by(formato=Formato.GRUPOS).one()
        assert Partida.query.filter_by(torneio_id=grupos.id, rodada=Rodada.F).count() == 1

    def test_tem_partida_ao_vivo(self, app):
        app.test_cli_runner().invoke(args=['popular-demo'])
        assert Partida.query.filter_by(status=StatusPartida.EM_ANDAMENTO).count() == 1

    def test_rodar_duas_vezes_nao_duplica_jogadores(self, app):
        runner = app.test_cli_runner()
        runner.invoke(args=['popular-demo'])
        runner.invoke(args=['popular-demo'])
        assert Jogador.query.count() == 16
        assert Torneio.query.count() == 6


class TestCriarOrganizador:

    def test_cria(self, app):
        resultado = app.test_cli_runner().invoke(args=['criar-organizador', 'Orlando'])
        assert 'Organizador "Orlando" criado.' in resultado.output
        assert Usuario.query.one().nome == 'Orlando'
