from http import HTTPStatus

from django.test import TestCase
from django.urls import reverse

from torneios import services
from torneios.forms import ResultadoForm
from torneios.models import Partida, Torneio
from torneios.tests.helpers import criar_torneio, jogar


class PartidaResultadoGetTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio(jogadores=2)
        services.gerar_chave(self.torneio)
        self.partida = self.torneio.partidas.get()
        self.resp = self.client.get(reverse('partida_resultado', args=[self.partida.pk]))

    def test_status_code(self):
        self.assertEqual(self.resp.status_code, HTTPStatus.OK)

    def test_template(self):
        self.assertTemplateUsed(self.resp, 'torneios/partida_form.html')

    def test_formulario_no_contexto(self):
        self.assertIsInstance(self.resp.context['form'], ResultadoForm)

    def test_exibe_confronto(self):
        self.assertContains(self.resp, 'Jogador 01')
        self.assertContains(self.resp, 'Jogador 02')

    def test_voltar_padrao_e_chave(self):
        self.assertEqual(self.resp.context['destino'], f'{self.torneio.get_absolute_url()}?aba=chave')

    def test_voltar_para_aba_partidas(self):
        resp = self.client.get(reverse('partida_resultado', args=[self.partida.pk]), {'voltar': 'partidas'})
        self.assertEqual(resp.context['destino'], f'{self.torneio.get_absolute_url()}?aba=partidas')

    def test_voltar_invalido_usa_chave(self):
        resp = self.client.get(reverse('partida_resultado', args=[self.partida.pk]), {'voltar': 'https://evil.com'})
        self.assertEqual(resp.context['destino'], f'{self.torneio.get_absolute_url()}?aba=chave')

    def test_partida_inexistente(self):
        resp = self.client.get(reverse('partida_resultado', args=[9999]))
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)


class PartidaResultadoPostTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio(jogadores=4)
        services.gerar_chave(self.torneio)
        self.semi = self.torneio.partidas.filter(rodada=Partida.Rodada.SF).order_by('posicao').first()
        self.url = reverse('partida_resultado', args=[self.semi.pk])

    def post(self, **kwargs):
        dados = dict(status='FINALIZADA', placar='6-4 6-3', vencedor='', data_hora='', voltar='chave')
        dados.update(kwargs)
        return self.client.post(self.url, dados)

    def test_post_valido_redireciona(self):
        self.assertRedirects(self.post(), f'{self.torneio.get_absolute_url()}?aba=chave')

    def test_post_valido_salva_resultado(self):
        self.post()
        self.semi.refresh_from_db()
        self.assertEqual(self.semi.status, Partida.Status.FINALIZADA)
        self.assertEqual(self.semi.placar, '6-4 6-3')
        self.assertEqual(self.semi.vencedor, self.semi.inscricao_1)

    def test_vencedor_avanca_para_final(self):
        self.post()
        final = self.torneio.partidas.get(rodada=Partida.Rodada.F)
        self.assertEqual(final.inscricao_1, self.semi.inscricao_1)

    def test_volta_para_aba_partidas(self):
        resp = self.post(voltar='partidas')
        self.assertRedirects(resp, f'{self.torneio.get_absolute_url()}?aba=partidas')

    def test_post_invalido_reexibe_formulario(self):
        resp = self.post(placar='seis a quatro')
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertTrue(resp.context['form'].errors)
        self.semi.refresh_from_db()
        self.assertEqual(self.semi.status, Partida.Status.AGENDADA)

    def test_agendar_horario(self):
        self.post(status='AGENDADA', placar='', data_hora='2026-11-01T14:30')
        self.semi.refresh_from_db()
        self.assertIsNotNone(self.semi.data_hora)
        self.assertIsNone(self.semi.vencedor)

    def test_finalizar_torneio(self):
        for semi in self.torneio.partidas.filter(rodada=Partida.Rodada.SF):
            jogar(semi)
        final = self.torneio.partidas.get(rodada=Partida.Rodada.F)
        self.client.post(reverse('partida_resultado', args=[final.pk]),
                         {'status': 'FINALIZADA', 'placar': '3-6 4-6', 'vencedor': ''})
        self.torneio.refresh_from_db()
        self.assertEqual(self.torneio.status, Torneio.Status.FINALIZADO)


class PartidaBloqueadaTest(TestCase):

    def setUp(self):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        for semi in torneio.partidas.filter(rodada=Partida.Rodada.SF):
            jogar(semi)
        jogar(torneio.partidas.get(rodada=Partida.Rodada.F))
        self.semi = torneio.partidas.filter(rodada=Partida.Rodada.SF).first()
        self.url = reverse('partida_resultado', args=[self.semi.pk])

    def test_get_redireciona_com_mensagem(self):
        resp = self.client.get(self.url, follow=True)
        self.assertContains(resp, 'Esta partida não pode mais ser alterada')

    def test_post_nao_altera_resultado(self):
        self.client.post(self.url, {'status': 'FINALIZADA', 'placar': '0-6 0-6', 'vencedor': ''})
        self.semi.refresh_from_db()
        self.assertEqual(self.semi.placar, '6-4 6-3')

    def test_bye_bloqueado(self):
        torneio = criar_torneio(nome='Com bye', jogadores=3)
        services.gerar_chave(torneio)
        bye = torneio.partidas.get(placar='BYE')
        resp = self.client.get(reverse('partida_resultado', args=[bye.pk]))
        self.assertEqual(resp.status_code, HTTPStatus.FOUND)
