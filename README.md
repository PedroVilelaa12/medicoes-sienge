# Medições em lote no Sienge

> Desafio técnico · Grupo Baptista Leal · Núcleo de Desenvolvimento, Dados e Inovação · Etapa 3

Hoje, cada medição de contrato é lançada à mão no Sienge, uma por uma, em cerca de 12 etapas. Só 4 informações mudam de uma medição para outra. A proposta é uma ferramenta em que a usuária **lança as medições da semana de uma vez**. Ela informa apenas **contrato, valor, observação e anexos**, e a ferramenta:

- preenche o resto;
- valida antes de lançar;
- lança pela **API oficial do Sienge**;
- confere depois e entrega um comprovante.

Nada é gravado sem confirmação explícita.

Este repositório é o **primeiro passo**. O planejamento está completo; o núcleo funciona contra um Sienge simulado e a tela é um protótipo navegável. O que não deu tempo está listado abaixo.

## Por onde começar

| Leia | Para |
|---|---|
| [`docs/PLANEJAMENTO.md`](docs/PLANEJAMENTO.md) | Entender a solução inteira: o que a API do Sienge permite (verificado na spec oficial), a arquitetura, as regras, as validações, a interface, as decisões, a fase 2 (leitura de documentos), as perguntas para a área e o roadmap |
| [`docs/CONTEXTO_automacao_medicoes.md`](docs/CONTEXTO_automacao_medicoes.md) | Ver o processo atual e as decisões das Etapas 1 e 2 (insumo de partida) |
| [`docs/USO_DE_IA.md`](docs/USO_DE_IA.md) | Saber como a IA foi usada, o que foi verificado e o que foi corrigido |
| [`interface/index.html`](interface/index.html) | Ver a tela de lote (abre com duplo clique) |

## O que a leitura da API mudou

O que não está no documento de contexto, mas está na documentação oficial do Sienge (detalhes no [PLANEJAMENTO §2](docs/PLANEJAMENTO.md#2-o-que-a-api-oficial-do-sienge-permite-verificado)):

1. **Criar a medição e lançar o valor é uma chamada só.** Deixa de existir a "medição criada com valor zero".
2. **A API mede em quantidade, não em reais.** A ferramenta converte o valor e, quando sobra diferença de centavos, mostra o valor efetivo e pede decisão.
3. **Não há rota para a avaliação do fornecedor.** Ela vira um passo guiado, com link para o Sienge e pendência até ser feita.
4. **O responsável não é aceito pela API.** A auditoria da ferramenta registra quem lançou cada medição.
5. **A medição pode nascer desautorizada.** Assim quem lança continua sendo diferente de quem autoriza.

## Como rodar

Requisito: [`uv`](https://docs.astral.sh/uv/). O Python 3.12 é instalado automaticamente.

```bash
uv run --python 3.12 pytest -q                                        # testes
uv run --python 3.12 medicoes lancar exemplos/lote.json               # simulação: mostra o que SERIA lançado
uv run --python 3.12 medicoes lancar exemplos/lote.json --executar    # lança no Sienge simulado
uv run --python 3.12 medicoes lancar exemplos/lote.json --executar --falhar-em anexos   # falha e retomada sem duplicar
open interface/index.html                                             # protótipo da tela
```

## Estrutura

```
docs/            planejamento, contexto e uso de IA
medicoes/        núcleo em Python (só biblioteca padrão)
  dinheiro.py      Decimal, formato brasileiro, conversão valor ↔ quantidade
  dominio.py       modelos, status, alertas
  regras/          preenchimento e validações V1–V19 (funções puras, sem rede)
  sienge/          interface do cliente (uma função por rota verificada) e Sienge simulado
  orquestrador.py  passos, idempotência, reconciliação de timeout, retomada
  estado.py        estado do lote em arquivo (SQLite no roadmap)
  cli.py           medicoes lancar lote.json [--executar]
tests/           critérios de aceite do contexto e casos novos da API
exemplos/        lote de exemplo
interface/       protótipo da tela de lote (HTML, CSS e JS, sem build)
```

## Status

**Feito**
- Planejamento completo, com o mapa "etapa → rota" verificado na spec oficial do Sienge e 19 validações com as mensagens para a usuária.
- Núcleo: regras, conversão de valores, orquestrador com idempotência e retomada, Sienge simulado com falhas injetáveis, CLI em dry-run e testes.
- Protótipo da tela de lote: soltar documentos, juntar cards, completar, lançar prontas e comprovante.

**Ainda não feito, e por quê**
- **Cliente HTTP real testado contra uma API.** Não havia API simulada nem credencial disponíveis. As rotas estão mapeadas e documentadas, e só esse módulo muda quando houver acesso.
- **Serviço web ligando a tela ao núcleo.** No protótipo, a tela replica as regras em JavaScript só para demonstrar o fluxo.
- **Banco SQLite, login corporativo e auditoria persistente.** Estão no roadmap (semana 2).
- **Leitura automática dos documentos (OCR/IA).** É a fase 2. O estudo das opções e o plano de avaliação estão no [PLANEJAMENTO §8](docs/PLANEJAMENTO.md#8-fase-2--leitura-automática-dos-documentos-estudo).

**Próximos passos:** responder às perguntas da área ([PLANEJAMENTO §10](docs/PLANEJAMENTO.md#10-perguntas-para-a-área-por-prioridade)), rodar em dry-run sobre 20 medições antigas e comparar com o lançamento manual.
