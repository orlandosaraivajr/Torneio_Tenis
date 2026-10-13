import pytest

from torneio.extensions import db
from torneio.forms import InscricaoForm
from torneio.models import Inscricao, Jogador
from tests.helpers import criar_jogador, criar_torneio


@pytest.fixture
def torneio(app):
    return criar_torneio()


@pytest.fixture
def jogador(app):
    return criar_jogador()


def make_validated_form(app, torneio, **kwargs):
    with app.test_request_context(method='POST', data=kwargs):
        form = InscricaoForm(torneio)
        form.validate()
    return form


def inscrever(torneio, jogador, semente=None):
    db.session.add(Inscricao(torneio=torneio, jogador=jogador, cabeca_de_chave=semente))
    db.session.commit()


class TestInscricaoForm:

    def test_campos_do_formulario(self, app, torneio):
        with app.test_request_context():
            nomes = [c.name for c in InscricaoForm(torneio) if c.name != 'csrf_token']
        assert nomes == ['jogador', 'novo_jogador', 'cabeca_de_chave']

    def test_inscrever_jogador_existente(self, app, torneio, jogador):
        form = make_validated_form(app, torneio, jogador=str(jogador.id))
        assert form.errors == {}
        inscricao = form.criar_inscricao()
        assert inscricao.jogador == jogador
        assert inscricao.torneio == torneio

    def test_inscrever_novo_jogador(self, app, torneio):
        form = make_validated_form(app, torneio, novo_jogador='  Fernando Meligeni  ')
        inscricao = form.criar_inscricao()
        db.session.commit()
        assert inscricao.jogador.nome == 'Fernando Meligeni'
        assert Jogador.query.count() == 1

    def test_jogador_existente_tem_prioridade(self, app, torneio, jogador):
        form = make_validated_form(app, torneio, jogador=str(jogador.id), novo_jogador='Outro')
        assert form.criar_inscricao().jogador == jogador

    def test_sem_jogador_e_sem_nome(self, app, torneio):
        form = make_validated_form(app, torneio)
        assert 'Escolha um jogador ou informe o nome de um novo.' in form.form_errors

    def test_nome_so_com_espacos(self, app, torneio):
        assert make_validated_form(app, torneio, novo_jogador='   ').form_errors

    def test_cabeca_de_chave(self, app, torneio):
        form = make_validated_form(app, torneio, novo_jogador='Guga', cabeca_de_chave='1')
        assert form.criar_inscricao().cabeca_de_chave == 1

    def test_cabeca_de_chave_repetido(self, app, torneio, jogador):
        inscrever(torneio, jogador, semente=1)
        form = make_validated_form(app, torneio, novo_jogador='Guga', cabeca_de_chave='1')
        assert 'Já existe um cabeça de chave nº 1.' in form.errors['cabeca_de_chave']

    def test_cabeca_de_chave_zero(self, app, torneio):
        form = make_validated_form(app, torneio, novo_jogador='Guga', cabeca_de_chave='0')
        assert 'cabeca_de_chave' in form.errors

    def test_lista_exclui_jogadores_ja_inscritos(self, app, torneio, jogador):
        inscrever(torneio, jogador)
        livre = criar_jogador('Livre')
        with app.test_request_context():
            opcoes = InscricaoForm(torneio).jogador.choices
        assert opcoes == [(None, 'Selecione um jogador cadastrado'), (livre.id, 'Livre')]

    def test_jogador_ja_inscrito_e_invalido(self, app, torneio, jogador):
        inscrever(torneio, jogador)
        assert 'jogador' in make_validated_form(app, torneio, jogador=str(jogador.id)).errors

    def test_inscrito_em_outro_torneio_aparece(self, app, torneio, jogador):
        inscrever(criar_torneio(nome='Outro'), jogador)
        with app.test_request_context():
            ids = [valor for valor, _ in InscricaoForm(torneio).jogador.choices]
        assert jogador.id in ids
