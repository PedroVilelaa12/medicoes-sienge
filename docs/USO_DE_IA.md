# Uso de IA neste desafio

> Ferramenta: Claude Code (modelo Claude Opus), no terminal, em 01/10/2026.
> O histórico completo da sessão fica salvo localmente em `~/.claude/projects/<projeto>/<sessão>.jsonl`. Ele não está versionado no repositório porque contém dados da conta, mas está disponível para mostrar na entrevista.

## Como a IA foi usada, passo a passo

| # | O que foi pedido | O que a IA fez | Como foi verificado |
|---|---|---|---|
| 1 | Ler o documento de contexto e explicar o que entendeu | Fez um resumo e apontou 3 riscos não explícitos no documento: o POST com itens (janela de "valor zero"), o timeout ambíguo na criação e a duplicidade por "mês atual" × competência | Revisão humana do resumo antes de seguir |
| 2 | Ler a documentação da API do Sienge | O contexto dizia que a documentação "bloqueia leitura automática". A IA descobriu que a página é um Swagger UI e baixou os **YAML oficiais**, que são públicos. Leu as specs de medições e de contratos **inteiras**, e as de parâmetros, fornecedores e webhooks | Cada rota do planejamento cita o arquivo e o campo da spec oficial ([PLANEJAMENTO §2](PLANEJAMENTO.md#2-o-que-a-api-oficial-do-sienge-permite-verificado)) |
| 3 | Planejar a entrega dentro do prazo | A primeira proposta (10 documentos e um ciclo formal de spec) era pesada demais; o Pedro apontou o prazo. A IA replanejou em etapas que terminam sempre em algo apresentável, cortando do fim | Decisão humana: prazo às 15:20; o planejamento é o centro, e o código e a tela são demonstrativos |
| 4 | Construir em paralelo | A IA principal escreveu o planejamento. Dois agentes com o mesmo contexto fizeram o núcleo em Python (com testes) e o protótipo da tela, cada um restrito às suas pastas e proibido de rodar git | A IA principal rodou de novo os 30 testes (todos passaram) e a demonstração. Também tirou screenshots da tela num Chrome sem interface. Um verificador automático de design apontou contraste baixo, texto pequeno e espaçamento apertado; os três foram corrigidos antes do commit |
| 5 | Leitura de documentos (fase 2) | O Pedro propôs tentar primeiro com Python e usar a IA só como fallback. A IA concordou e acrescentou dois cuidados: o gatilho para descer de camada é falhar na checagem (o Python também erra com confiança), e a cascata é decidida campo a campo | Registrado como decisão D14 e no PLANEJAMENTO §8.2; as proporções reais virão do benchmark |

## O que a verificação na fonte corrigiu ou acrescentou

- **Corrigido:** `/measurements/clearing` não é glosa, é a **liberação** da medição.
- **Corrigido:** `GET /supply-contracts` consulta **um** contrato. A lista é `/all` e não filtra por fornecedor.
- **Descoberto:** criar a medição já aceita os itens, então criar e lançar o valor são **uma só chamada**.
- **Descoberto:** a API mede em **quantidade com 4 casas decimais**, e "Valores monetários" não existe. Isso pode gerar diferença de centavos (nova validação V17).
- **Descoberto:** **não há rota de avaliação de fornecedor** para medições. Ela vira passo guiado (V19).
- **Descoberto:** o POST não aceita responsável, e há a opção de criar a medição desautorizada (`makeUnauthorized`).
- **Descoberto:** o Sienge recusa medição se houver **anteriores não finalizadas** (nova validação V14). Anexos têm limite de 70 MB, nome de até 100 caracteres e um arquivo por chamada, e o envio não devolve identificador.

## Onde a IA **não** decide

- **Rotas:** nenhuma foi inventada. O que não está na spec oficial aparece como lacuna ou pergunta.
- **Suposições:** tudo o que é suposição está marcado como [ASSUMIDO] ou [EM ABERTO] e listado como pergunta para a área.
- **Dinheiro:** sempre em `Decimal`, com testes nos casos do manual (saldo 288,74; bloqueio em 300,00; 264,66 → 264,64 quando o item é "1 vb").
- **No produto:** a IA não participa do lançamento. Na fase 2 ela só **lê** documentos. Regra decide, pessoa aprova (PLANEJAMENTO §8).

## O que eu revisaria com mais tempo

- Rodar o cliente HTTP contra a API simulada e comparar cada resposta com a spec oficial (PLANEJAMENTO §2.5).
- Revisar linha a linha o código gerado pelos agentes, com atenção especial à reconciliação de timeout e às mensagens para a usuária.
