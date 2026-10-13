import re
from datetime import date, datetime
from typing import Optional

from flask import url_for
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db

PLACAR_SET_RE = re.compile(r'^(\d{1,2})-(\d{1,2})(?:\((\d{1,2})\))?$')


def parse_placar(placar):
    """Converte "6-4 3-6 7-6(5)" em [(6, 4, None), (3, 6, None), (7, 6, 5)].

    Levanta ValueError se algum set estiver em formato inválido.
    """
    sets = []
    for parte in (placar or '').split():
        match = PLACAR_SET_RE.match(parte)
        if not match:
            raise ValueError(f'Set inválido: "{parte}". Use o formato 6-4 ou 7-6(5).')
        g1, g2, tb = match.groups()
        sets.append((int(g1), int(g2), int(tb) if tb else None))
    return sets


class Choices:
    """Valores fixos de um campo, com rótulo para exibição (como os choices do Django)."""
    LABELS: dict = {}

    @classmethod
    def choices(cls):
        return list(cls.LABELS.items())

    @classmethod
    def label(cls, valor):
        return cls.LABELS.get(valor, valor)


class Formato(Choices):
    ELIMINATORIA = 'ELIM'
    ROUND_ROBIN = 'RR'
    GRUPOS = 'GRUPOS'
    LABELS = {
        ELIMINATORIA: 'Eliminatória simples',
        ROUND_ROBIN: 'Round-robin (todos contra todos)',
        GRUPOS: 'Grupos + mata-mata',
    }


class StatusTorneio(Choices):
    RASCUNHO = 'RASCUNHO'
    INSCRICOES = 'INSCRICOES'
    EM_ANDAMENTO = 'ANDAMENTO'
    FINALIZADO = 'FINALIZADO'
    CANCELADO = 'CANCELADO'
    LABELS = {
        RASCUNHO: 'Rascunho',
        INSCRICOES: 'Inscrições abertas',
        EM_ANDAMENTO: 'Em andamento',
        FINALIZADO: 'Finalizado',
        CANCELADO: 'Cancelado',
    }


class Rodada(Choices):
    TODOS = 'RR'
    GRUPOS = 'GR'
    R32 = 'R32'
    R16 = 'R16'
    QF = 'QF'
    SF = 'SF'
    F = 'F'
    LABELS = {
        TODOS: 'Todos contra todos',
        GRUPOS: 'Fase de grupos',
        R32: 'Primeira rodada (R32)',
        R16: 'Oitavas de final',
        QF: 'Quartas de final',
        SF: 'Semifinal',
        F: 'Final',
    }
    MATA_MATA = (R32, R16, QF, SF, F)


class StatusPartida(Choices):
    AGENDADA = 'AGENDADA'
    EM_ANDAMENTO = 'ANDAMENTO'
    FINALIZADA = 'FINALIZADA'
    WO = 'WO'
    ABANDONO = 'ABANDONO'
    LABELS = {
        AGENDADA: 'Agendada',
        EM_ANDAMENTO: 'Em andamento',
        FINALIZADA: 'Finalizada',
        WO: 'W.O.',
        ABANDONO: 'Abandono',
    }
    ENCERRADOS = (FINALIZADA, WO, ABANDONO)


class Usuario(db.Model):
    """Organizador de torneios (sem login no MVP)."""
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))

    torneios: Mapped[list['Torneio']] = relationship(back_populates='organizador', passive_deletes=True)

    def __str__(self):
        return self.nome


class Torneio(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    descricao: Mapped[str] = mapped_column(Text, default='')
    data_torneio: Mapped[date]
    local: Mapped[str] = mapped_column(String(150))
    formato: Mapped[str] = mapped_column(String(10), default=Formato.ELIMINATORIA)
    status: Mapped[str] = mapped_column(String(12), default=StatusTorneio.RASCUNHO)
    premiacao: Mapped[str] = mapped_column(String(255), default='')
    regulamento: Mapped[str] = mapped_column(Text, default='')
    regulamento_arquivo: Mapped[str] = mapped_column(String(255), default='')
    organizador_id: Mapped[Optional[int]] = mapped_column(ForeignKey('usuario.id', ondelete='SET NULL'))
    criado_em: Mapped[datetime] = mapped_column(default=datetime.now)

    organizador: Mapped[Optional[Usuario]] = relationship(back_populates='torneios')
    inscricoes: Mapped[list['Inscricao']] = relationship(
        back_populates='torneio', cascade='all, delete-orphan', passive_deletes=True
    )
    partidas: Mapped[list['Partida']] = relationship(
        back_populates='torneio', cascade='all, delete-orphan', passive_deletes=True,
        order_by=lambda: (Partida.grupo, Partida.jornada, Partida.posicao),
    )

    def __str__(self):
        return self.nome

    @property
    def url(self):
        return url_for('torneios.detalhe', torneio_id=self.id)

    @property
    def formato_label(self):
        return Formato.label(self.formato)

    @property
    def status_label(self):
        return StatusTorneio.label(self.status)

    @property
    def aceita_inscricoes(self):
        return self.status in (StatusTorneio.RASCUNHO, StatusTorneio.INSCRICOES) and not self.partidas

    @property
    def inscritos(self):
        """Inscrições ordenadas: cabeças de chave primeiro, depois por nome."""
        return sorted(
            self.inscricoes,
            key=lambda i: (i.cabeca_de_chave is None, i.cabeca_de_chave or 0, i.jogador.nome),
        )


class Jogador(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    foto: Mapped[str] = mapped_column(String(255), default='')

    inscricoes: Mapped[list['Inscricao']] = relationship(
        back_populates='jogador', cascade='all, delete-orphan', passive_deletes=True
    )

    def __str__(self):
        return self.nome

    @property
    def url(self):
        return url_for('jogadores.detalhe', jogador_id=self.id)

    @property
    def iniciais(self):
        return ''.join(p[0] for p in self.nome.split()[:2]).upper()


class Inscricao(db.Model):
    __table_args__ = (UniqueConstraint('torneio_id', 'jogador_id', name='inscricao_unica_por_torneio'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    torneio_id: Mapped[int] = mapped_column(ForeignKey('torneio.id', ondelete='CASCADE'))
    jogador_id: Mapped[int] = mapped_column(ForeignKey('jogador.id', ondelete='CASCADE'))
    cabeca_de_chave: Mapped[Optional[int]]
    grupo: Mapped[str] = mapped_column(String(2), default='')
    data_inscricao: Mapped[datetime] = mapped_column(default=datetime.now)

    torneio: Mapped[Torneio] = relationship(back_populates='inscricoes')
    jogador: Mapped[Jogador] = relationship(back_populates='inscricoes')

    def __str__(self):
        if self.cabeca_de_chave:
            return f'{self.jogador.nome} [{self.cabeca_de_chave}]'
        return self.jogador.nome


class Partida(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    torneio_id: Mapped[int] = mapped_column(ForeignKey('torneio.id', ondelete='CASCADE'))
    rodada: Mapped[str] = mapped_column(String(3))
    posicao: Mapped[int] = mapped_column(default=0)
    grupo: Mapped[str] = mapped_column(String(2), default='')
    jornada: Mapped[Optional[int]]
    inscricao_1_id: Mapped[Optional[int]] = mapped_column(ForeignKey('inscricao.id', ondelete='CASCADE'))
    inscricao_2_id: Mapped[Optional[int]] = mapped_column(ForeignKey('inscricao.id', ondelete='CASCADE'))
    data_hora: Mapped[Optional[datetime]]
    placar: Mapped[str] = mapped_column(String(50), default='')
    vencedor_id: Mapped[Optional[int]] = mapped_column(ForeignKey('inscricao.id', ondelete='SET NULL'))
    status: Mapped[str] = mapped_column(String(10), default=StatusPartida.AGENDADA)
    proxima_partida_id: Mapped[Optional[int]] = mapped_column(ForeignKey('partida.id', ondelete='SET NULL'))

    torneio: Mapped[Torneio] = relationship(back_populates='partidas')
    inscricao_1: Mapped[Optional[Inscricao]] = relationship(foreign_keys=[inscricao_1_id])
    inscricao_2: Mapped[Optional[Inscricao]] = relationship(foreign_keys=[inscricao_2_id])
    vencedor: Mapped[Optional[Inscricao]] = relationship(foreign_keys=[vencedor_id])
    proxima_partida: Mapped[Optional['Partida']] = relationship(remote_side=[id], post_update=True)

    def __str__(self):
        return f'{self.rodada_label}: {self.nome_1} x {self.nome_2}'

    @property
    def rodada_label(self):
        return Rodada.label(self.rodada)

    @property
    def status_label(self):
        return StatusPartida.label(self.status)

    @property
    def encerrada(self):
        return self.status in StatusPartida.ENCERRADOS

    @property
    def is_bye(self):
        return self.placar == 'BYE'

    @property
    def nome_1(self):
        return self._nome(self.inscricao_1)

    @property
    def nome_2(self):
        return self._nome(self.inscricao_2)

    def _nome(self, inscricao):
        if inscricao:
            return inscricao.jogador.nome
        return 'BYE' if self.is_bye else 'A definir'

    @property
    def sets(self):
        if self.is_bye:
            return []
        try:
            return parse_placar(self.placar)
        except ValueError:
            return []

    @property
    def sets_vencidos(self):
        """Sets ganhos por cada jogador, ex.: (2, 1). Ao vivo, o set em disputa não conta."""
        sets = self.sets
        if self.status == StatusPartida.EM_ANDAMENTO:
            sets = sets[:-1]
        return sum(g1 > g2 for g1, g2, _ in sets), sum(g2 > g1 for g1, g2, _ in sets)

    @property
    def editavel(self):
        """Uma partida só pode ser alterada se a seguinte ainda não foi decidida."""
        if self.is_bye or self.torneio.status == StatusTorneio.CANCELADO:
            return False
        if self.rodada == Rodada.GRUPOS:
            # Depois de gerado o mata-mata, a classificação dos grupos fica congelada.
            return not any(p.rodada in Rodada.MATA_MATA for p in self.torneio.partidas)
        return not (self.proxima_partida and self.proxima_partida.encerrada)
