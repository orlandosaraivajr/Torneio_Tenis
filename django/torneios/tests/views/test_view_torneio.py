from http import HTTPStatus

from django.test import TestCase
from django.urls import reverse

from torneios import services
from torneios.forms import InscricaoForm, TorneioForm
from torneios.models import Partida, Torneio
from torneios.tests.helpers import criar_torneio, jogar, jogar_favorito


def dados_torneio(**kwargs):
    dados = dict(
        nome='Open de Primavera', descricao='', data_torneio='2026-11-01', local='Clube Central',
        formato=Torneio.Formato.ELIMINATORIA, status=Torneio.Status.RASCUNHO,
        premiacao='', regulamento='', organizador='',
    )
    dados.update(kwargs)
    return dados


class TorneioListaTest(TestCase):

    def setUp(self):
        self.aberto = criar_torneio(nome='Aberto', status=Torneio.Status.INSCRICOES)
        self.cancelado = criar_torneio(nome='Cancelado', status=Torneio.Status.CANCELADO)
        self.resp = self.client.get(reverse('torneio_lista'))

    def test_status_code(self):
        self.assertEqual(self.resp.status_code, HTTPStatus.OK)

    def test_template(self):
        self.assertTemplateUsed(self.resp, 'torneios/torneio_lista.html')

    def test_lista_todos(self):
        self.assertContains(self.resp, 'Aberto')
        self.assertContains(self.resp, 'Cancelado')

    def test_filtro_por_status(self):
        resp = self.client.get(reverse('torneio_lista'), {'status': Torneio.Status.CANCELADO})
        self.assertEqual(list(resp.context['torneios']), [self.cancelado])
        self.assertEqual(resp.context['status_atual'], Torneio.Status.CANCELADO)

    def test_lista_vazia(self):
        resp = self.client.get(reverse('torneio_lista'), {'status': Torneio.Status.FINALIZADO})
        self.assertContains(resp, 'Nenhum torneio encontrado.')


class TorneioNovoGetTest(TestCase):

    def setUp(self):
        self.resp = self.client.get(reverse('torneio_novo'))

    def test_status_code(self):
        self.assertEqual(self.resp.status_code, HTTPStatus.OK)

    def test_template(self):
        self.assertTemplateUsed(self.resp, 'torneios/form.html')

    def test_formulario_no_contexto(self):
        self.assertIsInstance(self.resp.context['form'], TorneioForm)
        self.assertEqual(self.resp.context['titulo'], 'Novo torneio')

    def test_csrf(self):
        self.assertContains(self.resp, 'csrfmiddlewaretoken')

    def test_upload_habilitado(self):
        self.assertContains(self.resp, 'enctype="multipart/form-data"')


class TorneioNovoPostTest(TestCase):

    def test_post_valido_cria_e_redireciona(self):
        resp = self.client.post(reverse('torneio_novo'), dados_torneio())
        torneio = Torneio.objects.get()
        self.assertRedirects(resp, torneio.get_absolute_url())

    def test_post_valido_exibe_mensagem(self):
        resp = self.client.post(reverse('torneio_novo'), dados_torneio(), follow=True)
        self.assertContains(resp, 'Torneio salvo.')

    def test_post_invalido_nao_salva(self):
        resp = self.client.post(reverse('torneio_novo'), dados_torneio(nome=''))
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(resp, 'torneios/form.html')
        self.assertTrue(resp.context['form'].errors)
        self.assertFalse(Torneio.objects.exists())


class TorneioEditarTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio()

    def test_get(self):
        resp = self.client.get(reverse('torneio_editar', args=[self.torneio.pk]))
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertEqual(resp.context['titulo'], 'Editar torneio')
        self.assertEqual(resp.context['form'].instance, self.torneio)

    def test_post_atualiza(self):
        self.client.post(reverse('torneio_editar', args=[self.torneio.pk]), dados_torneio(nome='Novo nome'))
        self.torneio.refresh_from_db()
        self.assertEqual(self.torneio.nome, 'Novo nome')

    def test_torneio_inexistente(self):
        resp = self.client.get(reverse('torneio_editar', args=[9999]))
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)


class TorneioExcluirTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio()

    def test_post_exclui_e_redireciona(self):
        resp = self.client.post(reverse('torneio_excluir', args=[self.torneio.pk]))
        self.assertRedirects(resp, reverse('torneio_lista'))
        self.assertFalse(Torneio.objects.exists())

    def test_get_nao_permitido(self):
        resp = self.client.get(reverse('torneio_excluir', args=[self.torneio.pk]))
        self.assertEqual(resp.status_code, HTTPStatus.METHOD_NOT_ALLOWED)
        self.assertTrue(Torneio.objects.exists())


class TorneioDetalheTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio(jogadores=2)
        self.url = self.torneio.get_absolute_url()

    def test_status_code(self):
        self.assertEqual(self.client.get(self.url).status_code, HTTPStatus.OK)

    def test_template(self):
        self.assertTemplateUsed(self.client.get(self.url), 'torneios/torneio_detalhe.html')

    def test_aba_padrao_visao_geral(self):
        self.assertEqual(self.client.get(self.url).context['aba'], 'visao')

    def test_aba_invalida_vira_visao_geral(self):
        self.assertEqual(self.client.get(self.url, {'aba': 'xpto'}).context['aba'], 'visao')

    def test_todas_as_abas(self):
        for aba in ['visao', 'inscritos', 'chave', 'partidas', 'classificacao']:
            with self.subTest(aba=aba):
                resp = self.client.get(self.url, {'aba': aba})
                self.assertEqual(resp.status_code, HTTPStatus.OK)
                self.assertEqual(resp.context['aba'], aba)

    def test_torneio_inexistente(self):
        resp = self.client.get(reverse('torneio_detalhe', args=[9999]))
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_sugere_gerar_chave(self):
        self.assertContains(self.client.get(self.url), reverse('gerar_chave', args=[self.torneio.pk]))

    def test_formulario_de_inscricao_disponivel(self):
        resp = self.client.get(self.url, {'aba': 'inscritos'})
        self.assertIsInstance(resp.context['inscricao_form'], InscricaoForm)

    def test_sem_formulario_depois_da_chave(self):
        services.gerar_chave(self.torneio)
        resp = self.client.get(self.url, {'aba': 'inscritos'})
        self.assertIsNone(resp.context['inscricao_form'])
        self.assertContains(resp, 'as inscrições estão encerradas')

    def test_exibe_campeao(self):
        services.gerar_chave(self.torneio)
        jogar(self.torneio.partidas.get())
        resp = self.client.get(self.url)
        self.assertEqual(resp.context['campeao'].jogador.nome, 'Jogador 01')
        self.assertContains(resp, 'Campeão')

    def test_chave_eliminatoria_no_contexto(self):
        torneio = criar_torneio(jogadores=8)
        services.gerar_chave(torneio)
        resp = self.client.get(torneio.get_absolute_url(), {'aba': 'chave'})
        nomes = [rodada['nome'] for rodada in resp.context['chave']]
        self.assertEqual(nomes, ['Quartas de final', 'Semifinal', 'Final'])
        self.assertTrue(resp.context['tem_mata_mata'])

    def test_round_robin_exibe_rodadas_e_tabela(self):
        torneio = criar_torneio(Torneio.Formato.ROUND_ROBIN, jogadores=4)
        services.gerar_chave(torneio)
        resp = self.client.get(torneio.get_absolute_url(), {'aba': 'chave'})
        self.assertContains(resp, 'Rodada 3')
        self.assertEqual(len(resp.context['tabela_geral']), 4)

    def test_grupos_concluidos_oferece_mata_mata(self):
        torneio = criar_torneio(Torneio.Formato.GRUPOS, jogadores=8)
        services.gerar_chave(torneio)
        for partida in torneio.partidas.all():
            jogar_favorito(partida)
        resp = self.client.get(torneio.get_absolute_url(), {'aba': 'chave'})
        self.assertTrue(resp.context['grupos_concluidos'])
        self.assertEqual([g['letra'] for g in resp.context['grupos']], ['A', 'B'])
        self.assertContains(resp, reverse('gerar_mata_mata', args=[torneio.pk]))


class InscreverTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio()
        self.url = reverse('inscrever', args=[self.torneio.pk])
        self.redirect = f'{self.torneio.get_absolute_url()}?aba=inscritos'

    def test_inscreve_novo_jogador(self):
        resp = self.client.post(self.url, {'novo_jogador': 'Guga'})
        self.assertRedirects(resp, self.redirect)
        self.assertTrue(self.torneio.inscricoes.filter(jogador__nome='Guga').exists())

    def test_mensagem_de_sucesso(self):
        resp = self.client.post(self.url, {'novo_jogador': 'Guga'}, follow=True)
        self.assertContains(resp, 'Guga inscrito(a).')

    def test_dados_invalidos_exibem_erro(self):
        resp = self.client.post(self.url, {}, follow=True)
        self.assertContains(resp, 'Escolha um jogador ou informe o nome de um novo.')
        self.assertFalse(self.torneio.inscricoes.exists())

    def test_torneio_fechado_recusa_inscricao(self):
        Torneio.objects.filter(pk=self.torneio.pk).update(status=Torneio.Status.EM_ANDAMENTO)
        resp = self.client.post(self.url, {'novo_jogador': 'Guga'}, follow=True)
        self.assertContains(resp, 'Este torneio não aceita mais inscrições.')
        self.assertFalse(self.torneio.inscricoes.exists())

    def test_get_nao_permitido(self):
        self.assertEqual(self.client.get(self.url).status_code, HTTPStatus.METHOD_NOT_ALLOWED)


class RemoverInscricaoTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio(jogadores=2)
        self.inscricao = self.torneio.inscricoes.first()
        self.url = reverse('remover_inscricao', args=[self.inscricao.pk])

    def test_remove_inscricao(self):
        resp = self.client.post(self.url)
        self.assertRedirects(resp, f'{self.torneio.get_absolute_url()}?aba=inscritos')
        self.assertEqual(self.torneio.inscricoes.count(), 1)

    def test_nao_remove_depois_da_chave(self):
        services.gerar_chave(self.torneio)
        resp = self.client.post(self.url, follow=True)
        self.assertContains(resp, 'Não é possível remover inscritos depois de gerada a chave.')
        self.assertEqual(self.torneio.inscricoes.count(), 2)


class GerarChaveViewTest(TestCase):

    def test_gera_chave_e_redireciona(self):
        torneio = criar_torneio(jogadores=4)
        resp = self.client.post(reverse('gerar_chave', args=[torneio.pk]))
        self.assertRedirects(resp, f'{torneio.get_absolute_url()}?aba=chave')
        self.assertEqual(torneio.partidas.count(), 3)

    def test_mensagem_de_sucesso(self):
        torneio = criar_torneio(jogadores=4)
        resp = self.client.post(reverse('gerar_chave', args=[torneio.pk]), follow=True)
        self.assertContains(resp, 'Chave gerada! Bons jogos.')

    def test_erro_de_regra_vira_mensagem(self):
        torneio = criar_torneio(jogadores=1)
        resp = self.client.post(reverse('gerar_chave', args=[torneio.pk]), follow=True)
        self.assertContains(resp, 'São necessários pelo menos 2 jogadores para montar a chave.')
        self.assertFalse(torneio.partidas.exists())

    def test_get_nao_permitido(self):
        torneio = criar_torneio(jogadores=4)
        resp = self.client.get(reverse('gerar_chave', args=[torneio.pk]))
        self.assertEqual(resp.status_code, HTTPStatus.METHOD_NOT_ALLOWED)


class GerarMataMataViewTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio(Torneio.Formato.GRUPOS, jogadores=8)
        services.gerar_chave(self.torneio)
        self.url = reverse('gerar_mata_mata', args=[self.torneio.pk])

    def test_grupos_incompletos(self):
        resp = self.client.post(self.url, follow=True)
        self.assertContains(resp, 'Finalize todas as partidas da fase de grupos')

    def test_gera_mata_mata(self):
        for partida in self.torneio.partidas.all():
            jogar_favorito(partida)
        resp = self.client.post(self.url, follow=True)
        self.assertContains(resp, 'Mata-mata gerado com os classificados.')
        self.assertTrue(self.torneio.partidas.filter(rodada=Partida.Rodada.F).exists())


class RefazerChaveViewTest(TestCase):

    def test_apaga_partidas_e_reabre_inscricoes(self):
        torneio = criar_torneio(jogadores=4)
        services.gerar_chave(torneio)
        resp = self.client.post(reverse('refazer_chave', args=[torneio.pk]))
        self.assertRedirects(resp, f'{torneio.get_absolute_url()}?aba=inscritos')
        torneio.refresh_from_db()
        self.assertFalse(torneio.partidas.exists())
        self.assertEqual(torneio.status, Torneio.Status.INSCRICOES)
