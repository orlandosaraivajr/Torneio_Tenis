import datetime

from django.test import TestCase

from torneios.forms import ResultadoForm
from torneios.models import Partida
from torneios.tests.helpers import criar_torneio


class ResultadoFormTest(TestCase):

    def setUp(self):
        torneio = criar_torneio(jogadores=2)
        self.ins_1, self.ins_2 = torneio.inscricoes.all()
        self.partida = Partida.objects.create(
            torneio=torneio, rodada=Partida.Rodada.F, inscricao_1=self.ins_1, inscricao_2=self.ins_2
        )

    def make_validated_form(self, partida=None, **kwargs):
        valid = dict(status=Partida.Status.FINALIZADA, placar='6-4 6-3', vencedor='', data_hora='')
        data = dict(valid, **kwargs)
        form = ResultadoForm(partida or self.partida, data)
        form.is_valid()
        return form

    def test_campos_do_formulario(self):
        self.assertSequenceEqual(
            ['data_hora', 'status', 'placar', 'vencedor'],
            list(ResultadoForm(self.partida).fields)
        )

    def test_opcoes_de_vencedor(self):
        opcoes = ResultadoForm(self.partida).fields['vencedor'].choices
        self.assertEqual(opcoes, [
            ('', 'Pelo placar'),
            (str(self.ins_1.pk), 'Jogador 01'),
            (str(self.ins_2.pk), 'Jogador 02'),
        ])

    def test_opcoes_sem_jogadores_definidos(self):
        vazia = Partida.objects.create(torneio=self.partida.torneio, rodada=Partida.Rodada.SF)
        self.assertEqual(ResultadoForm(vazia).fields['vencedor'].choices, [('', 'Pelo placar')])

    def test_valores_iniciais_vem_da_partida(self):
        self.partida.placar = '6-0 6-0'
        self.partida.status = Partida.Status.FINALIZADA
        self.partida.vencedor = self.ins_1
        form = ResultadoForm(self.partida)
        self.assertEqual(form.initial['placar'], '6-0 6-0')
        self.assertEqual(form.initial['status'], Partida.Status.FINALIZADA)
        self.assertEqual(form.initial['vencedor'], self.ins_1.pk)

    def test_vencedor_calculado_pelo_placar(self):
        form = self.make_validated_form(placar='4-6 6-3 10-7')
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['vencedor_obj'], self.ins_1)

    def test_vencedor_jogador_2_pelo_placar(self):
        form = self.make_validated_form(placar='3-6 4-6')
        self.assertEqual(form.cleaned_data['vencedor_obj'], self.ins_2)

    def test_vencedor_escolhido_confere_com_placar(self):
        form = self.make_validated_form(vencedor=str(self.ins_1.pk))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['vencedor_obj'], self.ins_1)

    def test_vencedor_escolhido_diferente_do_placar(self):
        form = self.make_validated_form(vencedor=str(self.ins_2.pk))
        self.assertIn('O vencedor escolhido não confere com o placar.', form.errors['vencedor'])

    def test_vencedor_inexistente(self):
        form = self.make_validated_form(vencedor='9999')
        self.assertIn('vencedor', form.errors)

    def test_placar_empatado_sem_vencedor(self):
        form = self.make_validated_form(placar='6-4 4-6')
        self.assertIn('vencedor', form.errors)

    def test_placar_invalido(self):
        form = self.make_validated_form(placar='seis a quatro')
        self.assertIn('placar', form.errors)

    def test_placar_normaliza_espacos(self):
        form = self.make_validated_form(placar='  6-4    6-3 ')
        self.assertEqual(form.cleaned_data['placar'], '6-4 6-3')

    def test_finalizada_exige_placar(self):
        form = self.make_validated_form(placar='', vencedor=str(self.ins_1.pk))
        self.assertIn('Informe o placar de uma partida finalizada.', form.errors['placar'])

    def test_wo_sem_placar_com_vencedor(self):
        form = self.make_validated_form(status=Partida.Status.WO, placar='', vencedor=str(self.ins_2.pk))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['vencedor_obj'], self.ins_2)

    def test_wo_sem_vencedor(self):
        form = self.make_validated_form(status=Partida.Status.WO, placar='')
        self.assertIn('vencedor', form.errors)

    def test_abandono_aceita_vencedor_atras_no_placar(self):
        form = self.make_validated_form(status=Partida.Status.ABANDONO, placar='6-2 1-0', vencedor=str(self.ins_2.pk))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['vencedor_obj'], self.ins_2)

    def test_agendada_nao_define_vencedor(self):
        form = self.make_validated_form(status=Partida.Status.AGENDADA, placar='', vencedor=str(self.ins_1.pk))
        self.assertTrue(form.is_valid())
        self.assertIsNone(form.cleaned_data['vencedor_obj'])

    def test_em_andamento_com_placar_parcial(self):
        form = self.make_validated_form(status=Partida.Status.EM_ANDAMENTO, placar='6-4 2-3')
        self.assertTrue(form.is_valid())
        self.assertIsNone(form.cleaned_data['vencedor_obj'])

    def test_finalizar_sem_os_dois_jogadores(self):
        incompleta = Partida.objects.create(
            torneio=self.partida.torneio, rodada=Partida.Rodada.SF, inscricao_1=self.ins_1
        )
        form = self.make_validated_form(partida=incompleta)
        self.assertIn('A partida ainda não tem os dois jogadores definidos.', form.non_field_errors())

    def test_data_hora(self):
        form = self.make_validated_form(status=Partida.Status.AGENDADA, placar='', data_hora='2026-11-01T14:30')
        self.assertEqual(form.cleaned_data['data_hora'].replace(tzinfo=None), datetime.datetime(2026, 11, 1, 14, 30))

    def test_data_hora_invalida(self):
        form = self.make_validated_form(data_hora='01/11/2026 14h')
        self.assertIn('data_hora', form.errors)

    def test_status_invalido(self):
        form = self.make_validated_form(status='ADIADA')
        self.assertIn('status', form.errors)
