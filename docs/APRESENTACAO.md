# Roteiro da apresentação (Etapa 5 · 10 minutos + conversa)

Mensagem central: **antes de construir, perguntei e verifiquei na fonte.** O que construí é o núcleo mais arriscado (regras e confiabilidade). O resto está planejado, com as decisões explicadas.

## Roteiro

| Tempo | Bloco | O que mostrar | Frase-chave |
|---|---|---|---|
| 0:00–1:00 | O problema | 12 etapas por medição, das quais só 4 mudam; lançamento em sequência na segunda-feira | "O risco não é a lentidão, é o erro silencioso: medição sem valor, em dobro, sem anexo." |
| 1:00–3:00 | O que a API do Sienge mudou | PLANEJAMENTO §2.3: criar já com o valor; quantidade × reais; sem rota de avaliação; responsável; `makeUnauthorized` | "A documentação parecia bloqueada. Achei as specs oficiais e li inteiras antes de escrever uma linha de cliente." |
| 3:00–6:00 | Demonstração | **Tela:** soltar documentos, juntar boleto e NF arrastando, completar, "Lançar 2 prontas", uma falha, "Tentar de novo", comprovante com a pendência da avaliação. **Terminal:** dry-run, `--executar --falhar-em anexos`, retomada sem duplicar, testes verdes | "Cada medição é independente: se uma falha, as outras seguem, e a retomada nunca cria outra." |
| 6:00–7:30 | Decisões e o que ficou de fora | D1 (API × RPA × banco × agente), D3 (avaliação guiada), D5 (centavos), D9 (casos fora do MVP); fase 2 como estudo (§8) | "Deixar contratos com retenção para o manual é uma decisão, não esquecimento: a própria tela nova do Sienge não aceita." |
| 7:30–8:30 | Uso de IA | `docs/USO_DE_IA.md`: o que pedi, o que verifiquei, o que a IA corrigiu no contexto | "Usei a IA para ir mais rápido, mas a fonte da verdade foi a spec oficial e os testes." |
| 8:30–10:00 | Próximos passos | 12 perguntas para a área (§10); 4 semanas (§11); métricas | "Semana 1: refazer 20 medições antigas sem gravar e comparar com o lançamento manual." |

## Perguntas prováveis da banca

**Por que não RPA, se a API não tem a avaliação?**
Porque o RPA traria toda a fragilidade de volta (o Sienge está migrando de tela) por causa de um único passo. Prefiro um passo guiado com link e conversar com a área sobre o parâmetro 298 (avaliar na liberação).

**E se a conexão cair logo depois de criar a medição?**
Esse é o estado ambíguo `CRIACAO_ENVIADA`. Antes de qualquer nova tentativa, a ferramenta procura no Sienge uma medição do mesmo contrato, obra e data:
- achou uma igual → adota o número;
- não achou → pode criar;
- ficou ambíguo → mostra à usuária, e ela decide.

Escrita nunca é repetida às cegas.

**Como garantem que não duplica?**
São quatro camadas:
1. a chave de idempotência gravada antes do POST;
2. o número da medição guardado assim que o Sienge responde;
3. a reconciliação depois de um timeout;
4. a trava no botão e no serviço.

Os anexos são conferidos na lista do Sienge antes de reenviar.

**Por que a IA não faz tudo, inclusive lançar?**
Porque é valor financeiro, e o lançamento precisa de regra previsível e auditável. A IA entra na fase 2 só para **ler** documentos. A confiança vem de checagem cruzada (dígito verificador, NF = boleto, valor dentro do saldo), não da nota que o modelo dá para si mesmo.

**O que acontece com o valor quando o item é "1 vb"?**
A API só aceita quantidade com 4 casas. A ferramenta calcula o valor que de fato entra (R$ 264,64 em vez de R$ 264,66), mostra a diferença, e a usuária decide. Nunca arredonda calada. Pergunta nº 1 para a área: como esses itens são cadastrados.

**LGPD?**
- Usuário de API com permissão mínima.
- Credenciais fora do código.
- Logs sem CPF, senha ou token.
- Anexos sem cópia permanente.
- Na fase 2, provedor de IA sem retenção para treino.

**O que faria com mais tempo?**
- Rodar o cliente HTTP contra a API simulada e comparar com a spec.
- SQLite e o serviço web ligando a tela ao núcleo.
- Dry-run sobre medições reais antigas.
- O benchmark de leitura de documentos (§8.3).
