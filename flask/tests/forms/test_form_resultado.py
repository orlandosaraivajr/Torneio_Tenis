import datetime

import pytest

from torneio.extensions import db
from torneio.forms import ResultadoForm
from torneio.models import Partida, Rodada, StatusPartida
from tests.helpers import criar_torneio


@pytest.fixture
def partida(app):
    torneio = criar_torneio(jogadores=2)
    ins_1, ins_2 = torneio.inscritos
    partida = Partida(torneio=torneio, rodada=Rodada.F, inscricao_1=ins_1, inscricao_2=ins_2)
    db.session.add(partida)
    db.session.commit()
    return partida


def make_validated_form(app, partida, **kwargs):
    valid = dict(status=StatusPartida.FINALIZADA, placar='6-4 6-3', vencedor='', data_hora='')
    data = dict(valid, **kwargs)
    with app.test_request_context(method='POST', data=data):
        form = ResultadoForm(partida)
        form.validate()
    return form


class TestResultadoForm:

    def test_campos_do_formulario(self, app, partida):
        with app.test_request_context():
            nomes = [c.name for c in ResultadoForm(partida) if c.name != 'csrf_token']
        assert nomes == ['data_hora', 'status', 'placar', 'vencedor']

    def test_opcoes_de_vencedor(self, app, partida):
        with app.test_request_context():
            opcoes = ResultadoForm(partida).vencedor.choices
        assert opcoes == [(None, 'Pelo placar'), (partida.inscricao_1_id, 'Jogador 01'),
                          (partida.inscricao_2_id, 'Jogador 02')]

    def test_opcoes_sem_jogadores(self, app, partida):
        vazia = Partida(torneio=partida.torneio, rodada=Rodada.SF)
        with app.test_request_context():
            assert ResultadoForm(vazia).vencedor.choices == [(None, 'Pelo placar')]

    def test_valores_iniciais_vem_da_partida(self, app, partida):
        partida.placar, partida.status, partida.vencedor = '6-0 6-0', StatusPartida.FINALIZADA, partida.inscricao_1
        db.session.commit()
        with app.test_request_context():
            form = ResultadoForm(partida)
        assert form.placar.data == '6-0 6-0'
        assert form.status.data == StatusPartida.FINALIZADA
        assert form.vencedor.data == partida.inscricao_1_id

    def test_vencedor_calculado_pelo_placar(self, app, partida):
        form = make_validated_form(app, partida, placar='4-6 6-3 10-7')
        assert form.errors == {}
        assert form.vencedor_obj == partida.inscricao_1

    def test_vencedor_jogador_2(self, app, partida):
        assert make_validated_form(app, partida, placar='3-6 4-6').vencedor_obj == partida.inscricao_2

    def test_vencedor_escolhido_confere(self, app, partida):
        form = make_validated_form(app, partida, vencedor=str(partida.inscricao_1_id))
        assert form.errors == {}
        assert form.vencedor_obj == partida.inscricao_1

    def test_vencedor_escolhido_diferente_do_placar(self, app, partida):
        form = make_validated_form(app, partida, vencedor=str(partida.inscricao_2_id))
        assert 'O vencedor escolhido não confere com o placar.' in form.errors['vencedor']

    @pytest.mark.parametrize('valor', ['9999', 'abc'])
    def test_vencedor_invalido(self, app, partida, valor):
        assert 'vencedor' in make_validated_form(app, partida, vencedor=valor).errors

    def test_placar_empatado_sem_vencedor(self, app, partida):
        assert 'vencedor' in make_validated_form(app, partida, placar='6-4 4-6').errors

    def test_placar_invalido(self, app, partida):
        assert 'placar' in make_validated_form(app, partida, placar='seis a quatro').errors

    def test_placar_normaliza_espacos(self, app, partida):
        assert make_validated_form(app, partida, placar='  6-4    6-3 ').placar.data == '6-4 6-3'

    def test_finalizada_exige_placar(self, app, partida):
        form = make_validated_form(app, partida, placar='', vencedor=str(partida.inscricao_1_id))
        assert 'Informe o placar de uma partida finalizada.' in form.errors['placar']

    def test_wo_sem_placar_com_vencedor(self, app, partida):
        form = make_validated_form(app, partida, status=StatusPartida.WO, placar='', vencedor=str(partida.inscricao_2_id))
        assert form.errors == {}
        assert form.vencedor_obj == partida.inscricao_2

    def test_wo_sem_vencedor(self, app, partida):
        assert 'vencedor' in make_validated_form(app, partida, status=StatusPartida.WO, placar='').errors

    def test_abandono_aceita_vencedor_atras_no_placar(self, app, partida):
        form = make_validated_form(app, partida, status=StatusPartida.ABANDONO, placar='6-2 1-0',
                                   vencedor=str(partida.inscricao_2_id))
        assert form.errors == {}

    def test_agendada_nao_define_vencedor(self, app, partida):
        form = make_validated_form(app, partida, status=StatusPartida.AGENDADA, placar='',
                                   vencedor=str(partida.inscricao_1_id))
        assert form.errors == {}
        assert form.vencedor_obj is None

    def test_em_andamento_com_placar_parcial(self, app, partida):
        form = make_validated_form(app, partida, status=StatusPartida.EM_ANDAMENTO, placar='6-4 2-3')
        assert form.errors == {}
        assert form.vencedor_obj is None

    def test_finalizar_sem_os_dois_jogadores(self, app, partida):
        incompleta = Partida(torneio=partida.torneio, rodada=Rodada.SF, inscricao_1=partida.inscricao_1)
        db.session.add(incompleta)
        db.session.commit()
        form = make_validated_form(app, incompleta)
        assert 'A partida ainda não tem os dois jogadores definidos.' in form.form_errors

    def test_data_hora(self, app, partida):
        form = make_validated_form(app, partida, status=StatusPartida.AGENDADA, placar='', data_hora='2026-11-01T14:30')
        assert form.data_hora.data == datetime.datetime(2026, 11, 1, 14, 30)

    def test_data_hora_invalida(self, app, partida):
        assert 'data_hora' in make_validated_form(app, partida, data_hora='01/11/2026 14h').errors

    def test_status_invalido(self, app, partida):
        assert 'status' in make_validated_form(app, partida, status='ADIADA').errors
