from django.test import TestCase

from torneios.forms import JogadorForm
from torneios.models import Jogador


class JogadorFormTest(TestCase):

    def make_validated_form(self, **kwargs):
        valid = dict(nome='Gustavo Kuerten')
        data = dict(valid, **kwargs)
        form = JogadorForm(data)
        form.is_valid()
        return form

    def test_campos_do_formulario(self):
        self.assertSequenceEqual(['nome', 'foto'], list(JogadorForm().fields))

    def test_formulario_valido(self):
        self.assertTrue(self.make_validated_form().is_valid())

    def test_salvar_cria_jogador(self):
        jogador = self.make_validated_form().save()
        self.assertTrue(Jogador.objects.filter(pk=jogador.pk, nome='Gustavo Kuerten').exists())

    def test_nome_obrigatorio(self):
        form = self.make_validated_form(nome='')
        self.assertIn('nome', form.errors)

    def test_nome_muito_longo(self):
        form = self.make_validated_form(nome='x' * 151)
        self.assertIn('nome', form.errors)

    def test_foto_opcional(self):
        self.assertFalse(JogadorForm().fields['foto'].required)
