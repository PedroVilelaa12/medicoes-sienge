# CLAUDE.md: regras do projeto

> Vale para todas as pessoas e agentes de IA que trabalham neste repositório. Se algo aqui conflitar com um pedido, pare e pergunte ao tech lead.
>
> A fonte da verdade das regras de negócio e das decisões é o [`docs/PLANEJAMENTO.md`](docs/PLANEJAMENTO.md).

## O projeto em três linhas

- A usuária lança **as medições da semana de uma vez** no Sienge. Ela informa contrato, valor, observação e anexos, e a ferramenta faz o resto.
- O caminho é a **API REST oficial do Sienge**. Nada de RPA, de escrita no banco ou de agente de IA operando o Sienge (decisão D1).
- O que mais importa aqui é a **confiabilidade**: validar antes, nunca lançar em dobro, retomar de onde parou, conferir depois.

## Comandos

```bash
uv run --python 3.12 pytest -q                                   # testes: precisam estar verdes antes de qualquer PR
uv run --python 3.12 medicoes lancar exemplos/lote.json          # simulação (padrão): não grava nada
uv run --python 3.12 medicoes lancar exemplos/lote.json --executar [--falhar-em criacao|anexos|ambiguo]
uv run --python 3.12 medicoes limpar                             # zera o estado local da demonstração
open interface/index.html                                        # protótipo da tela
```

## Fronteiras da arquitetura (não atravessar)

| Camada | Pode | Não pode |
|---|---|---|
| `medicoes/regras/` | Calcular, preencher e validar com **funções puras** | Rede, disco, relógio do sistema (o relógio é injetado) |
| `medicoes/sienge/` | Ser a **única porta** para o Sienge | Conter regra de negócio |
| `medicoes/leitura/` | Extrair dados de documentos com regra determinística | Decidir ou chamar o Sienge; IA só como fallback (D14) |
| `medicoes/orquestrador.py` | Ser a **única camada que escreve** no Sienge | Decidir sozinho uma situação ambígua |
| `interface/` | Mostrar e coletar | Decidir. No produto, chama o serviço; as regras em JS existem só no protótipo |

## Regras invioláveis

1. **Dinheiro é sempre `Decimal`, nunca `float`.**
   - A entrada em formato brasileiro passa por `ler_valor_br`.
   - Valor ambíguo ("264.66") é recusado, não adivinhado.
2. **A API mede em quantidade com 4 casas decimais.** Sempre mostre o valor efetivo, e nunca arredonde sem avisar (V17).
3. **Nunca invente rota da API.**
   - Toda rota nova cita, na docstring, a spec oficial (`api.sienge.com.br/docs/yaml-files/<arquivo>.yaml` + operação).
   - Toda rota nova entra no mapa do PLANEJAMENTO §2.2.
4. **Escrita no Sienge nunca é repetida às cegas.**
   - Retentativa só em leitura, `429` e `5xx` de GET.
   - POST sem resposta → reconcilia antes de qualquer nova tentativa (§3.3).
5. **Antes de qualquer escrita, a chave de idempotência é gravada.** O número da medição é gravado assim que o Sienge responde.
6. **Dry-run é o padrão.** Executar exige a flag explícita `--executar`.
7. **Datas sempre com o fuso America/Recife.** A data da medição é congelada na confirmação.
8. **Situação ambígua vira alerta (V13), e quem decide é a usuária.** A ferramenta nunca escolhe sozinha.
9. **`makeUnauthorized = true` por padrão.** Quem lança não é quem autoriza (D4).
10. **IA não decide nada no lançamento.** Ela só lê documentos (fase 2, §8), sempre em cascata e com checagem cruzada (D14).

## Validações

- O catálogo V1 a V19 está no PLANEJAMENTO §5. As severidades são `BLOQUEIA`, `ATENCAO`, `FORA_MVP` e `PENDENCIA`.
- Uma validação nova exige:
  - um código V novo;
  - a mensagem para a usuária, em português simples e sem jargão;
  - o detalhe técnico, separado, só para o log;
  - um teste que dispara e um que não dispara;
  - uma linha no catálogo.

## Testes: definição de pronto

- **TDD** nas regras e no orquestrador: o teste que falha vem primeiro.
- **Todo bug corrigido ganha um teste que o reproduz.** Exemplos no histórico: o valor "264.66" e a duplicidade entre pedidos.
- No orquestrador, teste a **falha em cada passo de escrita** e a **retomada sem duplicar**.
- Testes sem rede (`ClienteFalso`) e com relógio fixo (`tests/apoio.py: relogio_fixo`).
- Nenhum PR sem `pytest` verde. Mostre a saída, não diga apenas "passou".

## Linguagem e estilo

- Identificadores em português sem acento (`medicao`, `contrato`, `valor_efetivo`).
- Mensagens para a usuária em português correto, com acentos e **sem termos técnicos** ("API", "payload", "request").
- Comentários só onde a regra de negócio não é óbvia. Cite o ID da validação (V8) ou da decisão (D5).
- Funções pequenas, cada uma com um propósito. Siga o estilo do arquivo que você está editando.

## Segurança e LGPD

- Credenciais só no `.env`, que fica fora do git. O `.env.example` não tem valores.
- Logs e auditoria nunca guardam senha, token, CPF ou conteúdo de documento.
- **Nunca versione documentos reais** (NF, boleto, contrato) nem dados de pessoas. Use só os dados fictícios de `medicoes/sienge/falso.py` e `interface/dados.js`.
- O usuário de API tem permissão mínima: só ler contratos e medições, criar medição e enviar anexo. Nunca autorizar ou reprovar.

## Fluxo de trabalho da equipe

- **Branch por tarefa:** `feat/…`, `fix/…`, `docs/…`, `test/…`.
- **Commits pequenos, em português:** `tipo: descrição` (`feat`, `fix`, `docs`, `test`, `refactor`).
- **Todo PR traz:**
  - o que muda e por quê;
  - como testar;
  - o impacto em regras ou validações.
- **Quando o PR muda regra ou decisão, ele também atualiza o PLANEJAMENTO.** Decisão nova vira linha na tabela da §7.
- **Revisão:** pelo menos 1 pessoa. Mudanças em `orquestrador.py`, `dinheiro.py` ou `sienge/` pedem 2.
- **Dúvida de regra de negócio vira pergunta para a área** (PLANEJAMENTO §10), nunca suposição escondida no código.

## Ao usar IA (Claude Code) neste repositório

- Leia este arquivo e a seção relevante do PLANEJAMENTO antes de mudar qualquer regra.
- Verifique na fonte (a spec oficial do Sienge) antes de afirmar algo sobre a API.
- Rode os testes antes de dizer que terminou, e mostre a saída.
- Decisões relevantes tomadas com ajuda de IA são registradas em [`docs/USO_DE_IA.md`](docs/USO_DE_IA.md).
