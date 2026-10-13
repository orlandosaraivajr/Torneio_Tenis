from django.contrib.auth.models import User
from django.test import TestCase

from torneios import services
from torneios.forms import TorneioForm
from torneios.models import Torneio
from torneios.tests.helpers import criar_torneio


class TorneioFormTest(TestCase):

    def make_validated_form(self, instance=None, **kwargs):
        valid = dict(
            nome='Open de Primavera',
            descricao='',
            data_torneio='2026-11-01',
            local='Clube Central',
            formato=Torneio.Formato.ELIMINATORIA,
            status=Torneio.Status.RASCUNHO,
            premiacao='',
            regulamento='',
            organizador='',
        )
        data = dict(valid, **kwargs)
        form = TorneioForm(data, instance=instance)
        form.is_valid()
        return form

    def test_campos_do_formulario(self):
        esperado = [
            'nome', 'descricao', 'data_torneio', 'local', 'formato', 'status',
            'premiacao', 'regulamento', 'regulamento_arquivo', 'organizador',
        ]
        self.assertSequenceEqual(esperado, list(TorneioForm().fields))

    def test_formulario_valido(self):
        form = self.make_validated_form()
        self.assertTrue(form.is_valid())

    def test_salvar_cria_torneio(self):
        torneio = self.make_validated_form().save()
        self.assertEqual(torneio.nome, 'Open de Primavera')
        self.assertTrue(Torneio.objects.filter(pk=torneio.pk).exists())

    def test_campos_obrigatorios(self):
        for campo in ['nome', 'data_torneio', 'local', 'formato', 'status']:
            with self.subTest(campo=campo):
                form = self.make_validated_form(**{campo: ''})
                self.assertIn(campo, form.errors)

    def test_campos_opcionais(self):
        form = self.make_validated_form()
        for campo in ['descricao', 'premiacao', 'regulamento', 'regulamento_arquivo', 'organizador']:
            with self.subTest(campo=campo):
                self.assertFalse(form.fields[campo].required)

    def test_data_invalida(self):
        form = self.make_validated_form(data_torneio='31/02/2026')
        self.assertIn('data_torneio', form.errors)

    def test_formato_invalido(self):
        form = self.make_validated_form(formato='SUICO')
        self.assertIn('formato', form.errors)

    def test_organizador_existente(self):
        usuario = User.objects.create_user('orlando')
        form = self.make_validated_form(organizador=usuario.pk)
        self.assertEqual(form.save().organizador, usuario)

    def test_rotulo_sem_organizador(self):
        self.assertEqual(TorneioForm().fields['organizador'].empty_label, 'Sem organizador')

    def test_formato_editavel_sem_chave(self):
        form = TorneioForm(instance=criar_torneio(jogadores=2))
        self.assertFalse(form.fields['formato'].disabled)

    def test_formato_bloqueado_com_chave_gerada(self):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        form = TorneioForm(instance=torneio)
        self.assertTrue(form.fields['formato'].disabled)

    def test_formato_bloqueado_ignora_valor_enviado(self):
        torneio = criar_torneio(jogadores=2)
        services.gerar_chave(torneio)
        form = self.make_validated_form(instance=torneio, formato=Torneio.Formato.ROUND_ROBIN)
        self.assertEqual(form.save().formato, Torneio.Formato.ELIMINATORIA)
