import os
from http import HTTPStatus

from torneio import services
from torneio.models import StatusPartida, StatusTorneio
from tests.helpers import criar_jogador, criar_torneio, jogar, partidas


class TestPlacarVazio:

    def test_status_code(self, client):
        assert client.get('/').status_code == HTTPStatus.OK

    def test_sem_partidas(self, client):
        assert 'Nenhuma partida ainda' in client.get('/').get_data(as_text=True)

    def test_caixa_de_busca(self, client):
        assert 'name="q"' in client.get('/').get_data(as_text=True)

    def test_links_de_cadastro(self, client):
        html = client.get('/').get_data(as_text=True)
        assert '/torneios/novo' in html
        assert '/jogadores/novo' in html


class TestPlacarComJogos:

    def preparar(self):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        semi_1, semi_2 = partidas(torneio, rodada='SF').all()
        jogar(semi_1)
        services.registrar_resultado(semi_2, StatusPartida.EM_ANDAMENTO, '6-4 2-1', None, None)
        return torneio

    def test_lista_partidas_por_torneio(self, app, client):
        self.preparar()
        html = client.get('/').get_data(as_text=True)
        assert 'Open de Primavera' in html
        assert 'Semifinal' in html

    def test_indicador_ao_vivo(self, app, client):
        self.preparar()
        html = client.get('/').get_data(as_text=True)
        assert 'AO VIVO' in html
        assert 'vivo-badge' in html

    def test_filtro_ao_vivo(self, app, client):
        self.preparar()
        html = client.get('/?filtro=ao-vivo').get_data(as_text=True)
        assert 'AO VIVO' in html
        assert 'Enc.' not in html

    def test_filtro_encerrados(self, app, client):
        self.preparar()
        html = client.get('/?filtro=encerrados').get_data(as_text=True)
        assert 'Enc.' in html
        assert '>AO VIVO<' not in html

    def test_filtro_agendados_vazio(self, app, client):
        self.preparar()
        assert 'Nenhuma partida neste filtro.' in client.get('/?filtro=agendados').get_data(as_text=True)

    def test_filtro_ao_vivo_vazio(self, app, client):
        assert 'Nenhuma partida ao vivo' in client.get('/?filtro=ao-vivo').get_data(as_text=True)

    def test_filtro_invalido_vira_todos(self, app, client):
        self.preparar()
        assert 'Semifinal' in client.get('/?filtro=xpto').get_data(as_text=True)

    def test_partidas_de_torneio_cancelado_nao_aparecem(self, app, client):
        torneio = self.preparar()
        torneio.status = StatusTorneio.CANCELADO
        from torneio.extensions import db
        db.session.commit()
        assert 'Semifinal' not in client.get('/').get_data(as_text=True)


class TestBusca:

    def preparar(self):
        criar_torneio(nome='Open de Primavera', local='Clube Pinheiros')
        criar_torneio(nome='Copa de Inverno', local='Clube Central', descricao='Aberto a todos.')
        criar_jogador('Gustavo Kuerten')

    def buscar(self, client, templates, termo):
        client.get('/', query_string={'q': termo})
        template, contexto = templates[0]
        assert template.name == 'busca.html'
        return contexto

    def test_busca_por_nome(self, app, client, templates):
        self.preparar()
        assert [t.nome for t in self.buscar(client, templates, 'primavera')['torneios']] == ['Open de Primavera']

    def test_busca_por_local(self, app, client, templates):
        self.preparar()
        assert [t.nome for t in self.buscar(client, templates, 'pinheiros')['torneios']] == ['Open de Primavera']

    def test_busca_por_descricao(self, app, client, templates):
        self.preparar()
        assert [t.nome for t in self.buscar(client, templates, 'aberto a todos')['torneios']] == ['Copa de Inverno']

    def test_busca_por_jogador(self, app, client, templates):
        self.preparar()
        contexto = self.buscar(client, templates, 'kuerten')
        assert [j.nome for j in contexto['jogadores']] == ['Gustavo Kuerten']
        assert contexto['torneios'] == []

    def test_total(self, app, client):
        self.preparar()
        assert '2 resultado(s)' in client.get('/?q=clube').get_data(as_text=True)

    def test_sem_resultados(self, app, client):
        assert 'Nenhum torneio ou jogador encontrado' in client.get('/?q=xyz').get_data(as_text=True)

    def test_termo_preenchido_na_busca(self, app, client):
        assert 'value="primavera"' in client.get('/?q=primavera').get_data(as_text=True)

    def test_termo_so_com_espacos_volta_ao_placar(self, app, client):
        assert 'Busca:' not in client.get('/?q=+++').get_data(as_text=True)


class TestUploads:

    def test_serve_arquivo_enviado(self, app, client):
        pasta = os.path.join(app.config['UPLOAD_FOLDER'], 'jogadores')
        os.makedirs(pasta)
        with open(os.path.join(pasta, 'foto.png'), 'wb') as arquivo:
            arquivo.write(b'conteudo')
        resposta = client.get('/uploads/jogadores/foto.png')
        assert resposta.status_code == HTTPStatus.OK
        assert resposta.data == b'conteudo'
        resposta.close()

    def test_arquivo_inexistente(self, client):
        assert client.get('/uploads/nada.png').status_code == HTTPStatus.NOT_FOUND


class TestAdmin:

    def test_painel(self, client):
        assert client.get('/admin/').status_code == HTTPStatus.OK

    def test_lista_torneios(self, app, client):
        criar_torneio()
        resposta = client.get('/admin/torneio/')
        assert resposta.status_code == HTTPStatus.OK
        assert 'Open de Primavera' in resposta.get_data(as_text=True)

    def test_cadastra_jogador_pelo_admin(self, app, client):
        assert client.get('/admin/jogador/new/').status_code == HTTPStatus.OK
        client.post('/admin/jogador/new/', data={'nome': 'Guga', 'foto': ''})
        from torneio.models import Jogador
        assert Jogador.query.one().nome == 'Guga'
