# Automação de Medições de Contratos no Sienge — Contexto para brainstorm, spec e desenvolvimento

> **Para o Claude Code:** este documento reúne tudo o que já foi levantado e decidido. Use-o como insumo do brainstorm (superpowers), não como spec final.
>
> Cada informação está marcada como **[DECIDIDO]**, **[ASSUMIDO]** ou **[EM ABERTO]**. Não trate o que é assumido ou em aberto como fato: pergunte antes. **Nunca invente rotas de API:** leia a documentação e a API simulada antes de escrever o cliente HTTP.

---

## 0. Contexto do desafio (restrições reais de tempo e escopo)

- Desafio técnico do Grupo Baptista Leal (construção civil, Recife), Núcleo de Desenvolvimento, Dados e Inovação. O Sienge é o ERP.
- Hoje as medições de contratos são lançadas manualmente no Sienge, uma por uma.
- As Etapas 1 (entender o processo) e 2 (proposta) já foram concluídas. Este documento prepara a **Etapa 3: construir o primeiro passo em 55 minutos.** Não precisa terminar, mas precisa mostrar caminho e qualidade.
- Depois vêm a Etapa 4 (revisão de código de um PR de outra pessoa) e a Etapa 5 (apresentação de 10 minutos mais conversa).
- Linguagem: Python ou TypeScript. **[ASSUMIDO]** Python 3.11+.
- **Não há acesso ao Sienge real.** Para a Etapa 3 recebemos:
  - dados fictícios de contratos;
  - alguns PDFs de nota fiscal e boleto;
  - uma **API simulada com as rotas de medição**.
- A banca valoriza: boas perguntas antes de soluções, decisões explicadas (inclusive o que ficou de fora), uso crítico de IA, clareza para não técnicos e honestidade sobre o que não deu tempo.
- O histórico de uso de IA deve ser guardado, porque será discutido na entrevista.

---

## 1. Problema e objetivo

**Problema:** cada medição exige cerca de 12 etapas manuais no Sienge. O caminho passa pela tela nova, pela tela antiga, por uma janela separada de avaliação de fornecedor e pela aba de anexos. Só 4 informações mudam de uma medição para outra; as outras 8 etapas repetem dados que o Sienge já tem ou seguem regras fixas. As medições se acumulam e são lançadas em sequência, por exemplo numa segunda-feira.

**Objetivo:** a usuária lança **todas as medições da semana de uma vez**, informando só o que muda, e **confia** que foram lançadas certas.

**Princípios [DECIDIDO]:**
- **Simples:** poucos campos, e tudo o que o Sienge já sabe é preenchido pela ferramenta.
- **Intuitivo:** linguagem da usuária, sem termos técnicos; ela vê o que vai ser lançado antes de lançar.
- **Confiável:** valida antes, confirma depois, nunca lança em dobro, retoma de onde parou e entrega um comprovante.
- **Todo imprevisto é relatado à usuária, e ela decide.** A ferramenta nunca resolve sozinha uma situação ambígua. Cada imprevisto novo descoberto no uso vira um alerta mapeado.

---

## 2. Processo atual (como a usuária faz hoje)

Caminho no Sienge: **Suprimentos › Contratos e Medições › Medições › Cadastros**.

| # | Etapa | O que ela faz | Na automação |
|---|---|---|---|
| 1 | Login | Entra com Sienge ID | Usuário de API dedicado |
| 2 | Abrir Medições › Cadastros | Navegação | Não se aplica |
| 3 | Consulta de medições | Filtra pelo contrato (sempre com o prefixo "CT/") | Vira **checagem automática** (duplicidade, autorização, medições posteriores) |
| 4 | Nova medição: contrato | Escolhe o CT | **Usuária informa** |
| 5 | Obra, fornecedor, responsável, data | A obra é filtrada pelo contrato; o fornecedor vem preenchido | Automático (regras na seção 4) |
| 6 | Data de vencimento | Digita | Automático: hoje + 15 dias |
| 7 | Observação | Digita | **Usuária informa** (com sugestão pré-preenchida) |
| 8 | Avaliação do fornecedor | Tela antiga › aba Itens › botão Avaliação. Remove todos os critérios padrão, clica em Adicionar, seleciona os 4 de sempre, salva e fecha | Automático |
| 9 | Entrada dos valores | Troca o dropdown para "Valores monetários" | Automático (sempre esse valor) |
| 10 | Valor medido | Abre a unidade construtiva (ícone de lápis) e digita o "Valor medido" no item | **Usuária informa o valor**; o item é escolhido por regra |
| 11 | Totalização | Confere o total líquido. "Quando aparecem os valores, é porque foi para o ZEPP" (sistema de pagamento) | Conferência automática |
| 12 | Anexos | Aba Anexos › Adicionar › escolhe o arquivo › escreve a descrição (BOLETO, NF, CONTRATO ou PROPOSTA) › salva | **Usuária anexa e escolhe o tipo**; o envio é automático |

O "Método de medição" na tela nova é "Medição manual". O campo "Período (data inicial e final)" é opcional e não é usado.

Avisos que o Sienge mostra e que precisamos antecipar como validação:
- "O contrato da medição está desautorizado."
- "Existem medições posteriores liberadas, só será permitido alterar o período e a observação."
- "Esta medição está incompleta: valor da medição igual a zero." Acontece quando a medição é criada mas o valor não é lançado; é exatamente a falha que o orquestrador precisa evitar.
- "Esta medição não possui nenhum anexo."

---

## 3. Escopo do MVP

### Dentro [DECIDIDO]
- Lançamento completo de medições de **contratos simples**, **em lote**.
- A usuária informa 4 coisas por medição: **contrato, valor, observação e anexos**.
- A ferramenta faz o resto: obra (se for única), fornecedor, responsável, datas, avaliação, tipo de entrada, item, conferência da totalização e envio de anexos.
- Nada é gravado no Sienge sem a confirmação explícita da usuária.

### Fora do MVP [DECIDIDO]
- Reajustes e a aba Índices. Mesmo que a observação mencione reajuste, a automação não trata isso.
- Contratos com retenções, caução ou impostos. A própria tela nova do Sienge só aceita medições sem retenção. A ferramenta detecta, avisa e o caso segue pelo caminho manual.
- Contratos com mais de uma unidade construtiva: detecta, avisa e segue manual.
- Autorização e liberação da medição, que são decisões de outras pessoas.
- Leitura automática dos documentos (é a fase 2, seção 9).
- Entrada por planilha (fase 2).

---

## 4. Regras de negócio

| Campo | Origem | Regra | Status |
|---|---|---|---|
| Contrato | Usuária | Busca pelo número (CT/…) **ou pelo nome do fornecedor**, porque é o que aparece no documento | DECIDIDO |
| Obra | Ferramenta | Busca as obras do contrato. Se houver 1, seleciona sozinha e mostra. Se houver várias, a usuária escolhe. Se houver 0, bloqueia | DECIDIDO |
| Fornecedor | Ferramenta | Vem do contrato | DECIDIDO |
| Responsável | Ferramenta | A pessoa que está usando a ferramenta, mapeada para o usuário do Sienge (ex.: "AVITORIA") | ASSUMIDO: como mapear login → usuário Sienge está em aberto |
| Data da medição | Ferramenta | Hoje (fuso America/Recife) | DECIDIDO |
| Data de vencimento | Ferramenta | **Hoje + 15 dias corridos** | DECIDIDO (15 dias). Fim de semana ou feriado: EM ABERTO, padrão sem ajuste |
| Observação | Usuária | Pré-preenchida com um modelo editável, por exemplo "Referente aos serviços prestados pelo {fornecedor} - {Mês}/{AAAA}" (formato do manual). O Sienge tem o parâmetro 843 de observação padrão | DECIDIDO (editável). O texto exato está EM ABERTO |
| Método de medição | Ferramenta | Medição manual | DECIDIDO |
| Avaliação do fornecedor | Ferramenta | Remove os critérios padrão e inclui os 4 critérios fixos | Quais são os 4 e as notas (no manual aparecem todas 10,0): EM ABERTO. Deve ser configurável |
| Entrada dos valores | Ferramenta | Sempre "Valores monetários" | DECIDIDO. O equivalente na API está EM ABERTO |
| Item que recebe o valor | Ferramenta | **O item mais recente do contrato** | DECIDIDO. O critério exato ("mais recente" = último aditivo? maior referência?) e o que fazer se ele não tiver saldo estão EM ABERTO |
| Valor medido | Usuária | Digitado, maior que zero e menor ou igual ao saldo do item | DECIDIDO |
| Totalização | Ferramenta | Confere se o total líquido é igual ao valor lançado | DECIDIDO |
| Anexos | Usuária | Ela anexa e escolhe o tipo; a descrição no Sienge é o tipo (BOLETO, NF, CONTRATO, PROPOSTA) | DECIDIDO. Se é obrigatório ter anexo: EM ABERTO (o manual sugere que pode ser aprovado sem) |

**Saldo do item** = valor contratado − acumulado anterior.

### Exemplo real do manual (útil como fixture de teste)

- **Contrato CT/1241**, obra 480 "START RECIFE ESTR. DA MUMBECA (COMERCIAL)", unidade construtiva 1, medição nº 25 em 17/06/2026.
- Itens do contrato:

| Item | Descrição | Aditivo | Preço / valor contratado | Acumulado anterior | Valor medido |
|---|---|---|---|---|---|
| 00.000.000.001 | Mensalidade de Software | não | 3.042,36 | 2.788,83 | 0,00 |
| 00.000.000.002 | Mensalidade de Software | sim | 3.200,00 | 2.911,26 | **264,66** |

- O valor foi lançado no item 002 (aditivo, o mais recente). O saldo do item 002 é 288,74, então 264,66 é válido.
- Na totalização: total medido de material 264,66 e total líquido 264,66, com caução, permuta, sinal, descontos e impostos zerados.
- **Outro exemplo:** contrato CT/154, obra 56 "ESCRITORIO CENTRAL - C.S.C (ADM)", fornecedor 1776 METADADOS, responsável Alessandra Vitoria.

---

## 5. Validações e mensagens (o coração da confiabilidade)

Cada validação gera uma mensagem **na linguagem da usuária**, explicando o motivo e o que fazer.

| ID | Validação | Quando | Efeito |
|---|---|---|---|
| V1 | Contrato existe e está autorizado | Ao escolher o contrato | Bloqueia |
| V2 | Obras do contrato: 0, 1 ou várias | Ao escolher o contrato | 0 bloqueia; 1 preenche sozinha; várias, a usuária escolhe |
| V3 | Contrato tem retenção, caução ou impostos | Ao escolher o contrato | "Fora do MVP": avisa e marca para o caminho manual |
| V4 | Contrato tem mais de uma unidade construtiva | Ao escolher o contrato | Mesmo tratamento do V3 |
| V5 | Já existe medição desse contrato no mês atual | Antes de confirmar | Alerta forte; só segue com confirmação explícita |
| V6 | Existem medições posteriores liberadas | Antes de confirmar | Bloqueia |
| V7 | Ordem cronológica: a data de hoje é maior ou igual à da última medição do contrato | Antes de confirmar | Bloqueia |
| V8 | Valor maior que zero e menor ou igual ao saldo do item mais recente | Ao digitar | Bloqueia acima do saldo |
| V9 | Item mais recente sem saldo | Ao escolher o contrato | Alerta; a usuária decide (regra em aberto) |
| V10 | Duplicidade dentro do lote: mesmo arquivo (hash) ou mesmo contrato duas vezes | Ao montar o lote | Alerta |
| V11 | Medição sem anexo | Antes de confirmar | Alerta (obrigatoriedade em aberto) |
| V12 | Total líquido diferente do valor lançado | Depois de lançar | Alerta com a diferença |
| V13 | Qualquer resposta inesperada da API ou do dado | A qualquer momento | **Imprevisto:** mostra o que aconteceu, a usuária decide e o caso é registrado para mapeamento |

**Status de cada medição no lote:**
- Falta contrato
- Falta valor
- Precisa de atenção (algum alerta)
- Fora do MVP
- Pronta
- Lançando
- Lançada
- Falhou em <passo>

---

## 6. Experiência da usuária (lote) [DECIDIDO, design visual a validar]

1. **Soltar os documentos:** ela arrasta todos os boletos e NFs da semana. A ferramenta cria um card por arquivo. Ela arrasta um arquivo para dentro de outro card para juntar documentos da mesma medição, por exemplo o boleto e a NF do mesmo fornecedor. **[ASSUMIDO]** boleto e NF chegam como arquivos separados. Alternativa mais simples, se faltar tempo: cada card tem um botão "+ anexo".
2. **Completar a lista:** a lista tem uma linha por medição, com status. Lista e não grade de cards, porque com 15 itens a lista se lê de cima para baixo. Ao clicar, a linha se expande com **o PDF à esquerda e os campos à direita**, porque no MVP ela lê o valor no documento e digita. O botão "Próxima" vai para o próximo card sem fechar nada. O que a ferramenta preencheu aparece diferente do que ela digitou.
3. **Lançar as prontas:** o botão "Lançar N prontas" não espera o lote inteiro. Antes de lançar, aparece uma confirmação única ("Você vai lançar 2 medições, total R$ 4.850,00"). Cada medição é lançada de forma independente: se uma falhar, as outras seguem, e a que falhou mostra o motivo e o botão "Tentar de novo". O comprovante traz o número da medição e um link para ela no Sienge.
4. O rascunho do lote fica salvo, para ela poder parar e voltar depois.

**Para a Etapa 3**, a interface é a última prioridade. Uma CLI ou um script que recebe o lote em JSON já demonstra o núcleo.

---

## 7. Arquitetura [DECIDIDO]

```
Tela web (lote) ──► Serviço de medições ──► API do Sienge ──► (Sienge envia ao ZEPP, já existe)
                     ├─ Motor de regras   (preenche e valida; funções puras)
                     ├─ Orquestrador      (sequência de passos, estado, retomada, idempotência)
                     ├─ Banco             (estado de cada medição + auditoria)
                     └─ Cofre / env       (credencial da API, nunca no código)
```

- A tela conversa só com o serviço. Só o serviço conversa com o Sienge.
- **Caminho técnico:** API REST oficial do Sienge.
- **Alternativas descartadas:**
  - RPA (robô clicando nas telas): frágil, e o Sienge está migrando da tela antiga para a nova.
  - Escrita direta no banco: o Sienge é SaaS, sem acesso.
  - Agente de IA operando o Sienge: valor financeiro pede regra previsível.
- O cliente do Sienge fica isolado em um único módulo, com uma implementação falsa para os testes.
- As regras ficam em configuração: dias de vencimento, critérios de avaliação, modelo de observação.

### Sequência de um lançamento (orquestrador)

| # | Passo | Tipo | Se falhar |
|---|---|---|---|
| 1 | Buscar contrato, obras, itens e saldos | Leitura | Mostra o erro; nada a desfazer |
| 2 | Buscar medições existentes do contrato (V5, V6, V7) | Leitura | Nada a desfazer |
| — | Usuária confirma | — | — |
| 3 | Criar a medição | Escrita | Registra o número retornado; **nunca cria uma segunda** |
| 4 | Registrar a avaliação do fornecedor | Escrita | Retoma deste passo |
| 5 | Lançar o valor no item mais recente | Escrita | Retoma deste passo |
| 6 | Enviar os anexos | Escrita | Reenvia só os que faltaram |
| 7 | Ler a totalização e conferir | Leitura | Alerta (V12) |

### Estados (sugestão para o brainstorm refinar)

`RASCUNHO → VALIDADA (PRONTA | ALERTA | FORA_MVP) → CONFIRMADA → CRIADA → AVALIADA → VALOR_LANCADO → ANEXOS_ENVIADOS → CONFERIDA`

Em qualquer passo de escrita, a medição pode ir para `FALHOU_EM_<passo>`. A retomada continua do passo que falhou, usando o número da medição já criada.

### Idempotência
- Chave local por medição, por exemplo `hash(contrato + obra + data + valor + hashes dos anexos)`, gravada **antes** do passo 3.
- Antes de criar, confere no Sienge se já existe medição correspondente.
- O botão de lançar trava após o clique.

### Esboço do modelo de dados
- `Lote`: id, criado_por, criado_em, status.
- `Medicao`: id_local, lote_id, chave_idempotencia, contrato, obra, fornecedor, item_alvo, valor (Decimal), observacao, data_medicao, data_vencimento, status, passo_atual, numero_medicao_sienge, alertas[], erro.
- `Anexo`: id, medicao_id, arquivo, tipo (BOLETO, NF, CONTRATO ou PROPOSTA), hash, enviado (bool).
- `Evento` (auditoria): medicao_id, passo, resultado, mensagem, quem, quando. Nunca grava dados sensíveis.

---

## 8. API do Sienge — o que sabemos e o que precisa ser verificado

> **Primeira tarefa do Claude Code:** ler a documentação da API de Medições de Contratos e a API simulada (procure por OpenAPI/Swagger, README ou lista de rotas), e montar a tabela "passo → rota" **antes** de escrever código.

**Confirmado pela central de ajuda do Sienge** (a documentação oficial em api.sienge.com.br/docs bloqueia leitura automática):
- `GET /supply-contracts/all` — todos os contratos de suprimentos.
- `GET /supply-contracts` — contratos com filtros (situação, empresa, fornecedor, empreendimento).
- `GET /supply-contracts/items` — itens dos contratos.
- `GET /supply-contracts/buildings` — obras dos contratos.
- `GET /supply-contracts/measurements/all` — medições registradas.
- `GET /supply-contracts/measurements/items` — itens de medição.
- `GET /supply-contracts/measurements/clearing` — glosa/compensação.
- `POST /supply-contracts/measurements` — **cria uma nova medição.**

**A verificar na documentação e na API simulada [EM ABERTO]:**
1. Rota para **gravar o valor medido nos itens**. Talvez o próprio POST de criação aceite os itens no corpo. É a verificação mais importante.
2. Rota de **anexos** de medição (algo como `.../measurements/.../attachments`).
3. Rota de **avaliação de fornecedor** na medição (algo como `.../evaluation`). Em pedidos de compra elas existem (`/purchase-orders/{id}/attachments`, `/purchase-orders/{id}/evaluation` e `/purchase-orders/{id}/supplier-evaluation-criteria`), mas isso não garante o equivalente em medições.
4. Como representar "Valores monetários" na API.
5. Como ler a totalização (total líquido).
6. Autenticação, URL base e limites de requisição. **[ASSUMIDO]** Autenticação Basic com usuário de API, a confirmar. Os recursos de API precisam ser liberados para o usuário de API no Sienge.

**Se algum passo não existir na API**, ele vira um **passo guiado**: a ferramenta conclui o resto, marca a medição como pendente nesse passo e oferece o link direto para a usuária concluir no Sienge. Sem RPA.

**Parâmetros do Sienge relevantes:**
- 298: a avaliação de fornecedor acontece na medição ou na liberação. Se fosse na liberação, a avaliação sairia do nosso fluxo; isso deve ser discutido com a área, não decidido por nós.
- 131: avaliação obrigatória deixa o registro inconsistente e bloqueia o pagamento.
- 843: observação padrão da medição.
- 249: permite datas retroativas.

---

## 9. Fase 2 — IA (não é para a Etapa 3, mas a arquitetura deve permitir)

**Regra-guia [DECIDIDO]:** IA para ler, regra para decidir, pessoa para aprovar. **No MVP, a IA não participa do lançamento.**

O que a fase 2 pré-preenche nos cards do lote:

| Campo | Como |
|---|---|
| Tipo do anexo | A IA classifica o arquivo; o boleto é reconhecido pela linha digitável |
| Juntar boleto e NF | Regra: mesmo CNPJ e valores compatíveis |
| Contrato | A IA lê o CNPJ (prestador na NF, beneficiário no boleto); a regra busca os contratos ativos. Se houver 1, preenche; se houver vários, sugere e a usuária escolhe |
| Valor | Boleto: **regra**, porque a linha digitável traz valor e vencimento, validados pelo dígito verificador. NF em PDF: **IA** |
| Observação | A IA lê a competência ou o mês na NF; o texto segue o modelo padrão |

**Nunca usar IA para:** calcular valores ou saldo, escolher o item, definir vencimento, decidir lançar ou chamar a API.

**Confiança por checagem, não pela nota da IA.** A nota que o modelo dá para si mesmo não é confiável. Cada campo lido aparece em um de três estados:
- **Verificado:** passou em checagens cruzadas. Ex.: dígito verificador do boleto válido, valor da NF igual ao do boleto, valor dentro do saldo, CNPJ válido com contrato ativo.
- **Conferir:** foi lido, mas sem confirmação cruzada.
- **Vazio:** não foi lido com segurança, então não é preenchido.

**Imprevisto típico:** NF ≠ boleto (provavelmente retenção de imposto). A ferramenta mostra os dois valores, explica a diferença e a usuária decide. Nunca escolhe sozinha.

**Calibração:** no início da fase 2, todo card lido pela IA exige um clique de "Conferido". A ferramenta mede quantos campos a usuária corrige, e só depois disso os cards verdes podem nascer como "Pronta".

**Alerta útil:** boleto que vence antes da data de vencimento da medição (hoje + 15). A regra não muda, apenas avisa.

---

## 10. Segurança e LGPD

- Usuário de API dedicado, com permissão mínima e recursos liberados só para o necessário.
- Credenciais em variável de ambiente ou cofre; `.env` fora do git; `.env.example` sem valores reais.
- Logs e auditoria sem senhas, tokens ou dados pessoais. Os anexos têm contratos de pessoas físicas com CPF.
- Arquivos só trafegam até o Sienge, sem cópia permanente desnecessária. Na fase 2, enviar ao LLM só o necessário, por um provedor sem retenção para treino.
- Acesso à ferramenta por login corporativo, só para quem lança medições, com registro de quem lançou cada uma.

---

## 11. Diretrizes técnicas para o desenvolvimento

- **Dinheiro sempre em `Decimal`**, nunca em `float`. Parser para o formato brasileiro ("3.042,36"). Arredondamento explícito em 2 casas.
- Datas com fuso explícito (America/Recife). Funções de data recebem um "relógio" injetável para os testes serem determinísticos.
- **Modo simulação (dry-run) como padrão:** monta e valida tudo e mostra o que seria enviado, sem gravar.
- O motor de regras é composto de **funções puras**, testáveis sem rede.
- O cliente do Sienge fica atrás de uma interface, com implementação real (HTTP), falsa (testes) e de simulação.
- Retry com backoff **só em leituras e erros transitórios**. Escritas não são repetidas cegamente; elas passam pela checagem de idempotência.
- TDD nas regras e no orquestrador: casos de sucesso, cada validação V1 a V13, falha em cada passo e retomada.
- Mensagens para a usuária em português simples, separadas do log técnico.

### Estrutura sugerida (o brainstorm pode mudar)
```
medicoes/
  config.py          # regras configuráveis (dias de vencimento, critérios, modelo de observação)
  domain/            # modelos (Lote, Medicao, Anexo, Evento), estados
  rules/             # preenchimento.py, validacoes.py (funções puras)
  sienge/            # client.py (interface), http.py, fake.py
  orchestrator/      # passos, máquina de estados, retomada, idempotência
  storage/           # SQLite (estado + auditoria)
  cli.py             # roda um lote a partir de JSON (dry-run por padrão)
tests/
```

---

## 12. Plano da Etapa 3 (55 minutos)

**O que construir:** o motor de regras e o orquestrador, rodando contra a API simulada, em modo simulação por padrão.

**Por quê (pitch de 2 minutos):** é onde está o valor (8 das 12 etapas) e o maior risco (a integração e a confiabilidade). A tela é a parte mais fácil de mudar depois.

**Ordem sugerida (cortar do fim se o tempo apertar):**
1. **(5–10 min)** Ler a API simulada e os dados fictícios; montar a tabela "passo → rota" e anotar os gaps.
2. **(15 min)** Motor de regras, com testes: obra única, vencimento, observação, item mais recente, saldo, duplicidade e ordem cronológica.
3. **(15 min)** Cliente da API simulada e orquestrador com estados e retomada; dry-run e execução real contra a API simulada.
4. **(10 min)** CLI: `medicoes lancar lote.json [--executar]` imprime, por medição, o status, os alertas e os passos executados.
5. **(Se sobrar)** Parser da linha digitável do boleto (valor, vencimento e dígito verificador). É determinístico e rápido de demonstrar.
6. Anotar honestamente o que não deu tempo e as próximas etapas.

**Critérios de aceite (exemplos):**
- **Dado** CT/1241 com 2 itens e valor 264,66, **quando** rodar em dry-run, **então** a ferramenta mostra o item 002 como alvo, saldo 288,74, vencimento = hoje + 15 e nenhuma escrita.
- **Dado** valor 300,00 para CT/1241, **então** bloqueia com a mensagem "acima do saldo do item (R$ 288,74)".
- **Dado** que já existe medição de CT/1241 no mês atual, **então** marca "Precisa de atenção" e não lança sem confirmação.
- **Dado** uma falha no passo 6 (anexos), **quando** retomar, **então** não cria outra medição e reenvia só os anexos pendentes.
- **Dado** um lote com 3 medições em que a 2ª falha, **então** a 1ª e a 3ª ficam "Lançada" e a 2ª fica "Falhou em <passo>", com o motivo.

---

## 13. Pontos em aberto (perguntar antes de assumir)

1. Quais são os 4 critérios da avaliação e as notas (sempre 10,0?).
2. A API cobre avaliação, anexos e a gravação do valor nos itens?
3. Vencimento em fim de semana ou feriado: mantém ou ajusta?
4. Critério exato de "item mais recente" e o que fazer se ele não tiver saldo.
5. Anexo é obrigatório para lançar?
6. Texto padrão da observação.
7. Como mapear a pessoa logada para o usuário responsável no Sienge.
8. Quem mais vai usar a ferramenta (define permissões e o plano de disseminação).
9. Frequência de contratos com várias obras, unidades construtivas ou retenção (define a prioridade da fase 2).
10. Boleto e NF chegam como arquivos separados ou num PDF só?

---

## 14. Métricas de sucesso (pós-MVP)

- Tempo por medição, comparado com uma linha de base cronometrada antes de começar. **[ASSUMIDO]** Meta abaixo de 2 minutos, a confirmar.
- Medições duplicadas ou incompletas: meta zero.
- Percentual de medições lançadas sem correção posterior.
- Adoção: pessoas usando e percentual das medições que passam pela ferramenta.

## 15. Roadmap de 4 semanas (pós-desafio)

1. **Semana 1:** regras e integração de leitura em modo simulação. A ferramenta refaz 20 medições antigas sem gravar e o resultado é comparado com o que foi lançado à mão.
2. **Semana 2:** orquestrador e primeiros lançamentos reais em contratos simples.
3. **Semana 3:** tela de lote em uso diário pela usuária.
4. **Semana 4:** guia de uma página, apresentação de 15 minutos para a equipe e painel de métricas.
