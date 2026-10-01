"""Orquestrador: valida o lote, lança as medições prontas e confere cada uma no Sienge.

Uma medição que falha não interrompe as outras. A retomada continua do passo que falhou,
usando o número da medição já criada, e nunca cria a mesma medição duas vezes.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from medicoes.config import Config
from medicoes.dinheiro import formatar_br
from medicoes.dominio import Alerta, Anexo, Contrato, Etapa, PedidoMedicao, Severidade, Status
from medicoes.estado import RETOMAVEIS, Armazem, EstadoMedicao
from medicoes.regras.preenchimento import Relogio, agora_recife, escolher_obra, nome_para_envio
from medicoes.regras.validacoes import Contexto, Resultado, validar, validar_lote
from medicoes.sienge.cliente import ClienteSienge, ErroSienge, RespostaAmbigua

PASSO_CRIACAO = "criação da medição"
PASSO_ANEXOS = "envio dos anexos"
PASSO_CONFERENCIA = "conferência da totalização"


@dataclass
class Execucao:
    pedido: PedidoMedicao
    status: Status
    alertas: list[Alerta] = field(default_factory=list)
    passos: list[str] = field(default_factory=list)
    resultado: Resultado | None = None
    contrato: Contrato | None = None
    estado: EstadoMedicao | None = None
    numero_sienge: int | None = None
    passo_falha: str | None = None
    erro: str | None = None

    @property
    def retomavel(self) -> bool:
        return self.estado is not None and self.estado.etapa in RETOMAVEIS


class Imprevisto(Exception):
    """Situação ambígua: a ferramenta mostra e a usuária decide (V13)."""


def chave_idempotencia(contrato: str, obra_id: int, data: date, valor: Decimal, anexos: Sequence[Anexo]) -> str:
    base = "|".join([contrato, str(obra_id), data.isoformat(), str(valor), *sorted(a.hash for a in anexos)])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def carregar_contexto(cliente: ClienteSienge, pedido: PedidoMedicao) -> Contexto:
    """Passos 1 e 2: contrato, obras, itens e medições existentes (só leituras)."""
    if not pedido.contrato:
        return Contexto(None)
    documento, _, numero = pedido.contrato.partition("/")
    contrato = cliente.buscar_contrato(documento, numero)
    if contrato is None:
        return Contexto(None)
    obras = cliente.listar_obras(documento, numero)
    obra = escolher_obra(obras, pedido.obra_id)
    itens = []
    if obra is not None and len(obra.unidades) == 1:
        itens = cliente.listar_itens(documento, numero, obra.id, obra.unidades[0].id)
    return Contexto(contrato, obras, itens, cliente.listar_medicoes(documento, numero))


class Orquestrador:
    def __init__(
        self,
        cliente: ClienteSienge,
        armazem: Armazem | None = None,
        config: Config | None = None,
        relogio: Relogio | None = None,
    ):
        self.cliente = cliente
        self.armazem = armazem or Armazem()
        self.config = config or Config()
        self.relogio = relogio or agora_recife

    def processar_lote(self, pedidos: Sequence[PedidoMedicao], executar: bool = False) -> list[Execucao]:
        preparadas = self.preparar(pedidos)
        return self.lancar(preparadas) if executar else self.simular(preparadas)

    def preparar(self, pedidos: Sequence[PedidoMedicao]) -> list[Execucao]:
        """Valida tudo sem gravar nada. É o que a usuária vê antes de confirmar."""
        extras = validar_lote(pedidos)
        return [self._seguro(p, lambda p=p: self._preparar_um(p, extras[p.id])) for p in pedidos]

    def simular(self, execucoes: list[Execucao]) -> list[Execucao]:
        for e in execucoes:
            if e.status is Status.PRONTA:
                e.passos.append("Simulação: nada foi gravado no Sienge.")
        return execucoes

    def lancar(self, execucoes: list[Execucao]) -> list[Execucao]:
        """Lança as prontas e retoma as interrompidas, uma de cada vez e de forma independente."""
        return [
            self._seguro(e.pedido, lambda e=e: self._lancar_um(e), base=e)
            if e.status is Status.PRONTA or e.retomavel
            else e
            for e in execucoes
        ]

    def _preparar_um(self, pedido: PedidoMedicao, extras: list[Alerta]) -> Execucao:
        estado = self.armazem.obter(pedido.id)
        if estado is not None and estado.etapa is Etapa.CONFERIDA:
            return Execucao(
                pedido, Status.LANCADA, estado=estado, numero_sienge=estado.numero_sienge,
                passos=[f"Já lançada antes: medição nº {estado.numero_sienge}. Nada a fazer."],
            )
        if estado is not None and estado.etapa in RETOMAVEIS:
            return Execucao(
                pedido, Status.FALHOU, estado=estado, numero_sienge=estado.numero_sienge,
                passo_falha=estado.passo_falha, erro=estado.erro,
                passos=[f"Interrompida em {estado.passo_falha or 'andamento'}: será retomada de onde parou, sem criar outra medição."],
            )
        resultado = validar(pedido, carregar_contexto(self.cliente, pedido), self.config, self.relogio, extras)
        return Execucao(pedido, resultado.status, list(resultado.alertas), resultado=resultado, contrato=resultado.contrato)

    def _lancar_um(self, execucao: Execucao) -> Execucao:
        if execucao.estado is None:
            execucao.estado = self._confirmar(execucao)
        estado = execucao.estado
        pedido = execucao.pedido
        execucao.status, execucao.passo_falha, execucao.erro = Status.LANCANDO, None, None
        criar = estado.plano["criar_medicao"]
        documento = criar["query"]["documentId"]
        numero = criar["query"]["contractNumber"]
        obra_id = criar["query"]["buildingId"]

        # Passo 3: criar a medição, já com o valor. Uma única vez.
        if estado.numero_sienge is None:
            if estado.etapa is Etapa.CRIACAO_ENVIADA:
                estado.numero_sienge = self._reconciliar(estado, documento, numero, obra_id)
                if estado.numero_sienge is not None:
                    execucao.passos.append(
                        f"A medição nº {estado.numero_sienge} já tinha sido criada na tentativa anterior: nada foi criado de novo."
                    )
            if estado.numero_sienge is None:
                estado.etapa = Etapa.CRIACAO_ENVIADA
                self._salvar(estado, PASSO_CRIACAO, "enviado")  # grava antes do POST
                try:
                    estado.numero_sienge = self.cliente.criar_medicao(documento, numero, obra_id, criar["corpo"])
                except RespostaAmbigua as erro:
                    return self._falhou(
                        execucao, PASSO_CRIACAO,
                        "O Sienge não confirmou a criação da medição. Na próxima tentativa, a ferramenta confere "
                        "se ela foi criada antes de criar de novo.",
                        erro,
                    )
                except ErroSienge as erro:
                    if erro.status is not None and erro.status < 500:
                        estado.etapa = Etapa.CONFIRMADA  # recusa clara: nada foi gravado
                    return self._falhou(execucao, PASSO_CRIACAO, f"O Sienge recusou a criação da medição: {erro}", erro)
                execucao.passos.append(
                    f"Medição nº {estado.numero_sienge} criada com valor, data, vencimento e observação."
                )
            estado.etapa = Etapa.CRIADA
            self._salvar(estado, PASSO_CRIACAO, "ok", f"medição nº {estado.numero_sienge}")
        execucao.numero_sienge = estado.numero_sienge

        # Passo 6: anexos. Só os que ainda não estão no Sienge.
        if estado.etapa is Etapa.CRIADA:
            enviados = 0
            try:
                no_sienge = set(self.cliente.listar_anexos(
                    documento, numero, obra_id, estado.numero_sienge, date.fromisoformat(estado.data_medicao)
                ))
                for anexo in pedido.anexos:
                    nome = nome_para_envio(anexo.nome, self.config.limite_nome_anexo)
                    if (nome, anexo.tipo) in no_sienge:
                        continue
                    self.cliente.enviar_anexo(documento, numero, obra_id, estado.numero_sienge, anexo, nome)
                    estado.anexos_enviados.append(f"{anexo.tipo} {nome}")
                    self._salvar(estado, PASSO_ANEXOS, "ok", f"{anexo.tipo} {nome}")
                    enviados += 1
            except ErroSienge as erro:
                return self._falhou(
                    execucao, PASSO_ANEXOS,
                    f"Falhou o envio dos anexos ({erro}). Na próxima tentativa, só os anexos que faltam serão enviados.",
                    erro,
                )
            ja_estavam = len(pedido.anexos) - enviados
            execucao.passos.append(
                f"{enviados} anexo(s) enviado(s)" + (f"; {ja_estavam} já estava(m) no Sienge." if ja_estavam else ".")
            )
            estado.etapa = Etapa.ANEXOS_ENVIADOS
            self._salvar(estado, PASSO_ANEXOS, "ok")

        # Passo 7: ler a totalização e conferir com o valor lançado.
        try:
            medicao = self.cliente.ler_medicao(documento, numero, obra_id, estado.numero_sienge)
        except ErroSienge as erro:
            return self._falhou(execucao, PASSO_CONFERENCIA, f"Não consegui ler a totalização no Sienge ({erro}).", erro)
        valor = Decimal(estado.valor_efetivo)
        if medicao.valor_liquido != valor:
            diferenca = abs(medicao.valor_liquido - valor)
            execucao.alertas.append(Alerta(
                "V12", Severidade.ATENCAO,
                f"O total líquido no Sienge ficou {formatar_br(medicao.valor_liquido)}, diferente do valor lançado "
                f"({formatar_br(valor)}): diferença de {formatar_br(diferenca)}. Confira impostos e descontos na medição.",
                f"netValue={medicao.valor_liquido}",
            ))
        if not medicao.consistente:
            execucao.alertas.append(Alerta(
                "V19", Severidade.PENDENCIA,
                f"Falta a avaliação do fornecedor no Sienge. A API não permite registrá-la: abra a medição "
                f"nº {estado.numero_sienge} no Sienge e faça a avaliação para liberar o pagamento.",
                "consistent=false",
            ))
        estado.etapa = Etapa.CONFERIDA
        estado.passo_falha = estado.erro = None
        self._salvar(estado, PASSO_CONFERENCIA, "ok", f"netValue={medicao.valor_liquido}")
        execucao.passos.append(f"Totalização conferida no Sienge: total líquido {formatar_br(medicao.valor_liquido)}.")
        execucao.status = Status.LANCADA
        return execucao

    def _confirmar(self, execucao: Execucao) -> EstadoMedicao:
        """Congela data, valor e requisições, e grava a chave de idempotência antes de escrever no Sienge."""
        resultado, pedido = execucao.resultado, execucao.pedido
        dados = resultado.preenchimento
        estado = EstadoMedicao(
            pedido_id=pedido.id,
            chave=chave_idempotencia(
                pedido.contrato, dados.obra.id, dados.data_medicao, dados.conversao.valor_efetivo, pedido.anexos
            ),
            contrato=pedido.contrato,
            fornecedor=resultado.contrato.fornecedor,
            plano=resultado.plano,
            data_medicao=dados.data_medicao.isoformat(),
            valor_efetivo=str(dados.conversao.valor_efetivo),
        )
        anterior = self.armazem.por_chave(estado.chave)
        if anterior is not None and anterior.pedido_id != pedido.id and anterior.etapa is not Etapa.CONFIRMADA:
            numero = f"nº {anterior.numero_sienge}" if anterior.numero_sienge else "sem número confirmado"
            raise Imprevisto(
                f"Esta medição parece já ter sido lançada ({numero}): mesmo contrato, obra, data, valor e "
                "documentos. Confira no Sienge antes de lançar de novo."
            )
        self._salvar(estado, "confirmação", "ok", f"chave {estado.chave}")
        return estado

    def _reconciliar(self, estado: EstadoMedicao, documento: str, numero: str, obra_id: int) -> int | None:
        """Depois de um POST sem resposta, procura a medição no Sienge antes de criar de novo."""
        valor = Decimal(estado.valor_efetivo)
        candidatas = [
            m for m in self.cliente.listar_medicoes(documento, numero, obra_id)
            if m.data.isoformat() == estado.data_medicao and m.valor_bruto == valor
        ]
        if len(candidatas) > 1:
            numeros = ", ".join(f"nº {m.numero}" for m in candidatas)
            raise Imprevisto(
                f"Encontrei {len(candidatas)} medições iguais a esta no Sienge ({numeros}). "
                "Confira no Sienge qual é a correta antes de seguir."
            )
        return candidatas[0].numero if candidatas else None

    def _falhou(self, execucao: Execucao, passo: str, mensagem: str, erro: Exception) -> Execucao:
        estado = execucao.estado
        estado.passo_falha, estado.erro = passo, str(erro)
        self._salvar(estado, passo, "falha", str(erro))
        execucao.status, execucao.passo_falha, execucao.erro = Status.FALHOU, passo, str(erro)
        execucao.numero_sienge = estado.numero_sienge
        execucao.alertas.append(Alerta("V13", Severidade.ATENCAO, mensagem, repr(erro)))
        return execucao

    def _salvar(self, estado: EstadoMedicao, passo: str, resultado: str, mensagem: str = "") -> None:
        estado.registrar(passo, resultado, mensagem)
        self.armazem.salvar(estado)

    def _seguro(self, pedido: PedidoMedicao, funcao: Callable[[], Execucao], base: Execucao | None = None) -> Execucao:
        """V13: um imprevisto numa medição nunca derruba o lote, e nunca é resolvido sozinho."""
        try:
            return funcao()
        except Exception as erro:
            execucao = base or Execucao(pedido, Status.FALHOU)
            execucao.status, execucao.erro = Status.FALHOU, str(erro)
            mensagem = str(erro) if isinstance(erro, Imprevisto) else (
                "Aconteceu um imprevisto. Nada foi decidido sozinho: veja o detalhe e decida como seguir."
            )
            execucao.alertas.append(Alerta("V13", Severidade.ATENCAO, mensagem, repr(erro)))
            return execucao
