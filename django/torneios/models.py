import re

from django.conf import settings
from django.db import models
from django.urls import reverse

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


class Torneio(models.Model):
    class Formato(models.TextChoices):
        ELIMINATORIA = 'ELIM', 'Eliminatória simples'
        ROUND_ROBIN = 'RR', 'Round-robin (todos contra todos)'
        GRUPOS = 'GRUPOS', 'Grupos + mata-mata'

    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        INSCRICOES = 'INSCRICOES', 'Inscrições abertas'
        EM_ANDAMENTO = 'ANDAMENTO', 'Em andamento'
        FINALIZADO = 'FINALIZADO', 'Finalizado'
        CANCELADO = 'CANCELADO', 'Cancelado'

    nome = models.CharField(max_length=150)
    descricao = models.TextField('descrição', blank=True)
    data_torneio = models.DateField('data do torneio')
    local = models.CharField('local (clube)', max_length=150)
    formato = models.CharField(max_length=10, choices=Formato.choices, default=Formato.ELIMINATORIA)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RASCUNHO)
    premiacao = models.CharField('premiação', max_length=255, blank=True)
    regulamento = models.TextField(blank=True)
    regulamento_arquivo = models.FileField('arquivo do regulamento', upload_to='regulamentos/', blank=True)
    organizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='torneios_organizados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_torneio', 'nome']

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse('torneio_detalhe', args=[self.pk])

    @property
    def aceita_inscricoes(self):
        return self.status in (self.Status.RASCUNHO, self.Status.INSCRICOES) and not self.partidas.exists()


class Jogador(models.Model):
    nome = models.CharField(max_length=150)
    foto = models.ImageField(upload_to='jogadores/', blank=True)

    class Meta:
        ordering = ['nome']
        verbose_name_plural = 'jogadores'

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse('jogador_detalhe', args=[self.pk])

    @property
    def iniciais(self):
        partes = self.nome.split()
        return ''.join(p[0] for p in partes[:2]).upper()


class Inscricao(models.Model):
    torneio = models.ForeignKey(Torneio, on_delete=models.CASCADE, related_name='inscricoes')
    jogador = models.ForeignKey(Jogador, on_delete=models.CASCADE, related_name='inscricoes')
    cabeca_de_chave = models.PositiveSmallIntegerField('cabeça de chave', null=True, blank=True)
    grupo = models.CharField(max_length=2, blank=True)
    data_inscricao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [models.F('cabeca_de_chave').asc(nulls_last=True), 'jogador__nome']
        verbose_name = 'inscrição'
        verbose_name_plural = 'inscrições'
        constraints = [
            models.UniqueConstraint(fields=['torneio', 'jogador'], name='inscricao_unica_por_torneio'),
        ]

    def __str__(self):
        if self.cabeca_de_chave:
            return f'{self.jogador.nome} [{self.cabeca_de_chave}]'
        return self.jogador.nome


class Partida(models.Model):
    class Rodada(models.TextChoices):
        TODOS = 'RR', 'Todos contra todos'
        GRUPOS = 'GR', 'Fase de grupos'
        R32 = 'R32', 'Primeira rodada (R32)'
        R16 = 'R16', 'Oitavas de final'
        QF = 'QF', 'Quartas de final'
        SF = 'SF', 'Semifinal'
        F = 'F', 'Final'

    class Status(models.TextChoices):
        AGENDADA = 'AGENDADA', 'Agendada'
        EM_ANDAMENTO = 'ANDAMENTO', 'Em andamento'
        FINALIZADA = 'FINALIZADA', 'Finalizada'
        WO = 'WO', 'W.O.'
        ABANDONO = 'ABANDONO', 'Abandono'

    ENCERRADOS = (Status.FINALIZADA, Status.WO, Status.ABANDONO)
    MATA_MATA = (Rodada.R32, Rodada.R16, Rodada.QF, Rodada.SF, Rodada.F)

    torneio = models.ForeignKey(Torneio, on_delete=models.CASCADE, related_name='partidas')
    rodada = models.CharField(max_length=3, choices=Rodada.choices)
    posicao = models.PositiveSmallIntegerField('posição na rodada', default=0)
    grupo = models.CharField(max_length=2, blank=True)
    jornada = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text='Número da rodada na fase de todos contra todos.'
    )
    inscricao_1 = models.ForeignKey(
        Inscricao, on_delete=models.CASCADE, null=True, blank=True, related_name='partidas_como_1'
    )
    inscricao_2 = models.ForeignKey(
        Inscricao, on_delete=models.CASCADE, null=True, blank=True, related_name='partidas_como_2'
    )
    data_hora = models.DateTimeField('data e hora', null=True, blank=True)
    placar = models.CharField(max_length=50, blank=True, help_text='Ex.: 6-4 3-6 10-7')
    vencedor = models.ForeignKey(
        Inscricao, on_delete=models.SET_NULL, null=True, blank=True, related_name='vitorias'
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AGENDADA)
    proxima_partida = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='partidas_anteriores'
    )

    class Meta:
        ordering = ['torneio', 'grupo', 'jornada', 'posicao']

    def __str__(self):
        return f'{self.get_rodada_display()}: {self.nome_1} x {self.nome_2}'

    @property
    def encerrada(self):
        return self.status in self.ENCERRADOS

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
    def editavel(self):
        """Uma partida só pode ser alterada se a seguinte ainda não foi decidida."""
        if self.is_bye or self.torneio.status == Torneio.Status.CANCELADO:
            return False
        if self.rodada == self.Rodada.GRUPOS:
            # Depois de gerado o mata-mata, a classificação dos grupos fica congelada.
            return not self.torneio.partidas.filter(rodada__in=self.MATA_MATA).exists()
        return not (self.proxima_partida and self.proxima_partida.encerrada)
