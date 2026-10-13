from http import HTTPStatus

from django.test import TestCase
from django.urls import reverse

from torneios import services
from torneios.forms import JogadorForm
from torneios.models import Inscricao, Jogador
from torneios.tests.helpers import criar_torneio, jogar


class JogadorListaTest(TestCase):

    def setUp(self):
        Jogador.objects.create(nome='Gustavo Kuerten')
        Jogador.objects.create(nome='Fernando Meligeni')
        self.resp = self.client.get(reverse('jogador_lista'))

    def test_status_code(self):
        self.assertEqual(self.resp.status_code, HTTPStatus.OK)

    def test_template(self):
        self.assertTemplateUsed(self.resp, 'torneios/jogador_lista.html')

    def test_lista_jogadores(self):
        self.assertContains(self.resp, 'Gustavo Kuerten')
        self.assertContains(self.resp, 'Fernando Meligeni')

    def test_filtro_por_nome(self):
        resp = self.client.get(reverse('jogador_lista'), {'q': 'kuerten'})
        self.assertEqual([j.nome for j in resp.context['jogadores']], ['Gustavo Kuerten'])

    def test_filtro_sem_resultado(self):
        resp = self.client.get(reverse('jogador_lista'), {'q': 'xyz'})
        self.assertContains(resp, 'Nenhum jogador encontrado.')


class JogadorListaEstatisticasTest(TestCase):

    def test_conta_torneios_e_vitorias_sem_bye(self):
        torneio = criar_torneio(jogadores=3)
        services.gerar_chave(torneio)  # cabeça 1 recebe BYE
        jogar(torneio.partidas.get(rodada='SF', placar=''))
        jogar(torneio.partidas.get(rodada='F'))
        resp = self.client.get(reverse('jogador_lista'))
        campeao = next(j for j in resp.context['jogadores'] if j.nome == 'Jogador 01')
        self.assertEqual(campeao.num_torneios, 1)
        self.assertEqual(campeao.num_vitorias, 1)


class JogadorNovoTest(TestCase):

    def test_get(self):
        resp = self.client.get(reverse('jogador_novo'))
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(resp, 'torneios/form.html')
        self.assertIsInstance(resp.context['form'], JogadorForm)
        self.assertEqual(resp.context['titulo'], 'Novo jogador')

    def test_post_valido(self):
        resp = self.client.post(reverse('jogador_novo'), {'nome': 'Gustavo Kuerten'})
        jogador = Jogador.objects.get()
        self.assertRedirects(resp, jogador.get_absolute_url())

    def test_post_invalido(self):
        resp = self.client.post(reverse('jogador_novo'), {'nome': ''})
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertTrue(resp.context['form'].errors)
        self.assertFalse(Jogador.objects.exists())


class JogadorEditarTest(TestCase):

    def setUp(self):
        self.jogador = Jogador.objects.create(nome='Guga')

    def test_get(self):
        resp = self.client.get(reverse('jogador_editar', args=[self.jogador.pk]))
        self.assertEqual(resp.context['titulo'], 'Editar jogador')
        self.assertContains(resp, 'value="Guga"')

    def test_post_atualiza(self):
        self.client.post(reverse('jogador_editar', args=[self.jogador.pk]), {'nome': 'Gustavo Kuerten'})
        self.jogador.refresh_from_db()
        self.assertEqual(self.jogador.nome, 'Gustavo Kuerten')

    def test_jogador_inexistente(self):
        resp = self.client.get(reverse('jogador_editar', args=[9999]))
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)


class JogadorExcluirTest(TestCase):

    def setUp(self):
        self.jogador = Jogador.objects.create(nome='Guga')

    def test_exclui_jogador_sem_partidas(self):
        resp = self.client.post(reverse('jogador_excluir', args=[self.jogador.pk]))
        self.assertRedirects(resp, reverse('jogador_lista'))
        self.assertFalse(Jogador.objects.exists())

    def test_exclui_jogador_apenas_inscrito(self):
        Inscricao.objects.create(torneio=criar_torneio(), jogador=self.jogador)
        self.client.post(reverse('jogador_excluir', args=[self.jogador.pk]))
        self.assertFalse(Jogador.objects.filter(pk=self.jogador.pk).exists())

    def test_nao_exclui_jogador_com_partidas(self):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        jogador = torneio.inscricoes.first().jogador
        resp = self.client.post(reverse('jogador_excluir', args=[jogador.pk]), follow=True)
        self.assertContains(resp, 'já disputou partidas e não pode ser excluído')
        self.assertTrue(Jogador.objects.filter(pk=jogador.pk).exists())

    def test_get_nao_permitido(self):
        resp = self.client.get(reverse('jogador_excluir', args=[self.jogador.pk]))
        self.assertEqual(resp.status_code, HTTPStatus.METHOD_NOT_ALLOWED)


class JogadorDetalheTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio(jogadores=4)
        services.gerar_chave(self.torneio)
        for semi in self.torneio.partidas.filter(rodada='SF'):
            jogar(semi)
        jogar(self.torneio.partidas.get(rodada='F'), vence_1=False)
        self.campeao = self.torneio.partidas.get(rodada='F').vencedor.jogador
        self.resp = self.client.get(reverse('jogador_detalhe', args=[self.campeao.pk]))

    def test_status_code(self):
        self.assertEqual(self.resp.status_code, HTTPStatus.OK)

    def test_template(self):
        self.assertTemplateUsed(self.resp, 'torneios/jogador_detalhe.html')

    def test_estatisticas(self):
        self.assertEqual(self.resp.context['vitorias'], 2)
        self.assertEqual(self.resp.context['derrotas'], 0)

    def test_historico_de_partidas(self):
        self.assertEqual(len(self.resp.context['partidas']), 2)
        self.assertContains(self.resp, 'Vitória')

    def test_torneios_do_jogador(self):
        self.assertContains(self.resp, self.torneio.nome)

    def test_derrota_aparece_para_o_vice(self):
        vice = self.torneio.partidas.get(rodada='F').inscricao_1.jogador
        resp = self.client.get(reverse('jogador_detalhe', args=[vice.pk]))
        self.assertEqual(resp.context['derrotas'], 1)
        self.assertContains(resp, 'Derrota')

    def test_partidas_bye_nao_aparecem(self):
        torneio = criar_torneio(nome='Com bye', jogadores=3)
        services.gerar_chave(torneio)
        cabeca = torneio.inscricoes.get(cabeca_de_chave=1).jogador
        resp = self.client.get(reverse('jogador_detalhe', args=[cabeca.pk]))
        # O cabeça 1 avança direto: só a final (ainda agendada) aparece no histórico.
        self.assertEqual([p.rodada for p in resp.context['partidas']], ['F'])
        self.assertEqual(resp.context['vitorias'], 0)

    def test_jogador_sem_torneios(self):
        jogador = Jogador.objects.create(nome='Novato')
        resp = self.client.get(reverse('jogador_detalhe', args=[jogador.pk]))
        self.assertContains(resp, 'Ainda não se inscreveu em nenhum torneio.')
