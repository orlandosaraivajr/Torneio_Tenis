import io
from http import HTTPStatus

import pytest

from torneio import services
from torneio.extensions import db
from torneio.models import Formato, Partida, StatusTorneio, Torneio
from tests.helpers import criar_torneio, jogar, jogar_todas, partidas


def dados_torneio(**kwargs):
    dados = dict(nome='Open de Primavera', descricao='', data_torneio='2026-11-01', local='Clube Central',
                 formato=Formato.ELIMINATORIA, status=StatusTorneio.RASCUNHO, premiacao='', regulamento='',
                 organizador='None')
    dados.update(kwargs)
    return dados


def html(resposta):
    return resposta.get_data(as_text=True)


class TestTorneioLista:

    def test_lista_todos(self, app, client):
        criar_torneio(nome='Aberto')
        criar_torneio(nome='Cancelado', status=StatusTorneio.CANCELADO)
        resposta = client.get('/torneios/')
        assert resposta.status_code == HTTPStatus.OK
        assert 'Aberto' in html(resposta) and 'Cancelado' in html(resposta)

    def test_filtro_por_status(self, app, client, templates):
        criar_torneio(nome='Torneio Aberto')
        criar_torneio(nome='Torneio Fechado', status=StatusTorneio.CANCELADO)
        client.get('/torneios/?status=CANCELADO')
        assert [t.nome for t in templates[0][1]['torneios']] == ['Torneio Fechado']

    def test_lista_vazia(self, client):
        assert 'Nenhum torneio encontrado.' in html(client.get('/torneios/'))


class TestTorneioNovo:

    def test_get(self, client):
        resposta = client.get('/torneios/novo')
        assert resposta.status_code == HTTPStatus.OK
        assert 'Novo torneio' in html(resposta)
        assert 'enctype="multipart/form-data"' in html(resposta)

    def test_post_valido_cria_e_redireciona(self, app, client):
        resposta = client.post('/torneios/novo', data=dados_torneio())
        torneio = Torneio.query.one()
        assert resposta.status_code == HTTPStatus.FOUND
        assert resposta.location.endswith(f'/torneios/{torneio.id}/')

    def test_post_valido_exibe_mensagem(self, client):
        assert 'Torneio salvo.' in html(client.post('/torneios/novo', data=dados_torneio(), follow_redirects=True))

    def test_post_invalido_nao_salva(self, app, client):
        resposta = client.post('/torneios/novo', data=dados_torneio(nome=''))
        assert resposta.status_code == HTTPStatus.OK
        assert Torneio.query.count() == 0

    def test_upload_do_regulamento(self, app, client):
        dados = dados_torneio(regulamento_arquivo=(io.BytesIO(b'%PDF'), 'regras.pdf'))
        client.post('/torneios/novo', data=dados, content_type='multipart/form-data')
        torneio = Torneio.query.one()
        assert torneio.regulamento_arquivo.startswith('regulamentos/')
        assert torneio.regulamento_arquivo.endswith('regras.pdf')


class TestTorneioEditar:

    def test_get(self, app, client):
        torneio = criar_torneio()
        resposta = client.get(f'/torneios/{torneio.id}/editar')
        assert 'Editar torneio' in html(resposta)
        assert 'value="Open de Primavera"' in html(resposta)

    def test_post_atualiza(self, app, client):
        torneio = criar_torneio()
        client.post(f'/torneios/{torneio.id}/editar', data=dados_torneio(nome='Novo nome'))
        assert db.session.get(Torneio, torneio.id).nome == 'Novo nome'

    def test_torneio_inexistente(self, client):
        assert client.get('/torneios/9999/editar').status_code == HTTPStatus.NOT_FOUND


class TestTorneioExcluir:

    def test_post_exclui(self, app, client):
        torneio = criar_torneio()
        resposta = client.post(f'/torneios/{torneio.id}/excluir')
        assert resposta.location.endswith('/torneios/')
        assert Torneio.query.count() == 0

    def test_get_nao_permitido(self, app, client):
        torneio = criar_torneio()
        assert client.get(f'/torneios/{torneio.id}/excluir').status_code == HTTPStatus.METHOD_NOT_ALLOWED


class TestTorneioDetalhe:

    @pytest.mark.parametrize('aba', ['resumo', 'inscritos', 'chave', 'partidas', 'classificacao', 'xpto'])
    def test_abas_sem_chave(self, app, client, aba):
        torneio = criar_torneio(jogadores=2)
        assert client.get(f'/torneios/{torneio.id}/?aba={aba}').status_code == HTTPStatus.OK

    @pytest.mark.parametrize('formato', [Formato.ELIMINATORIA, Formato.ROUND_ROBIN, Formato.GRUPOS])
    @pytest.mark.parametrize('aba', ['resumo', 'inscritos', 'chave', 'partidas', 'classificacao'])
    def test_abas_com_chave(self, app, client, formato, aba):
        torneio = criar_torneio(formato, jogadores=5)
        services.gerar_chave(torneio)
        assert client.get(f'/torneios/{torneio.id}/?aba={aba}').status_code == HTTPStatus.OK

    def test_torneio_inexistente(self, client):
        assert client.get('/torneios/9999/').status_code == HTTPStatus.NOT_FOUND

    def test_sugere_gerar_chave(self, app, client):
        torneio = criar_torneio(jogadores=2)
        assert f'/torneios/{torneio.id}/gerar-chave' in html(client.get(f'/torneios/{torneio.id}/'))

    def test_sugere_inscrever_com_poucos_jogadores(self, app, client):
        torneio = criar_torneio(jogadores=1)
        assert 'Inscreva pelo menos 2 jogadores' in html(client.get(f'/torneios/{torneio.id}/'))

    def test_formulario_de_inscricao(self, app, client):
        torneio = criar_torneio()
        assert 'name="novo_jogador"' in html(client.get(f'/torneios/{torneio.id}/?aba=inscritos'))

    def test_sem_formulario_depois_da_chave(self, app, client):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        pagina = html(client.get(f'/torneios/{torneio.id}/?aba=inscritos'))
        assert 'name="novo_jogador"' not in pagina
        assert 'as inscrições estão encerradas' in pagina

    def test_exibe_campeao(self, app, client):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        jogar(partidas(torneio).one())
        pagina = html(client.get(f'/torneios/{torneio.id}/'))
        assert 'Campeão' in pagina
        assert 'parabéns, <b>Jogador 01</b>' in pagina

    def test_chave_eliminatoria(self, app, client):
        torneio = criar_torneio(jogadores=8)
        services.gerar_chave(torneio)
        pagina = html(client.get(f'/torneios/{torneio.id}/?aba=chave'))
        for rodada in ['Quartas de final', 'Semifinal', 'Final', 'Campeão']:
            assert rodada in pagina

    def test_round_robin_exibe_rodadas(self, app, client):
        torneio = criar_torneio(Formato.ROUND_ROBIN, jogadores=4)
        services.gerar_chave(torneio)
        assert 'Rodada 3' in html(client.get(f'/torneios/{torneio.id}/?aba=chave'))

    def test_grupos_concluidos_oferece_mata_mata(self, app, client):
        torneio = criar_torneio(Formato.GRUPOS, jogadores=8)
        services.gerar_chave(torneio)
        jogar_todas(torneio)
        pagina = html(client.get(f'/torneios/{torneio.id}/?aba=chave'))
        assert 'Grupo A' in pagina and 'Grupo B' in pagina
        assert f'/torneios/{torneio.id}/gerar-mata-mata' in pagina

    def test_progresso(self, app, client):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        jogar(partidas(torneio, rodada='SF').first())
        assert '1 de 3 partidas encerradas' in html(client.get(f'/torneios/{torneio.id}/'))


class TestInscrever:

    def test_inscreve_novo_jogador(self, app, client):
        torneio = criar_torneio()
        resposta = client.post(f'/torneios/{torneio.id}/inscrever', data={'novo_jogador': 'Guga'})
        assert resposta.location.endswith(f'/torneios/{torneio.id}/?aba=inscritos')
        assert [i.jogador.nome for i in db.session.get(Torneio, torneio.id).inscricoes] == ['Guga']

    def test_mensagem_de_sucesso(self, app, client):
        torneio = criar_torneio()
        resposta = client.post(f'/torneios/{torneio.id}/inscrever', data={'novo_jogador': 'Guga'}, follow_redirects=True)
        assert 'Guga inscrito(a).' in html(resposta)

    def test_dados_invalidos(self, app, client):
        torneio = criar_torneio()
        resposta = client.post(f'/torneios/{torneio.id}/inscrever', data={}, follow_redirects=True)
        assert 'Escolha um jogador ou informe o nome de um novo.' in html(resposta)

    def test_torneio_fechado(self, app, client):
        torneio = criar_torneio(status=StatusTorneio.EM_ANDAMENTO)
        resposta = client.post(f'/torneios/{torneio.id}/inscrever', data={'novo_jogador': 'Guga'}, follow_redirects=True)
        assert 'Este torneio não aceita mais inscrições.' in html(resposta)

    def test_get_nao_permitido(self, app, client):
        torneio = criar_torneio()
        assert client.get(f'/torneios/{torneio.id}/inscrever').status_code == HTTPStatus.METHOD_NOT_ALLOWED


class TestRemoverInscricao:

    def test_remove(self, app, client):
        torneio = criar_torneio(jogadores=2)
        inscricao = torneio.inscritos[0]
        resposta = client.post(f'/inscricoes/{inscricao.id}/remover', follow_redirects=True)
        assert 'removido(a) do torneio' in html(resposta)
        assert len(db.session.get(Torneio, torneio.id).inscricoes) == 1

    def test_nao_remove_depois_da_chave(self, app, client):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        inscricao = torneio.inscritos[0]
        resposta = client.post(f'/inscricoes/{inscricao.id}/remover', follow_redirects=True)
        assert 'Não é possível remover inscritos depois de gerada a chave.' in html(resposta)

    def test_inscricao_inexistente(self, client):
        assert client.post('/inscricoes/9999/remover').status_code == HTTPStatus.NOT_FOUND


class TestFluxoDaChave:

    def test_gerar_chave(self, app, client):
        torneio = criar_torneio(jogadores=4)
        resposta = client.post(f'/torneios/{torneio.id}/gerar-chave', follow_redirects=True)
        assert 'Chave gerada! Bons jogos.' in html(resposta)
        assert Partida.query.count() == 3

    def test_erro_de_regra_vira_mensagem(self, app, client):
        torneio = criar_torneio(jogadores=1)
        resposta = client.post(f'/torneios/{torneio.id}/gerar-chave', follow_redirects=True)
        assert 'São necessários pelo menos 2 jogadores' in html(resposta)
        assert Partida.query.count() == 0

    def test_gerar_mata_mata_com_grupos_incompletos(self, app, client):
        torneio = criar_torneio(Formato.GRUPOS, jogadores=8)
        services.gerar_chave(torneio)
        resposta = client.post(f'/torneios/{torneio.id}/gerar-mata-mata', follow_redirects=True)
        assert 'Finalize todas as partidas da fase de grupos' in html(resposta)

    def test_gerar_mata_mata(self, app, client):
        torneio = criar_torneio(Formato.GRUPOS, jogadores=8)
        services.gerar_chave(torneio)
        jogar_todas(torneio)
        resposta = client.post(f'/torneios/{torneio.id}/gerar-mata-mata', follow_redirects=True)
        assert 'Mata-mata gerado com os classificados.' in html(resposta)
        assert partidas(torneio, rodada='F').count() == 1

    def test_refazer_chave(self, app, client):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        resposta = client.post(f'/torneios/{torneio.id}/refazer-chave')
        assert resposta.location.endswith('aba=inscritos')
        assert Partida.query.count() == 0
        assert db.session.get(Torneio, torneio.id).status == StatusTorneio.INSCRICOES
