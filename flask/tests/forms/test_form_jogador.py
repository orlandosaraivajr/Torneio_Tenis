import io

from werkzeug.datastructures import FileStorage

from torneio.forms import JogadorForm


def make_validated_form(app, **kwargs):
    data = dict(dict(nome='Gustavo Kuerten'), **kwargs)
    with app.test_request_context(method='POST', data=data):
        form = JogadorForm()
        form.validate()
    return form


class TestJogadorForm:

    def test_campos_do_formulario(self, app):
        with app.test_request_context():
            assert [c.name for c in JogadorForm() if c.name != 'csrf_token'] == ['nome', 'foto']

    def test_formulario_valido(self, app):
        assert make_validated_form(app).errors == {}

    def test_nome_obrigatorio(self, app):
        assert 'nome' in make_validated_form(app, nome='').errors

    def test_nome_muito_longo(self, app):
        assert 'nome' in make_validated_form(app, nome='x' * 151).errors

    def test_foto_imagem_aceita(self, app):
        foto = FileStorage(io.BytesIO(b'img'), filename='guga.png')
        assert make_validated_form(app, foto=foto).errors == {}

    def test_foto_com_extensao_invalida(self, app):
        arquivo = FileStorage(io.BytesIO(b'x'), filename='virus.exe')
        assert 'foto' in make_validated_form(app, foto=arquivo).errors
