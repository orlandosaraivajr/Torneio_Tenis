from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (DateField, DateTimeLocalField, IntegerField, RadioField, SelectField, StringField,
                     TextAreaField)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from .extensions import db
from .models import Formato, Inscricao, Jogador, StatusPartida, StatusTorneio, Usuario, parse_placar
from .services import vencedor_pelo_placar

IMAGENS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
DOCUMENTOS = ['pdf', 'doc', 'docx', 'txt', 'odt']


def _inteiro_ou_none(valor):
    return int(valor) if valor not in (None, '', 'None') else None


class TorneioForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired(), Length(max=150)])
    descricao = TextAreaField('Descrição', render_kw={'rows': 3})
    data_torneio = DateField('Data do torneio', validators=[DataRequired()])
    local = StringField('Local (clube)', validators=[DataRequired(), Length(max=150)])
    formato = SelectField('Formato', choices=Formato.choices(), default=Formato.ELIMINATORIA)
    status = SelectField('Status', choices=StatusTorneio.choices(), default=StatusTorneio.RASCUNHO)
    premiacao = StringField('Premiação', validators=[Length(max=255)])
    regulamento = TextAreaField('Regulamento', render_kw={'rows': 5})
    regulamento_arquivo = FileField(
        'Arquivo do regulamento', validators=[FileAllowed(DOCUMENTOS, 'Envie PDF, DOC, DOCX, ODT ou TXT.')]
    )
    organizador = SelectField('Organizador', coerce=_inteiro_ou_none, validators=[Optional()])

    def __init__(self, *args, torneio=None, **kwargs):
        super().__init__(*args, obj=torneio, **kwargs)
        self.torneio = torneio
        self.organizador.choices = [(None, 'Sem organizador')] + [
            (u.id, u.nome) for u in Usuario.query.order_by(Usuario.nome)
        ]
        if torneio is not None and not self.is_submitted():
            self.organizador.data = torneio.organizador_id
        self.formato_bloqueado = bool(torneio and torneio.partidas)
        if self.formato_bloqueado:
            # Com a chave gerada, mudar o formato quebraria as partidas existentes.
            self.formato.render_kw = {'disabled': True}
            self.formato.description = 'Refaça a chave para alterar o formato.'
            self.formato.data = torneio.formato

    def preencher(self, torneio):
        """Copia os dados validados para o torneio (sem tocar no arquivo)."""
        for campo in ['nome', 'descricao', 'data_torneio', 'local', 'status', 'premiacao', 'regulamento']:
            setattr(torneio, campo, getattr(self, campo).data)
        torneio.descricao = torneio.descricao or ''
        torneio.premiacao = torneio.premiacao or ''
        torneio.regulamento = torneio.regulamento or ''
        if not self.formato_bloqueado:
            torneio.formato = self.formato.data
        torneio.organizador_id = self.organizador.data


class JogadorForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired(), Length(max=150)])
    foto = FileField('Foto', validators=[FileAllowed(IMAGENS, 'Envie uma imagem (JPG, PNG, GIF ou WEBP).')])


class InscricaoForm(FlaskForm):
    jogador = SelectField('Jogador', coerce=_inteiro_ou_none, validators=[Optional()])
    novo_jogador = StringField(
        'ou cadastre um novo', validators=[Length(max=150)], render_kw={'placeholder': 'Nome do novo jogador'}
    )
    cabeca_de_chave = IntegerField(
        'Cabeça de chave', validators=[Optional(), NumberRange(min=1, message='Use um número a partir de 1.')],
        render_kw={'placeholder': 'Opcional'},
    )

    def __init__(self, torneio, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.torneio = torneio
        inscritos = {i.jogador_id for i in torneio.inscricoes}
        self.jogador.choices = [(None, 'Selecione um jogador cadastrado')] + [
            (j.id, j.nome) for j in Jogador.query.order_by(Jogador.nome) if j.id not in inscritos
        ]

    def validate(self, extra_validators=None):
        valido = super().validate(extra_validators)
        if not self.jogador.data and not (self.novo_jogador.data or '').strip():
            self.form_errors.append('Escolha um jogador ou informe o nome de um novo.')
            valido = False
        semente = self.cabeca_de_chave.data
        if semente and any(i.cabeca_de_chave == semente for i in self.torneio.inscricoes):
            self.cabeca_de_chave.errors = [*self.cabeca_de_chave.errors, f'Já existe um cabeça de chave nº {semente}.']
            valido = False
        return valido

    def criar_inscricao(self):
        if self.jogador.data:
            jogador = db.session.get(Jogador, self.jogador.data)
        else:
            jogador = Jogador(nome=self.novo_jogador.data.strip())
        inscricao = Inscricao(torneio=self.torneio, jogador=jogador, cabeca_de_chave=self.cabeca_de_chave.data)
        db.session.add(inscricao)
        return inscricao


class ResultadoForm(FlaskForm):
    data_hora = DateTimeLocalField('Data e hora', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    status = SelectField('Status', choices=StatusPartida.choices())
    placar = StringField(
        'Placar', validators=[Length(max=50)], render_kw={'placeholder': '6-4 3-6 10-7'},
        description='Sets separados por espaço, games do primeiro jogador primeiro. Tiebreak: 7-6(5).',
    )
    vencedor = RadioField(
        'Vencedor', coerce=_inteiro_ou_none, validate_choice=False,
        description='Deixe em "Pelo placar" para calcular automaticamente.',
    )

    def __init__(self, partida, *args, **kwargs):
        kwargs.setdefault('data', {
            'data_hora': partida.data_hora,
            'status': partida.status,
            'placar': partida.placar,
            'vencedor': partida.vencedor_id,
        })
        super().__init__(*args, **kwargs)
        self.partida = partida
        self.vencedor_obj = None
        self.vencedor.choices = [(None, 'Pelo placar')] + [
            (i.id, i.jogador.nome) for i in (partida.inscricao_1, partida.inscricao_2) if i
        ]

    def validate_placar(self, campo):
        campo.data = ' '.join((campo.data or '').split())
        try:
            parse_placar(campo.data)
        except ValueError as erro:
            raise ValidationError(str(erro))

    def validate_vencedor(self, campo):
        validos = {valor for valor, _ in campo.choices}
        if campo.data not in validos:
            raise ValidationError('Escolha um dos jogadores da partida.')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        partida = self.partida
        status = self.status.data
        if status not in StatusPartida.ENCERRADOS:
            return True

        if not (partida.inscricao_1 and partida.inscricao_2):
            self.form_errors.append('A partida ainda não tem os dois jogadores definidos.')
            return False

        valido = True
        placar = self.placar.data
        if self.vencedor.data:
            vencedor = partida.inscricao_1 if partida.inscricao_1.id == self.vencedor.data else partida.inscricao_2
            pelo_placar = vencedor_pelo_placar(partida, placar)
            if status == StatusPartida.FINALIZADA and pelo_placar and pelo_placar is not vencedor:
                self.vencedor.errors.append('O vencedor escolhido não confere com o placar.')
                valido = False
        else:
            vencedor = vencedor_pelo_placar(partida, placar)
            if not vencedor:
                self.vencedor.errors.append('Informe o vencedor ou um placar que defina quem venceu.')
                valido = False
        if status == StatusPartida.FINALIZADA and not placar:
            self.placar.errors.append('Informe o placar de uma partida finalizada.')
            valido = False
        self.vencedor_obj = vencedor
        return valido
