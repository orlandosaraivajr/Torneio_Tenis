import datetime

import pytest

from torneio import services
from torneio.extensions import db
from torneio.forms import TorneioForm
from torneio.models import Formato, StatusTorneio, Torneio, Usuario
from tests.helpers import criar_torneio


def make_validated_form(app, torneio=None, **kwargs):
    valid = dict(
        nome='Open de Primavera', descricao='', data_torneio='2026-11-01', local='Clube Central',
        formato=Formato.ELIMINATORIA, status=StatusTorneio.RASCUNHO, premiacao='', regulamento='', organizador='None',
    )
    data = dict(valid, **kwargs)
    with app.test_request_context(method='POST', data=data):
        form = TorneioForm(torneio=torneio)
        form.validate()
    return form


def salvar(form, torneio=None):
    torneio = torneio or Torneio()
    form.preencher(torneio)
    db.session.add(torneio)
    db.session.commit()
    return torneio


class TestTorneioForm:

    def test_campos_do_formulario(self, app):
        with app.test_request_context():
            nomes = [campo.name for campo in TorneioForm() if campo.name != 'csrf_token']
        assert nomes == ['nome', 'descricao', 'data_torneio', 'local', 'formato', 'status',
                         'premiacao', 'regulamento', 'regulamento_arquivo', 'organizador']

    def test_formulario_valido(self, app):
        assert make_validated_form(app).errors == {}

    def test_preencher_cria_torneio(self, app):
        torneio = salvar(make_validated_form(app))
        assert torneio.nome == 'Open de Primavera'
        assert torneio.data_torneio == datetime.date(2026, 11, 1)
        assert torneio.organizador_id is None

    @pytest.mark.parametrize('campo', ['nome', 'data_torneio', 'local'])
    def test_campos_obrigatorios(self, app, campo):
        assert campo in make_validated_form(app, **{campo: ''}).errors

    def test_data_invalida(self, app):
        assert 'data_torneio' in make_validated_form(app, data_torneio='31/02/2026').errors

    def test_formato_invalido(self, app):
        assert 'formato' in make_validated_form(app, formato='SUICO').errors

    def test_nome_muito_longo(self, app):
        assert 'nome' in make_validated_form(app, nome='x' * 151).errors

    def test_organizador_existente(self, app):
        usuario = Usuario(nome='Orlando')
        db.session.add(usuario)
        db.session.commit()
        torneio = salvar(make_validated_form(app, organizador=str(usuario.id)))
        assert torneio.organizador == usuario

    def test_opcoes_de_organizador(self, app):
        db.session.add(Usuario(nome='Orlando'))
        db.session.commit()
        with app.test_request_context():
            rotulos = [rotulo for _, rotulo in TorneioForm().organizador.choices]
        assert rotulos == ['Sem organizador', 'Orlando']

    def test_edicao_carrega_dados_do_torneio(self, app):
        torneio = criar_torneio()
        with app.test_request_context():
            form = TorneioForm(torneio=torneio)
        assert form.nome.data == 'Open de Primavera'
        assert form.organizador.data is None

    def test_formato_livre_sem_chave(self, app):
        with app.test_request_context():
            assert not TorneioForm(torneio=criar_torneio(jogadores=2)).formato_bloqueado

    def test_formato_bloqueado_com_chave(self, app):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        with app.test_request_context():
            form = TorneioForm(torneio=torneio)
        assert form.formato_bloqueado
        assert form.formato.render_kw == {'disabled': True}

    def test_formato_bloqueado_ignora_valor_enviado(self, app):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        form = make_validated_form(app, torneio=torneio, formato=Formato.ROUND_ROBIN)
        salvar(form, torneio)
        assert torneio.formato == Formato.ELIMINATORIA

    def test_campos_de_texto_vazios_viram_string_vazia(self, app):
        torneio = salvar(make_validated_form(app))
        assert (torneio.descricao, torneio.premiacao, torneio.regulamento) == ('', '', '')
