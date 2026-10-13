from django.test import TestCase

from torneios.forms import InscricaoForm
from torneios.models import Inscricao, Jogador
from torneios.tests.helpers import criar_torneio


class InscricaoFormTest(TestCase):

    def setUp(self):
        self.torneio = criar_torneio()
        self.jogador = Jogador.objects.create(nome='Gustavo Kuerten')

    def make_validated_form(self, **kwargs):
        valid = dict(jogador=self.jogador.pk, novo_jogador='', cabeca_de_chave='')
        data = dict(valid, **kwargs)
        form = InscricaoForm(self.torneio, data)
        form.is_valid()
        return form

    def test_campos_do_formulario(self):
        self.assertSequenceEqual(
            ['jogador', 'novo_jogador', 'cabeca_de_chave'],
            list(InscricaoForm(self.torneio).fields)
        )

    def test_inscrever_jogador_existente(self):
        form = self.make_validated_form()
        self.assertTrue(form.is_valid())
        inscricao = form.save()
        self.assertEqual(inscricao.jogador, self.jogador)
        self.assertEqual(inscricao.torneio, self.torneio)

    def test_inscrever_novo_jogador(self):
        form = self.make_validated_form(jogador='', novo_jogador='  Fernando Meligeni  ')
        inscricao = form.save()
        self.assertEqual(inscricao.jogador.nome, 'Fernando Meligeni')
        self.assertEqual(Jogador.objects.count(), 2)

    def test_jogador_existente_tem_prioridade(self):
        inscricao = self.make_validated_form(novo_jogador='Outro').save()
        self.assertEqual(inscricao.jogador, self.jogador)
        self.assertFalse(Jogador.objects.filter(nome='Outro').exists())

    def test_sem_jogador_e_sem_nome(self):
        form = self.make_validated_form(jogador='', novo_jogador='')
        self.assertIn('Escolha um jogador ou informe o nome de um novo.', form.non_field_errors())

    def test_nome_so_com_espacos(self):
        form = self.make_validated_form(jogador='', novo_jogador='   ')
        self.assertTrue(form.non_field_errors())

    def test_cabeca_de_chave_salva(self):
        inscricao = self.make_validated_form(cabeca_de_chave=1).save()
        self.assertEqual(inscricao.cabeca_de_chave, 1)

    def test_cabeca_de_chave_repetido(self):
        outro = Jogador.objects.create(nome='Outro')
        Inscricao.objects.create(torneio=self.torneio, jogador=outro, cabeca_de_chave=1)
        form = self.make_validated_form(cabeca_de_chave=1)
        self.assertIn('cabeca_de_chave', form.errors)

    def test_cabeca_de_chave_zero(self):
        form = self.make_validated_form(cabeca_de_chave=0)
        self.assertIn('cabeca_de_chave', form.errors)

    def test_lista_exclui_jogadores_ja_inscritos(self):
        Inscricao.objects.create(torneio=self.torneio, jogador=self.jogador)
        livre = Jogador.objects.create(nome='Livre')
        opcoes = list(InscricaoForm(self.torneio).fields['jogador'].queryset)
        self.assertEqual(opcoes, [livre])

    def test_jogador_ja_inscrito_e_invalido(self):
        Inscricao.objects.create(torneio=self.torneio, jogador=self.jogador)
        form = self.make_validated_form()
        self.assertIn('jogador', form.errors)

    def test_inscrito_em_outro_torneio_aparece_na_lista(self):
        Inscricao.objects.create(torneio=criar_torneio(nome='Outro'), jogador=self.jogador)
        opcoes = InscricaoForm(self.torneio).fields['jogador'].queryset
        self.assertIn(self.jogador, opcoes)
