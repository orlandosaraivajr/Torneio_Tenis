import io
from http import HTTPStatus

from torneio import services
from torneio.extensions import db
from torneio.models import Inscricao, Jogador
from tests.helpers import criar_jogador, criar_torneio, jogar, partidas


def html(resposta):
    return resposta.get_data(as_text=True)


class TestJogadorLista:

    def test_lista(self, app, client):
        criar_jogador('Gustavo Kuerten')
        criar_jogador('Fernando Meligeni')
        pagina = html(client.get('/jogadores/'))
        assert 'Gustavo Kuerten' in pagina and 'Fernando Meligeni' in pagina

    def test_filtro(self, app, client):
        criar_jogador('Gustavo Kuerten')
        criar_jogador('Fernando Meligeni')
        pagina = html(client.get('/jogadores/?q=kuerten'))
        assert 'Gustavo Kuerten' in pagina
        assert 'Fernando Meligeni' not in pagina

    def test_vazia(self, client):
        assert 'Nenhum jogador encontrado.' in html(client.get('/jogadores/'))

    def test_template(self, client, templates):
        client.get('/jogadores/')
        assert templates[0][0].name == 'jogadores/lista.html'

    def test_estatisticas_ignoram_bye(self, app, client, templates):
        torneio = criar_torneio(jogadores=3)
        services.gerar_chave(torneio)  # cabeça 1 recebe BYE
        jogar(partidas(torneio, rodada='SF', placar='').one())
        jogar(partidas(torneio, rodada='F').one())
        client.get('/jogadores/')
        linhas = templates[0][1]['linhas']
        campeao = next(l for l in linhas if l['jogador'].nome == 'Jogador 01')
        assert campeao['torneios'] == 1
        assert campeao['vitorias'] == 1  # só a final; o BYE não conta


class TestJogadorNovo:

    def test_get(self, client):
        assert 'Novo jogador' in html(client.get('/jogadores/novo'))

    def test_post_valido(self, app, client):
        resposta = client.post('/jogadores/novo', data={'nome': 'Gustavo Kuerten'})
        jogador = Jogador.query.one()
        assert resposta.location.endswith(f'/jogadores/{jogador.id}/')

    def test_post_invalido(self, app, client):
        resposta = client.post('/jogadores/novo', data={'nome': ''})
        assert resposta.status_code == HTTPStatus.OK
        assert Jogador.query.count() == 0

    def test_upload_de_foto(self, app, client):
        client.post('/jogadores/novo', data={'nome': 'Guga', 'foto': (io.BytesIO(b'img'), 'guga.png')},
                    content_type='multipart/form-data')
        jogador = Jogador.query.one()
        assert jogador.foto.startswith('jogadores/')
        assert f'/uploads/{jogador.foto}' in html(client.get(f'/jogadores/{jogador.id}/'))


class TestJogadorEditar:

    def test_get(self, app, client):
        jogador = criar_jogador('Guga')
        pagina = html(client.get(f'/jogadores/{jogador.id}/editar'))
        assert 'Editar jogador' in pagina
        assert 'value="Guga"' in pagina

    def test_post_atualiza(self, app, client):
        jogador = criar_jogador('Guga')
        client.post(f'/jogadores/{jogador.id}/editar', data={'nome': 'Gustavo Kuerten'})
        assert db.session.get(Jogador, jogador.id).nome == 'Gustavo Kuerten'

    def test_inexistente(self, client):
        assert client.get('/jogadores/9999/editar').status_code == HTTPStatus.NOT_FOUND


class TestJogadorExcluir:

    def test_exclui_sem_partidas(self, app, client):
        jogador = criar_jogador()
        resposta = client.post(f'/jogadores/{jogador.id}/excluir')
        assert resposta.location.endswith('/jogadores/')
        assert Jogador.query.count() == 0

    def test_exclui_apenas_inscrito(self, app, client):
        jogador = criar_jogador()
        db.session.add(Inscricao(torneio=criar_torneio(), jogador=jogador))
        db.session.commit()
        client.post(f'/jogadores/{jogador.id}/excluir')
        assert Jogador.query.count() == 0

    def test_nao_exclui_com_partidas(self, app, client):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        jogador = torneio.inscritos[0].jogador
        resposta = client.post(f'/jogadores/{jogador.id}/excluir', follow_redirects=True)
        assert 'já disputou partidas e não pode ser excluído' in html(resposta)
        assert db.session.get(Jogador, jogador.id) is not None

    def test_get_nao_permitido(self, app, client):
        jogador = criar_jogador()
        assert client.get(f'/jogadores/{jogador.id}/excluir').status_code == HTTPStatus.METHOD_NOT_ALLOWED


class TestJogadorDetalhe:

    def preparar(self):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        for semi in partidas(torneio, rodada='SF').all():
            jogar(semi)
        final = partidas(torneio, rodada='F').one()
        jogar(final, vence_1=False)
        return torneio, final

    def test_campeao(self, app, client, templates):
        torneio, final = self.preparar()
        pagina = html(client.get(f'/jogadores/{final.inscricao_2.jogador_id}/'))
        contexto = templates[0][1]
        assert (contexto['vitorias'], contexto['derrotas']) == (2, 0)
        assert len(contexto['partidas']) == 2
        assert torneio.nome in pagina

    def test_vice(self, app, client, templates):
        _, final = self.preparar()
        client.get(f'/jogadores/{final.inscricao_1.jogador_id}/')
        assert (templates[0][1]['vitorias'], templates[0][1]['derrotas']) == (1, 1)

    def test_partidas_bye_nao_aparecem(self, app, client, templates):
        torneio = criar_torneio(nome='Com bye', jogadores=3)
        services.gerar_chave(torneio)
        cabeca = next(i for i in torneio.inscritos if i.cabeca_de_chave == 1)
        client.get(f'/jogadores/{cabeca.jogador_id}/')
        # O cabeça 1 avança direto: só a final (ainda agendada) aparece no histórico.
        assert [p.rodada for p in templates[0][1]['partidas']] == ['F']

    def test_sem_torneios(self, app, client):
        jogador = criar_jogador('Novato')
        pagina = html(client.get(f'/jogadores/{jogador.id}/'))
        assert 'Ainda não se inscreveu em nenhum torneio.' in pagina
        assert 'Nenhuma partida disputada.' in pagina

    def test_inexistente(self, client):
        assert client.get('/jogadores/9999/').status_code == HTTPStatus.NOT_FOUND
