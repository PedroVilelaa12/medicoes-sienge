// Dados fictícios da demonstração — os mesmos casos usados nos testes do núcleo.
// Valores em centavos (inteiros) para nunca depender de ponto flutuante.
// precoUnitario = R$ 1,00 (100) quando o item é controlado em reais; o Sienge mede em quantidade.

var HOJE = "2026-10-01"; // data fixa para a demonstração ser reproduzível
var PRAZO_VENCIMENTO_DIAS = 15;

var CONTRATOS = [
  {
    numero: "CT/1241",
    fornecedor: "ALFA SISTEMAS LTDA",
    autorizado: true,
    caucao: false,
    obras: [{ id: 480, nome: "START RECIFE ESTR. DA MUMBECA (COMERCIAL)", unidades: 1 }],
    itens: [
      { ref: "00.000.000.001", descricao: "Mensalidade de Software", aditivo: false,
        unidade: "R$", precoUnitario: 100, contratado: 304236, acumulado: 278883 },
      { ref: "00.000.000.002", descricao: "Mensalidade de Software", aditivo: true,
        unidade: "R$", precoUnitario: 100, contratado: 320000, acumulado: 291126 }
    ],
    ultimaMedicao: 25
  },
  {
    numero: "CT/154",
    fornecedor: "1776 METADADOS",
    autorizado: true,
    caucao: false,
    obras: [{ id: 56, nome: "ESCRITORIO CENTRAL - C.S.C (ADM)", unidades: 1 }],
    itens: [
      { ref: "00.000.000.001", descricao: "Licença e suporte de software", aditivo: false,
        unidade: "R$", precoUnitario: 100, contratado: 2400000, acumulado: 1800000 }
    ],
    ultimaMedicao: 13
  },
  {
    numero: "CT/2088",
    fornecedor: "CONSTRUTORA PILAR LTDA",
    autorizado: true,
    caucao: true,
    obras: [{ id: 112, nome: "RESIDENCIAL JAQUEIRA", unidades: 1 }],
    itens: [
      { ref: "00.000.000.001", descricao: "Execução de alvenaria", aditivo: false,
        unidade: "R$", precoUnitario: 100, contratado: 18500000, acumulado: 9200000 }
    ],
    ultimaMedicao: 7
  },
  {
    numero: "CT/3310",
    fornecedor: "HIDRO INSTALAÇÕES LTDA",
    autorizado: true,
    caucao: false,
    obras: [{ id: 205, nome: "EMPRESARIAL BOA VIAGEM", unidades: 2 }],
    itens: [
      { ref: "00.000.000.001", descricao: "Instalações hidrossanitárias", aditivo: false,
        unidade: "R$", precoUnitario: 100, contratado: 9600000, acumulado: 4100000 }
    ],
    ultimaMedicao: 4
  },
  {
    numero: "CT/0977",
    fornecedor: "VIDRAÇARIA BOA VISTA LTDA",
    autorizado: false,
    caucao: false,
    obras: [{ id: 205, nome: "EMPRESARIAL BOA VIAGEM", unidades: 1 }],
    itens: [
      { ref: "00.000.000.001", descricao: "Esquadrias de vidro temperado", aditivo: false,
        unidade: "R$", precoUnitario: 100, contratado: 4300000, acumulado: 1000000 }
    ],
    ultimaMedicao: 2
  },
  {
    numero: "CT/4102",
    fornecedor: "LOCAMAQ EQUIPAMENTOS LTDA",
    autorizado: true,
    caucao: false,
    obras: [{ id: 112, nome: "RESIDENCIAL JAQUEIRA", unidades: 1 }],
    itens: [
      // Item cadastrado em quantidade: 1 vb por mês × R$ 3.200,00.
      { ref: "00.000.000.001", descricao: "Locação mensal de equipamento", aditivo: false,
        unidade: "vb", precoUnitario: 320000, contratado: 3840000, acumulado: 2880000 }
    ],
    ultimaMedicao: 9
  }
];

// Lote de exemplo: o boleto da 1776 METADADOS chega solto, para demonstrar o "arrastar para juntar".
var LOTE_EXEMPLO = [
  { contrato: "CT/1241", valor: "264,66", docs: [
      { nome: "NF_000812_ALFA_SISTEMAS.pdf", tipo: "NF" },
      { nome: "BOLETO_ALFA_SISTEMAS_OUT.pdf", tipo: "BOLETO" } ] },
  { contrato: "CT/154", valor: "2.000,00", docs: [
      { nome: "NFS-e_2291_1776_METADADOS.pdf", tipo: "NF" } ] },
  { contrato: "CT/2088", valor: "", docs: [
      { nome: "NF_PILAR_MEDICAO_08.pdf", tipo: "NF" } ] },
  { contrato: null, valor: "", docs: [
      { nome: "BOLETO_1776_METADADOS.pdf", tipo: "BOLETO" } ] }
];
