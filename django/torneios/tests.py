import datetime

from django.test import TestCase
from django.urls import reverse

from . import services
from .models import Inscricao, Jogador, Partida, Torneio, parse_placar


def criar_torneio(formato, n):
    torneio = Torneio.objects.create(
        nome='Open', data_torneio=datetime.date(2026, 11, 1), local='Clube', formato=formato,
        status=Torneio.Status.INSCRICOES,
    )
    for i in range(n):
        jogador = Jogador.objects.create(nome=f'Jogador {i + 1:02d}')
        Inscricao.objects.create(torneio=torneio, jogador=jogador, cabeca_de_chave=i + 1)
    return torneio


def jogar(partida, vence_1=True):
    placar = '6-4 6-3' if vence_1 else '4-6 3-6'
    vencedor = partida.inscricao_1 if vence_1 else partida.inscricao_2
    services.registrar_resultado(partida, Partida.Status.FINALIZADA, placar, vencedor, None)


class PlacarTests(TestCase):
    def test_parse(self):
        self.assertEqual(parse_placar('6-4 3-6 7-6(5)'), [(6, 4, None), (3, 6, None), (7, 6, 5)])

    def test_invalido(self):
        with self.assertRaises(ValueError):
            parse_placar('6x4')


class EliminatoriaTests(TestCase):
    def test_ordem_cabecas(self):
        self.assertEqual(services.ordem_cabecas_de_chave(8), [1, 8, 4, 5, 2, 7, 3, 6])

    def test_chave_com_byes_e_campeao(self):
        torneio = criar_torneio(Torneio.Formato.ELIMINATORIA, 6)
        services.gerar_chave(torneio)
        self.assertEqual(torneio.partidas.filter(rodada='QF').count(), 4)
        self.assertEqual(torneio.partidas.filter(placar='BYE').count(), 2)

        # Os cabeças 1 e 2 recebem BYE e já aparecem nas semifinais.
        semis = list(torneio.partidas.filter(rodada='SF').order_by('posicao'))
        self.assertEqual(semis[0].inscricao_1.cabeca_de_chave, 1)
        self.assertEqual(semis[1].inscricao_1.cabeca_de_chave, 2)

        for rodada in ['QF', 'SF', 'F']:
            for partida in torneio.partidas.filter(rodada=rodada).exclude(placar='BYE').order_by('posicao'):
                jogar(Partida.objects.get(pk=partida.pk))

        torneio.refresh_from_db()
        self.assertEqual(torneio.status, Torneio.Status.FINALIZADO)
        self.assertEqual(services.campeao(torneio).cabeca_de_chave, 1)

    def test_partida_bloqueada_apos_proxima_encerrada(self):
        torneio = criar_torneio(Torneio.Formato.ELIMINATORIA, 4)
        services.gerar_chave(torneio)
        for partida in torneio.partidas.filter(rodada='SF'):
            jogar(partida)
        jogar(torneio.partidas.get(rodada='F'))
        self.assertFalse(torneio.partidas.filter(rodada='SF').first().editavel)


class RoundRobinTests(TestCase):
    def test_todos_contra_todos(self):
        torneio = criar_torneio(Torneio.Formato.ROUND_ROBIN, 5)
        services.gerar_chave(torneio)
        self.assertEqual(torneio.partidas.count(), 10)
        for partida in torneio.partidas.all():
            # Quem tem a melhor semente sempre vence.
            jogar(partida, partida.inscricao_1.cabeca_de_chave < partida.inscricao_2.cabeca_de_chave)
        torneio.refresh_from_db()
        self.assertEqual(torneio.status, Torneio.Status.FINALIZADO)
        self.assertEqual(services.campeao(torneio).cabeca_de_chave, 1)


class GruposTests(TestCase):
    def test_grupos_e_mata_mata(self):
        torneio = criar_torneio(Torneio.Formato.GRUPOS, 8)
        services.gerar_chave(torneio)
        self.assertEqual(set(torneio.inscricoes.values_list('grupo', flat=True)), {'A', 'B'})
        self.assertEqual(torneio.partidas.count(), 12)

        with self.assertRaises(services.FluxoError):
            services.gerar_mata_mata_dos_grupos(torneio)

        for partida in torneio.partidas.all():
            jogar(partida, partida.inscricao_1.cabeca_de_chave < partida.inscricao_2.cabeca_de_chave)
        services.gerar_mata_mata_dos_grupos(torneio)
        self.assertEqual(torneio.partidas.filter(rodada='SF').count(), 2)
        self.assertEqual(torneio.partidas.filter(rodada='F').count(), 1)
        self.assertFalse(torneio.partidas.filter(rodada='GR').first().editavel)


class ViewsTests(TestCase):
    def test_paginas_principais(self):
        torneio = criar_torneio(Torneio.Formato.GRUPOS, 8)
        services.gerar_chave(torneio)
        for partida in torneio.partidas.all():
            jogar(partida)
        services.gerar_mata_mata_dos_grupos(torneio)
        jogador = Jogador.objects.first()
        urls = [
            reverse('home'), reverse('home') + '?q=Open', reverse('torneio_lista'), reverse('torneio_novo'),
            reverse('jogador_lista'), reverse('jogador_novo'), reverse('jogador_detalhe', args=[jogador.pk]),
            reverse('partida_resultado', args=[torneio.partidas.get(rodada='F').pk]),
        ]
        urls += [f'{torneio.get_absolute_url()}?aba={aba}' for aba in ['visao', 'inscritos', 'chave', 'partidas', 'classificacao']]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_registrar_resultado_pelo_placar(self):
        torneio = criar_torneio(Torneio.Formato.ELIMINATORIA, 2)
        self.client.post(reverse('gerar_chave', args=[torneio.pk]))
        final = torneio.partidas.get()
        resposta = self.client.post(reverse('partida_resultado', args=[final.pk]), {
            'status': 'FINALIZADA', 'placar': '4-6 6-3 10-8', 'vencedor': '', 'voltar': 'chave',
        })
        self.assertEqual(resposta.status_code, 302)
        final.refresh_from_db()
        self.assertEqual(final.vencedor, final.inscricao_1)
        torneio.refresh_from_db()
        self.assertEqual(torneio.status, Torneio.Status.FINALIZADO)

    def test_inscricao_novo_jogador(self):
        torneio = criar_torneio(Torneio.Formato.ELIMINATORIA, 0)
        self.client.post(reverse('inscrever', args=[torneio.pk]), {'novo_jogador': 'Guga'})
        self.assertTrue(torneio.inscricoes.filter(jogador__nome='Guga').exists())
