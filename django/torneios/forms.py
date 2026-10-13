from django import forms

from .models import Inscricao, Jogador, Partida, Torneio, parse_placar
from .services import vencedor_pelo_placar


class TorneioForm(forms.ModelForm):
    class Meta:
        model = Torneio
        fields = [
            'nome', 'descricao', 'data_torneio', 'local', 'formato', 'status',
            'premiacao', 'regulamento', 'regulamento_arquivo', 'organizador',
        ]
        widgets = {
            'data_torneio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'regulamento': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['organizador'].empty_label = 'Sem organizador'
        if self.instance.pk and self.instance.partidas.exists():
            # Com a chave gerada, mudar o formato quebraria as partidas existentes.
            self.fields['formato'].disabled = True
            self.fields['formato'].help_text = 'Refaça a chave para alterar o formato.'


class JogadorForm(forms.ModelForm):
    class Meta:
        model = Jogador
        fields = ['nome', 'foto']


class InscricaoForm(forms.Form):
    jogador = forms.ModelChoiceField(
        queryset=Jogador.objects.none(), required=False, empty_label='Selecione um jogador cadastrado'
    )
    novo_jogador = forms.CharField(
        label='ou cadastre um novo', max_length=150, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Nome do novo jogador'}),
    )
    cabeca_de_chave = forms.IntegerField(
        label='Cabeça de chave', min_value=1, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Opcional'}),
    )

    def __init__(self, torneio, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.torneio = torneio
        self.fields['jogador'].queryset = Jogador.objects.exclude(inscricoes__torneio=torneio)

    def clean(self):
        dados = super().clean()
        if not dados.get('jogador') and not dados.get('novo_jogador', '').strip():
            raise forms.ValidationError('Escolha um jogador ou informe o nome de um novo.')
        semente = dados.get('cabeca_de_chave')
        if semente and self.torneio.inscricoes.filter(cabeca_de_chave=semente).exists():
            self.add_error('cabeca_de_chave', f'Já existe um cabeça de chave nº {semente}.')
        return dados

    def save(self):
        jogador = self.cleaned_data.get('jogador')
        if not jogador:
            jogador = Jogador.objects.create(nome=self.cleaned_data['novo_jogador'].strip())
        return Inscricao.objects.create(
            torneio=self.torneio, jogador=jogador, cabeca_de_chave=self.cleaned_data.get('cabeca_de_chave')
        )


class ResultadoForm(forms.Form):
    data_hora = forms.DateTimeField(
        label='Data e hora', required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M'],
    )
    status = forms.ChoiceField(choices=Partida.Status.choices)
    placar = forms.CharField(
        max_length=50, required=False,
        widget=forms.TextInput(attrs={'placeholder': '6-4 3-6 10-7'}),
        help_text='Sets separados por espaço, games do primeiro jogador primeiro. Tiebreak: 7-6(5).',
    )
    vencedor = forms.ChoiceField(
        required=False, widget=forms.RadioSelect,
        help_text='Deixe em "Pelo placar" para calcular automaticamente.',
    )

    def __init__(self, partida, *args, **kwargs):
        self.partida = partida
        kwargs.setdefault('initial', {
            'data_hora': partida.data_hora,
            'status': partida.status,
            'placar': partida.placar,
            'vencedor': partida.vencedor_id or '',
        })
        super().__init__(*args, **kwargs)
        opcoes = [('', 'Pelo placar')]
        for inscricao in (partida.inscricao_1, partida.inscricao_2):
            if inscricao:
                opcoes.append((str(inscricao.pk), inscricao.jogador.nome))
        self.fields['vencedor'].choices = opcoes

    def clean_placar(self):
        placar = ' '.join(self.cleaned_data['placar'].split())
        try:
            parse_placar(placar)
        except ValueError as erro:
            raise forms.ValidationError(str(erro))
        return placar

    def clean(self):
        dados = super().clean()
        status = dados.get('status')
        partida = self.partida
        if 'placar' not in dados or status not in Partida.ENCERRADOS:
            dados['vencedor_obj'] = None
            return dados

        if not (partida.inscricao_1 and partida.inscricao_2):
            raise forms.ValidationError('A partida ainda não tem os dois jogadores definidos.')

        escolhido = dados.get('vencedor')
        if escolhido:
            vencedor = partida.inscricao_1 if str(partida.inscricao_1.pk) == escolhido else partida.inscricao_2
            pelo_placar = vencedor_pelo_placar(partida, dados['placar'])
            if status == Partida.Status.FINALIZADA and pelo_placar and pelo_placar != vencedor:
                self.add_error('vencedor', 'O vencedor escolhido não confere com o placar.')
        else:
            vencedor = vencedor_pelo_placar(partida, dados['placar'])
            if not vencedor:
                self.add_error('vencedor', 'Informe o vencedor ou um placar que defina quem venceu.')
        if status == Partida.Status.FINALIZADA and not dados['placar']:
            self.add_error('placar', 'Informe o placar de uma partida finalizada.')
        dados['vencedor_obj'] = vencedor
        return dados
