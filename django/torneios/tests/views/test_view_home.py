from http import HTTPStatus

from django.test import TestCase
from django.urls import reverse

from torneios.models import Jogador
from torneios.tests.helpers import criar_torneio


class HomeGetTest(TestCase):

    def setUp(self):
        self.resp = self.client.get(reverse('home'))

    def test_status_code(self):
        self.assertEqual(self.resp.status_code, HTTPStatus.OK)

    def test_template_home(self):
        self.assertTemplateUsed(self.resp, 'torneios/home.html')
        self.assertTemplateUsed(self.resp, 'torneios/base.html')

    def test_caixa_de_busca(self):
        self.assertContains(self.resp, '<form', 1)
        self.assertContains(self.resp, 'name="q"')

    def test_links_de_cadastro(self):
        self.assertContains(self.resp, reverse('torneio_novo'))
        self.assertContains(self.resp, reverse('jogador_novo'))

    def test_sem_torneios_recentes(self):
        self.assertNotContains(self.resp, 'Torneios recentes')


class HomeTorneiosRecentesTest(TestCase):

    def setUp(self):
        for i in range(8):
            criar_torneio(nome=f'Torneio {i}')
        self.resp = self.client.get(reverse('home'))

    def test_exibe_torneios_recentes(self):
        self.assertContains(self.resp, 'Torneios recentes')

    def test_limita_a_seis_torneios(self):
        self.assertEqual(len(self.resp.context['recentes']), 6)


class BuscaTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio(nome='Open de Primavera', local='Clube Pinheiros')
        criar_torneio(nome='Copa de Inverno', local='Clube Central', descricao='Torneio aberto a todos.')
        self.jogador = Jogador.objects.create(nome='Gustavo Kuerten')

    def buscar(self, termo):
        return self.client.get(reverse('home'), {'q': termo})

    def test_template_busca(self):
        self.assertTemplateUsed(self.buscar('open'), 'torneios/busca.html')

    def test_busca_por_nome_do_torneio(self):
        resp = self.buscar('primavera')
        self.assertEqual(list(resp.context['torneios']), [self.torneio])

    def test_busca_por_local(self):
        resp = self.buscar('pinheiros')
        self.assertEqual(list(resp.context['torneios']), [self.torneio])

    def test_busca_por_descricao(self):
        resp = self.buscar('aberto a todos')
        self.assertEqual(resp.context['torneios'][0].nome, 'Copa de Inverno')

    def test_busca_por_jogador(self):
        resp = self.buscar('kuerten')
        self.assertEqual(list(resp.context['jogadores']), [self.jogador])
        self.assertContains(resp, self.jogador.get_absolute_url())

    def test_total_de_resultados(self):
        resp = self.buscar('clube')
        self.assertEqual(resp.context['total'], 2)

    def test_sem_resultados(self):
        resp = self.buscar('xyz')
        self.assertEqual(resp.context['total'], 0)
        self.assertContains(resp, 'não encontrou nenhum torneio ou jogador')

    def test_termo_so_com_espacos_volta_para_home(self):
        self.assertTemplateUsed(self.buscar('   '), 'torneios/home.html')

    def test_termo_preenchido_na_caixa_de_busca(self):
        self.assertContains(self.buscar('primavera'), 'value="primavera"')
