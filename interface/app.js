// Protótipo da tela de lote. As regras aqui espelham o núcleo em Python (medicoes/);
// o lançamento é simulado — nada sai deste navegador.
(function () {
  "use strict";

  var CHAVE_RASCUNHO = "medicoes-rascunho-v1";
  // Simulação de imprevisto: na 1ª tentativa, o envio de anexos deste contrato falha.
  var SIMULAR_FALHA = { contrato: "CT/154" };
  var TIPOS = ["NF", "BOLETO", "CONTRATO", "PROPOSTA"];
  var PASSOS = [
    "Conferir contrato e medições anteriores",
    "Criar a medição com o valor",
    "Enviar anexos",
    "Conferir o total líquido"
  ];
  var MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
    "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];

  var estado = { medicoes: [], aberta: null, seq: 1 };
  var arquivos = {};        // id do documento -> URL do arquivo solto (não vai para o rascunho)
  var arrastando = null;    // id da medição cujo cartão está sendo arrastado
  var anexarEm = null;      // id da medição que receberá o próximo arquivo escolhido
  var lancando = false;

  // ---------- utilidades ----------

  var formatoMoeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  function moeda(centavos) { return formatoMoeda.format(centavos / 100); }
  function numeroBR(centavos) {
    return (centavos / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  // "3.042,36", "R$ 264,66", "2000" -> centavos (inteiro). Vazio -> null; inválido -> NaN.
  function paraCentavos(texto) {
    var t = String(texto == null ? "" : texto).replace(/[R$\s]/g, "");
    if (!t) return null;
    if (t.indexOf(",") >= 0) t = t.replace(/\./g, "").replace(",", ".");
    else if (!/^\d+\.\d{1,2}$/.test(t)) t = t.replace(/\./g, "");
    if (!/^\d+(\.\d{1,2})?$/.test(t)) return NaN;
    var partes = t.split(".");
    var centavos = partes[1] ? parseInt((partes[1] + "0").slice(0, 2), 10) : 0;
    return parseInt(partes[0], 10) * 100 + centavos;
  }

  function dataLocal(iso) { var p = iso.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function somaDias(iso, dias) { var d = dataLocal(iso); d.setDate(d.getDate() + dias); return d; }
  function dataCurta(d) { return d.toLocaleDateString("pt-BR"); }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function novoId(prefixo) { return prefixo + estado.seq++; }
  function achar(id) { return estado.medicoes.filter(function (m) { return m.id === id; })[0] || null; }
  function dormir(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function anunciar(texto) {
    var el = document.getElementById("aviso-vivo");
    el.textContent = "";
    setTimeout(function () { el.textContent = texto; }, 40);
  }

  // ---------- regras (as mesmas do núcleo) ----------

  function contratoPorNumero(numero) {
    return CONTRATOS.filter(function (c) { return c.numero === numero; })[0] || null;
  }

  // Aceita "CT/1241", "1241", "CT/1241 — ALFA SISTEMAS LTDA" ou parte do nome do fornecedor.
  function buscarContrato(texto) {
    var t = String(texto || "").trim().toUpperCase();
    if (!t) return null;
    var numero = t.match(/^(?:CT\/)?\s*(\d+)/);
    if (numero) {
      var porNumero = contratoPorNumero("CT/" + numero[1]);
      if (porNumero) return porNumero;
    }
    var porNome = CONTRATOS.filter(function (c) { return c.fornecedor.indexOf(t.replace(/^.*—\s*/, "")) >= 0; });
    return porNome.length === 1 ? porNome[0] : null;
  }

  // Item que recebe o valor: o que ainda tem saldo; havendo mais de um, o mais recente (aditivo primeiro, depois a maior referência).
  function itemAlvo(contrato) {
    var ordenados = contrato.itens.slice().sort(function (a, b) {
      if (a.aditivo !== b.aditivo) return a.aditivo ? -1 : 1;
      return a.ref < b.ref ? 1 : -1;
    });
    var comSaldo = ordenados.filter(function (item) { return saldo(item) > 0; });
    return (comSaldo.length ? comSaldo : ordenados)[0];
  }

  function saldo(item) { return item.contratado - item.acumulado; }

  // O Sienge recebe quantidade com 4 casas (quantidade = valor ÷ preço unitário).
  function valorEfetivo(centavos, precoUnitario) {
    var quantidade = Math.round((centavos / precoUnitario) * 10000) / 10000;
    return { quantidade: quantidade, centavos: Math.round(quantidade * precoUnitario) };
  }

  function observacaoSugerida(contrato) {
    var hoje = dataLocal(HOJE);
    return "Referente aos serviços prestados pelo " + contrato.fornecedor + " - " +
      MESES[hoje.getMonth()] + "/" + hoje.getFullYear();
  }

  function rotuloContrato(c) { return c.numero + " — " + c.fornecedor; }

  var SITUACOES = {
    "falta-contrato": { rotulo: "Falta contrato", classe: "s-falta" },
    "falta-valor": { rotulo: "Falta o valor", classe: "s-falta" },
    "atencao": { rotulo: "Precisa de atenção", classe: "s-atencao" },
    "manual": { rotulo: "Fica para o caminho manual", classe: "s-manual" },
    "pronta": { rotulo: "Pronta para lançar", classe: "s-pronta" },
    "lancando": { rotulo: "Lançando…", classe: "s-lancando" },
    "lancada": { rotulo: "Lançada", classe: "s-lancada" },
    "falhou": { rotulo: "Falhou", classe: "s-falhou" }
  };

  // Devolve a situação da medição e as mensagens para a usuária. Nenhum efeito colateral.
  function avaliar(m) {
    var r = { codigo: "pronta", mensagens: [], efetivo: null, contrato: null, item: null };
    var L = m.lancamento;
    if (L && L.estado === "lancada") { r.codigo = "lancada"; return r; }
    if (L && L.estado === "lancando") { r.codigo = "lancando"; return r; }
    if (L && L.estado === "falhou") { r.codigo = "falhou"; return r; }

    var c = m.contrato ? contratoPorNumero(m.contrato) : null;
    if (!c) {
      if (m.contratoTexto && m.contratoTexto.trim()) {
        r.codigo = "atencao";
        r.mensagens.push({ tipo: "erro", titulo: "Não encontramos esse contrato.",
          texto: "Confira o número (CT/…) ou busque pelo nome do fornecedor que aparece na nota." });
      } else {
        r.codigo = "falta-contrato";
        r.mensagens.push({ tipo: "aviso", titulo: "Escolha o contrato.",
          texto: "Você pode buscar pelo número (CT/…) ou pelo nome do fornecedor." });
      }
      return r;
    }
    r.contrato = c;

    if (!c.autorizado) {
      r.codigo = "atencao";
      r.mensagens.push({ tipo: "erro", titulo: "O contrato está desautorizado no Sienge.",
        texto: "Fale com o responsável pela autorização. Esta medição não será lançada até lá." });
      return r;
    }
    if (c.caucao) {
      r.codigo = "manual";
      r.mensagens.push({ tipo: "manual", titulo: "Este contrato tem caução.",
        texto: "Por enquanto, medições com caução seguem pelo caminho manual no Sienge." });
      return r;
    }
    if (c.obras[0].unidades > 1) {
      r.codigo = "manual";
      r.mensagens.push({ tipo: "manual", titulo: "Este contrato tem mais de uma unidade construtiva.",
        texto: "Por enquanto, ele segue pelo caminho manual no Sienge." });
      return r;
    }

    var item = itemAlvo(c);
    r.item = item;
    var centavos = paraCentavos(m.valor);
    if (centavos === null) {
      r.codigo = "falta-valor";
      r.mensagens.push({ tipo: "aviso", titulo: "Digite o valor que está no documento." });
      return r;
    }
    if (isNaN(centavos)) {
      r.codigo = "atencao";
      r.mensagens.push({ tipo: "erro", titulo: "Não entendemos esse valor.", texto: "Use o formato 1.234,56." });
      return r;
    }
    if (centavos <= 0) {
      r.codigo = "atencao";
      r.mensagens.push({ tipo: "erro", titulo: "O valor precisa ser maior que zero." });
      return r;
    }
    if (centavos > saldo(item)) {
      r.codigo = "atencao";
      r.mensagens.push({ tipo: "erro", titulo: "Valor acima do saldo do item (" + moeda(saldo(item)) + ").",
        texto: "Confira o valor no documento. Se estiver certo, o contrato precisa de aditivo antes da medição." });
      return r;
    }

    var efetivo = valorEfetivo(centavos, item.precoUnitario);
    r.efetivo = efetivo.centavos;
    if (efetivo.centavos !== centavos) {
      r.mensagens.push({ tipo: "aviso", confirma: "centavos",
        titulo: "O Sienge registra este item em quantidade; o valor lançado será " + moeda(efetivo.centavos) +
          " (diferença de " + moeda(Math.abs(centavos - efetivo.centavos)) + ").",
        texto: "Item cobrado por " + item.unidade + " a " + moeda(item.precoUnitario) + ".",
        rotuloConfirma: "Entendi, pode lançar " + moeda(efetivo.centavos) });
      if (!m.confirmado.centavos) r.codigo = "atencao";
    }

    var repetido = estado.medicoes.some(function (o) {
      return o !== m && o.contrato === m.contrato && !(o.lancamento && o.lancamento.estado === "falhou");
    });
    if (repetido) {
      r.mensagens.push({ tipo: "aviso", confirma: "duplicado",
        titulo: "Este contrato aparece em outra medição deste lote.",
        texto: "Confira se não é o mesmo documento duas vezes.",
        rotuloConfirma: "É outra medição, pode seguir" });
      if (!m.confirmado.duplicado) r.codigo = "atencao";
    }
    return r;
  }

  function situacaoDe(m, av) {
    var s = SITUACOES[av.codigo];
    if (av.codigo === "falhou") return { rotulo: "Falhou em: " + PASSOS[m.lancamento.passo], classe: s.classe };
    return s;
  }

  // ---------- estado e rascunho ----------

  function novaMedicao(docs, extra) {
    var m = { id: novoId("m"), docs: docs, contrato: null, contratoTexto: "", valor: "",
      observacao: null, confirmado: { centavos: false, duplicado: false }, lancamento: null, docAtivo: null };
    if (extra) Object.keys(extra).forEach(function (k) { m[k] = extra[k]; });
    return m;
  }

  function salvar() {
    try {
      localStorage.setItem(CHAVE_RASCUNHO, JSON.stringify({ medicoes: estado.medicoes, seq: estado.seq }));
    } catch (e) { /* sem armazenamento: o protótipo segue funcionando */ }
  }

  function carregar() {
    try {
      var bruto = localStorage.getItem(CHAVE_RASCUNHO);
      if (!bruto) return;
      var salvo = JSON.parse(bruto);
      estado.seq = salvo.seq || 1;
      estado.medicoes = (salvo.medicoes || []).map(function (m) {
        m.docs.forEach(function (d) { d.temArquivo = false; }); // arquivos não sobrevivem ao recarregar
        if (m.lancamento && m.lancamento.estado === "lancando") {
          m.lancamento.estado = "falhou";
          m.lancamento.falha = "O lançamento foi interrompido. Ao tentar de novo, a ferramenta continua de onde parou.";
        }
        return m;
      });
    } catch (e) { estado.medicoes = []; }
  }

  // ---------- documentos: soltar, juntar, separar ----------

  function tipoPeloNome(nome) {
    var n = nome.toUpperCase();
    if (n.indexOf("BOLETO") >= 0) return "BOLETO";
    if (n.indexOf("CONTRATO") >= 0) return "CONTRATO";
    if (n.indexOf("PROPOSTA") >= 0) return "PROPOSTA";
    return "NF";
  }

  function criarDeArquivos(lista, destinoId) {
    var docs = Array.prototype.map.call(lista, function (f) {
      var id = novoId("d");
      try { arquivos[id] = URL.createObjectURL(f); } catch (e) { /* sem pré-visualização */ }
      return { id: id, nome: f.name, tipo: tipoPeloNome(f.name), temArquivo: true, mime: f.type || "" };
    });
    if (!docs.length) return;
    var destino = destinoId ? achar(destinoId) : null;
    if (destino) {
      destino.docs = destino.docs.concat(docs);
      anunciar(docs.length + " documento(s) adicionado(s) à medição.");
    } else {
      docs.forEach(function (d) { estado.medicoes.push(novaMedicao([d])); });
      anunciar(docs.length + " documento(s) recebido(s). Cada um virou um cartão.");
    }
    salvar();
    renderTudo();
  }

  function juntar(origemId, destinoId) {
    var o = achar(origemId), d = achar(destinoId);
    if (!o || !d || o === d || o.lancamento || d.lancamento) return;
    d.docs = d.docs.concat(o.docs);
    if (!d.contrato && o.contrato) { d.contrato = o.contrato; d.contratoTexto = ""; }
    if (!d.valor && o.valor) d.valor = o.valor;
    estado.medicoes = estado.medicoes.filter(function (m) { return m !== o; });
    if (estado.aberta === o.id) estado.aberta = d.id;
    salvar();
    renderTudo();
    var el = document.querySelector('.cartao[data-id="' + d.id + '"]');
    if (el) el.classList.add("juntou");
    anunciar("Documentos juntados: agora são " + d.docs.length + " documentos na mesma medição.");
  }

  function separar(medicaoId, docId) {
    var m = achar(medicaoId);
    if (!m || m.docs.length < 2 || m.lancamento) return;
    var doc = m.docs.filter(function (d) { return d.id === docId; })[0];
    m.docs = m.docs.filter(function (d) { return d.id !== docId; });
    if (m.docAtivo === docId) m.docAtivo = null;
    var nova = novaMedicao([doc]);
    estado.medicoes.splice(estado.medicoes.indexOf(m) + 1, 0, nova);
    salvar();
    renderTudo();
    anunciar("O documento virou uma medição separada.");
  }

  function carregarExemplo() {
    estado.medicoes = LOTE_EXEMPLO.map(function (e) {
      var docs = e.docs.map(function (d) { return { id: novoId("d"), nome: d.nome, tipo: d.tipo, temArquivo: false, mime: "" }; });
      return novaMedicao(docs, { contrato: e.contrato, valor: e.valor });
    });
    estado.aberta = null;
    salvar();
    renderTudo();
    anunciar("Exemplo carregado com " + estado.medicoes.length + " medições.");
  }

  // ---------- desenho da tela ----------

  function renderTudo() {
    renderCartoes();
    renderLista();
    renderBarra();
    renderComprovante();
  }

  function renderCartoes() {
    var ul = document.getElementById("cartoes");
    ul.innerHTML = estado.medicoes.map(function (m) {
      var c = m.contrato ? contratoPorNumero(m.contrato) : null;
      var travado = !!m.lancamento;
      return '<li class="cartao' + (travado ? " travado" : "") + '" data-id="' + m.id + '"' +
        (travado ? "" : ' draggable="true" title="Arraste para dentro de outro cartão para juntar"') + ">" +
        '<div class="cartao-topo"><span class="cartao-contrato' + (c ? "" : " sem") + '">' +
        (c ? esc(c.numero) : "Sem contrato") + "</span></div>" +
        (c ? '<div class="cartao-fornecedor">' + esc(c.fornecedor) + "</div>" : "") +
        '<ul class="cartao-docs">' + m.docs.map(function (d) {
          return '<li><span class="tipo">' + esc(d.tipo) + '</span><span class="nome">' + esc(d.nome) + "</span></li>";
        }).join("") + "</ul>" +
        '<div class="cartao-rodape"><span class="cartao-contagem">' + m.docs.length +
        (m.docs.length === 1 ? " documento" : " documentos") + "</span>" +
        (travado ? "" : '<button type="button" class="cartao-anexo" data-acao="anexo" data-id="' + m.id + '">+ anexo</button>') +
        "</div></li>";
    }).join("");
  }

  function cabecalhoLinha(m) {
    var av = avaliar(m);
    var s = situacaoDe(m, av);
    var c = m.contrato ? contratoPorNumero(m.contrato) : null;
    var centavos = paraCentavos(m.valor);
    var valor = centavos && !isNaN(centavos) ? moeda(av.efetivo || centavos) : "—";
    return '<span class="linha-id"><span class="linha-contrato"><span class="seta" aria-hidden="true"></span>' +
      (c ? esc(c.numero) : "Sem contrato") + '</span><span class="linha-fornecedor">' +
      (c ? esc(c.fornecedor) : esc(m.docs[0] ? m.docs[0].nome : "")) + "</span></span>" +
      '<span class="linha-valor' + (valor === "—" ? " vazio-valor" : "") + '">' + valor + "</span>" +
      '<span class="linha-docs">' + m.docs.length + "</span>" +
      '<span><span class="situacao ' + s.classe + '">' + esc(s.rotulo) + "</span></span>";
  }

  function faixaLinha(m) {
    var L = m.lancamento;
    if (!L) return "";
    if (L.estado === "lancando") {
      var passos = PASSOS.map(function (p, i) {
        var cls = i < L.passo ? "passo-feito" : (i === L.passo ? "passo-atual" : "");
        return '<span class="' + cls + '">' + (i + 1) + ". " + esc(p) + (i === 2 && i === L.passo ?
          " (" + L.anexosEnviados + " de " + m.docs.length + ")" : "") + "</span>";
      }).join("");
      var retomada = L.tentativas > 1 && L.numero ?
        '<span>Medição nº ' + L.numero + " mantida — nenhuma medição nova foi criada.</span>" : "";
      return '<div class="linha-faixa"><div class="passos">' + passos + "</div>" + retomada + "</div>";
    }
    if (L.estado === "falhou") {
      var feito = L.numero ? " A medição nº " + L.numero + " já foi criada e " + L.anexosEnviados + " de " +
        m.docs.length + " anexo(s) foram enviados. Ao tentar de novo, só o que falta será reenviado." : "";
      return '<div class="linha-faixa falha"><span>' + esc(L.falha || "") + feito + "</span>" +
        '<button type="button" class="botao botao-secundario botao-pequeno" data-acao="tentar" data-id="' + m.id +
        '"' + (lancando ? " disabled" : "") + ">Tentar de novo</button></div>";
    }
    return '<div class="linha-faixa sucesso"><span>Lançada no Sienge como medição nº ' + L.numero +
      ". Total líquido conferido: " + moeda(L.total) + ". Falta a avaliação do fornecedor no Sienge.</span></div>";
  }

  function visualDocumento(m) {
    var doc = m.docs.filter(function (d) { return d.id === m.docAtivo; })[0] || m.docs[0];
    var abas = m.docs.length > 1 ? '<div class="doc-abas" role="group" aria-label="Documentos desta medição">' +
      m.docs.map(function (d) {
        return '<button type="button" class="doc-aba" data-acao="aba-doc" data-id="' + m.id + '" data-doc="' + d.id +
          '" aria-pressed="' + (d === doc) + '"><span class="tipo">' + esc(d.tipo) + "</span><span>" + esc(d.nome) + "</span></button>";
      }).join("") + "</div>" : "";
    var url = doc && arquivos[doc.id];
    var conteudo;
    if (url && /^image\//.test(doc.mime)) {
      conteudo = '<img src="' + url + '" alt="' + esc(doc.nome) + '">';
    } else if (url) {
      conteudo = '<iframe src="' + url + '" title="' + esc(doc.nome) + '"></iframe>';
    } else {
      conteudo = '<div class="folha"><span class="folha-nome">' + esc(doc ? doc.nome : "") + "</span>" +
        '<span class="folha-titulo">Pré-visualização do documento</span>' +
        '<span class="folha-traco l"></span><span class="folha-traco m"></span><span class="folha-traco c"></span>' +
        '<span class="folha-traco l"></span><span class="folha-traco m"></span>' +
        '<p class="folha-nota">No exemplo não há arquivo real. Solte um PDF para vê-lo aqui, ao lado dos campos.</p></div>';
    }
    return "<div>" + abas + '<div class="doc-visual">' + conteudo + "</div></div>";
  }

  function mensagensHtml(m, av) {
    return av.mensagens.map(function (msg) {
      var confirma = msg.confirma ? '<label><input type="checkbox" data-confirma="' + msg.confirma + '" data-id="' + m.id + '"' +
        (m.confirmado[msg.confirma] ? " checked" : "") + (m.lancamento ? " disabled" : "") + ">" + esc(msg.rotuloConfirma) + "</label>" : "";
      return '<div class="mensagem ' + msg.tipo + '"><strong>' + esc(msg.titulo) + "</strong>" +
        (msg.texto ? "<p>" + esc(msg.texto) + "</p>" : "") + confirma + "</div>";
    }).join("");
  }

  function corpoLinha(m) {
    var av = avaliar(m);
    var c = m.contrato ? contratoPorNumero(m.contrato) : null;
    var bloqueado = m.lancamento ? " disabled" : "";
    var auto = '<span class="marca-auto">preenchido pelo sistema</span>';
    var campos = [];

    campos.push('<div class="campo"><label for="contrato-' + m.id + '">Contrato</label>' +
      '<input class="entrada" id="contrato-' + m.id + '" list="sugestoes-contratos" autocomplete="off" data-campo="contrato" data-id="' +
      m.id + '" placeholder="CT/… ou nome do fornecedor" value="' + esc(c ? rotuloContrato(c) : m.contratoTexto) + '"' + bloqueado + ">" +
      '<p class="ajuda">Busque pelo número do contrato ou pelo nome do fornecedor que aparece no documento.</p></div>');

    if (c) {
      var obra = c.obras[0];
      campos.push('<div class="campo"><span class="rotulo">Obra ' + auto + '</span><div class="automatico">' +
        obra.id + " · " + esc(obra.nome) + '<span class="sub">Única obra deste contrato</span></div></div>');
      if (av.item) {
        campos.push('<div class="campo"><span class="rotulo">Item que recebe o valor ' + auto + '</span><div class="automatico">' +
          esc(av.item.descricao) + (av.item.aditivo ? " · aditivo" : "") + ' · saldo <span class="numero">' + moeda(saldo(av.item)) +
          '</span><span class="sub">Ref. ' + esc(av.item.ref) + " · item que ainda tem saldo</span></div></div>");
      }
    }

    campos.push('<div class="campo"><label for="valor-' + m.id + '">Valor medido</label>' +
      '<div class="moeda"><span aria-hidden="true">R$</span><input class="entrada" id="valor-' + m.id + '" inputmode="decimal" autocomplete="off" data-campo="valor" data-id="' +
      m.id + '" placeholder="0,00" value="' + esc(m.valor) + '"' + bloqueado + "></div></div>");

    if (c) {
      campos.push('<div class="campo"><label for="obs-' + m.id + '">Observação</label>' +
        '<textarea class="area" id="obs-' + m.id + '" data-campo="observacao" data-id="' + m.id + '"' + bloqueado + ">" +
        esc(m.observacao != null ? m.observacao : observacaoSugerida(c)) + "</textarea>" +
        '<p class="ajuda">Modelo sugerido. Pode editar.</p></div>');
      campos.push('<div class="campo-par"><div class="campo"><span class="rotulo">Data da medição ' + auto + '</span>' +
        '<div class="automatico numero">' + dataCurta(dataLocal(HOJE)) + '<span class="sub">Hoje</span></div></div>' +
        '<div class="campo"><span class="rotulo">Vencimento ' + auto + '</span><div class="automatico numero">' +
        dataCurta(somaDias(HOJE, PRAZO_VENCIMENTO_DIAS)) + '<span class="sub">Hoje + ' + PRAZO_VENCIMENTO_DIAS + " dias</span></div></div></div>");
    }

    campos.push('<div class="campo"><span class="rotulo">Documentos</span><ul class="docs-lista">' +
      m.docs.map(function (d) {
        return '<li><span class="nome" title="' + esc(d.nome) + '">' + esc(d.nome) + "</span>" +
          '<select aria-label="Tipo do documento ' + esc(d.nome) + '" data-campo="tipo" data-id="' + m.id + '" data-doc="' + d.id + '"' + bloqueado + ">" +
          TIPOS.map(function (t) { return '<option value="' + t + '"' + (t === d.tipo ? " selected" : "") + ">" + t + "</option>"; }).join("") +
          "</select>" + (m.docs.length > 1 && !m.lancamento ? '<button type="button" class="botao-texto" data-acao="separar" data-id="' + m.id +
          '" data-doc="' + d.id + '">Separar</button>' : "<span></span>") + "</li>";
      }).join("") + "</ul>" +
      (m.lancamento ? "" : '<div><button type="button" class="botao-link" data-acao="anexo" data-id="' + m.id + '">Adicionar documento</button></div>') +
      "</div>");

    campos.push('<div class="mensagens" id="msg-' + m.id + '">' + mensagensHtml(m, av) + "</div>");
    campos.push('<div class="detalhe-acoes"><button type="button" class="botao botao-secundario" data-acao="fechar">Fechar</button>' +
      '<button type="button" class="botao botao-primario" data-acao="proxima" data-id="' + m.id + '">Próxima pendente</button></div>');

    return '<div class="linha-corpo" id="corpo-' + m.id + '">' + visualDocumento(m) +
      '<div class="campos">' + campos.join("") + "</div></div>";
  }

  function renderLista() {
    var lista = document.getElementById("lista");
    lista.innerHTML = estado.medicoes.map(function (m) {
      var aberta = estado.aberta === m.id;
      return '<div class="linha' + (aberta ? " aberta" : "") + '" role="listitem" data-id="' + m.id + '">' +
        '<button type="button" class="linha-cab" data-acao="alternar" data-id="' + m.id + '" aria-expanded="' + aberta +
        '" aria-controls="corpo-' + m.id + '">' + cabecalhoLinha(m) + "</button>" +
        '<div class="faixa" id="faixa-' + m.id + '">' + faixaLinha(m) + "</div>" +
        (aberta ? corpoLinha(m) : "") + "</div>";
    }).join("");
    document.getElementById("vazio").hidden = estado.medicoes.length > 0;
  }

  // Atualiza só o que muda enquanto a usuária digita, sem perder o foco do campo.
  function atualizarLinha(m) {
    var linha = document.querySelector('.linha[data-id="' + m.id + '"]');
    if (!linha) return;
    linha.querySelector(".linha-cab").innerHTML = cabecalhoLinha(m);
    linha.querySelector(".faixa").innerHTML = faixaLinha(m);
    var msg = document.getElementById("msg-" + m.id);
    if (msg) msg.innerHTML = mensagensHtml(m, avaliar(m));
    var valor = document.getElementById("valor-" + m.id);
    if (valor) {
      var av = avaliar(m);
      valor.classList.toggle("invalida", av.mensagens.some(function (x) { return x.tipo === "erro" && /valor|saldo|zero/i.test(x.titulo); }));
    }
  }

  function prontas() {
    return estado.medicoes.filter(function (m) { return avaliar(m).codigo === "pronta"; });
  }

  function totalDe(lista) {
    return lista.reduce(function (soma, m) { return soma + avaliar(m).efetivo; }, 0);
  }

  function renderBarra() {
    var p = prontas();
    var contagem = {};
    estado.medicoes.forEach(function (m) { var k = avaliar(m).codigo; contagem[k] = (contagem[k] || 0) + 1; });
    var partes = [];
    if (contagem["falta-contrato"]) partes.push(contagem["falta-contrato"] + " sem contrato");
    if (contagem["falta-valor"]) partes.push(contagem["falta-valor"] + " sem valor");
    if (contagem.atencao) partes.push(contagem.atencao + " precisa(m) de atenção");
    if (contagem.manual) partes.push(contagem.manual + " no caminho manual");
    if (contagem.falhou) partes.push(contagem.falhou + " com falha");
    if (contagem.lancada) partes.push(contagem.lancada + " lançada(s)");

    var info = p.length ? "<strong>" + p.length + (p.length === 1 ? " pronta" : " prontas") + "</strong> · total <strong>" +
      moeda(totalDe(p)) + "</strong>" : "Nenhuma medição pronta ainda.";
    if (partes.length) info += ' <span aria-hidden="true">·</span> ' + partes.join(" · ");
    document.getElementById("barra-info").innerHTML = info;

    var botao = document.getElementById("lancar");
    botao.disabled = !p.length || lancando;
    botao.textContent = p.length ? "Lançar " + p.length + (p.length === 1 ? " pronta" : " prontas") : "Lançar prontas";

    var resumo = document.getElementById("resumo");
    resumo.textContent = estado.medicoes.length ?
      estado.medicoes.length + (estado.medicoes.length === 1 ? " medição no lote" : " medições no lote") +
      ". O rascunho fica salvo neste navegador; você pode parar e voltar depois." :
      "Solte os documentos da semana para começar.";
  }

  function renderComprovante() {
    var lancadas = estado.medicoes.filter(function (m) { return m.lancamento && m.lancamento.estado === "lancada"; });
    document.getElementById("comprovante").hidden = !lancadas.length;
    document.getElementById("comprovante-lista").innerHTML = lancadas.map(function (m) {
      var c = contratoPorNumero(m.contrato);
      return '<div class="recibo">' +
        '<div><span class="recibo-rotulo">Contrato</span>' + esc(c.numero) + " · " + esc(c.fornecedor) + "</div>" +
        '<div><span class="recibo-rotulo">Medição</span><span class="recibo-num">nº ' + m.lancamento.numero + "</span></div>" +
        '<div><span class="recibo-rotulo">Valor</span><span class="numero">' + moeda(m.lancamento.total) + "</span></div>" +
        '<div><span class="recibo-rotulo">Vencimento</span><span class="numero">' + dataCurta(somaDias(HOJE, PRAZO_VENCIMENTO_DIAS)) + "</span></div>" +
        '<div><span class="recibo-rotulo">Pendência</span><span class="pendencia">Falta a avaliação do fornecedor no Sienge.</span> ' +
        '<a href="#" data-acao="abrir-sienge" title="No produto, o link abre esta medição direto no Sienge">Abrir no Sienge</a>' +
        '<span class="recibo-rotulo" style="margin-top:6px">' + m.docs.length + " anexo(s) enviados · " + m.lancamento.tentativas +
        (m.lancamento.tentativas === 1 ? " tentativa" : " tentativas") + "</span></div></div>";
    }).join("");
  }

  // ---------- lançamento (simulado) ----------

  function abrirConfirmacao() {
    var p = prontas();
    if (!p.length || lancando) return;
    document.getElementById("confirmar-texto").textContent = "Você vai lançar " + p.length +
      (p.length === 1 ? " medição" : " medições") + ", total " + moeda(totalDe(p)) + ".";
    document.getElementById("confirmar-lista").innerHTML = p.map(function (m) {
      var c = contratoPorNumero(m.contrato);
      return "<li><span>" + esc(c.numero) + " · " + esc(c.fornecedor) + '</span><span class="numero">' +
        moeda(avaliar(m).efetivo) + "</span></li>";
    }).join("");
    document.getElementById("confirmar-botao").textContent = "Lançar " + p.length + (p.length === 1 ? " medição" : " medições");
    var dialogo = document.getElementById("confirmar");
    dialogo.returnValue = "";
    dialogo.showModal();
  }

  async function executar(lista) {
    lancando = true;
    estado.aberta = null;
    renderTudo();
    for (var i = 0; i < lista.length; i++) {
      await lancarMedicao(lista[i]); // cada medição é independente: uma falha não interrompe as outras
    }
    lancando = false;
    renderTudo();
    var falhas = estado.medicoes.filter(function (m) { return m.lancamento && m.lancamento.estado === "falhou"; }).length;
    anunciar("Lançamento concluído." + (falhas ? " " + falhas + " medição(ões) precisam de nova tentativa." : ""));
  }

  async function lancarMedicao(m) {
    var c = contratoPorNumero(m.contrato);
    var L = m.lancamento;
    if (!L) {
      L = m.lancamento = { estado: "lancando", passo: 0, numero: null, anexosEnviados: 0, tentativas: 0,
        valor: avaliar(m).efetivo, total: null, falha: "" };
    }
    L.estado = "lancando";
    L.falha = "";
    L.tentativas++;
    var passo = function () { salvar(); atualizarLinha(m); renderCartoes(); renderBarra(); };

    if (L.passo === 0) { passo(); await dormir(650); L.passo = 1; }

    if (L.passo === 1) {
      passo();
      await dormir(800);
      if (!L.numero) { c.ultimaMedicao += 1; L.numero = c.ultimaMedicao; } // nunca cria uma segunda
      L.passo = 2;
    }

    if (L.passo === 2) {
      while (L.anexosEnviados < m.docs.length) {
        passo();
        await dormir(550);
        var pontoDeFalha = m.docs.length > 1 ? 1 : 0;
        if (m.contrato === SIMULAR_FALHA.contrato && L.tentativas === 1 && L.anexosEnviados === pontoDeFalha) {
          L.estado = "falhou";
          L.falha = "O Sienge não respondeu a tempo ao receber o anexo.";
          salvar();
          renderTudo();
          return;
        }
        L.anexosEnviados++;
      }
      L.passo = 3;
    }

    if (L.passo === 3) { passo(); await dormir(500); L.total = L.valor; }

    L.estado = "lancada";
    salvar();
    renderTudo();
  }

  // ---------- eventos ----------

  function proximaPendente(depoisDe) {
    var pendentes = ["falta-contrato", "falta-valor", "atencao"];
    var lista = estado.medicoes;
    var inicio = lista.indexOf(achar(depoisDe));
    for (var k = 1; k <= lista.length; k++) {
      var m = lista[(inicio + k) % lista.length];
      if (m.id !== depoisDe && pendentes.indexOf(avaliar(m).codigo) >= 0) return m;
    }
    return null;
  }

  function abrir(id, focar) {
    estado.aberta = id;
    renderLista();
    var linha = document.querySelector('.linha[data-id="' + id + '"]');
    if (linha) {
      linha.scrollIntoView({ block: "start", behavior: "smooth" });
      if (focar) {
        var m = achar(id);
        var alvo = document.getElementById((m && m.contrato ? "valor-" : "contrato-") + id);
        if (alvo) alvo.focus({ preventScroll: true });
      }
    }
  }

  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-acao]");
    if (!el) {
      var cartao = e.target.closest(".cartao");
      if (cartao) abrir(cartao.getAttribute("data-id"), true);
      return;
    }
    var id = el.getAttribute("data-id");
    var acao = el.getAttribute("data-acao");
    if (acao === "alternar") {
      estado.aberta = estado.aberta === id ? null : id;
      renderLista();
    } else if (acao === "fechar") {
      var aberta = estado.aberta;
      estado.aberta = null;
      renderLista();
      var cab = document.querySelector('.linha[data-id="' + aberta + '"] .linha-cab');
      if (cab) cab.focus();
    } else if (acao === "proxima") {
      var prox = proximaPendente(id);
      if (prox) abrir(prox.id, true);
      else { estado.aberta = null; renderLista(); anunciar("Não há mais medições pendentes."); }
    } else if (acao === "aba-doc") {
      achar(id).docAtivo = el.getAttribute("data-doc");
      renderLista();
    } else if (acao === "separar") {
      separar(id, el.getAttribute("data-doc"));
    } else if (acao === "anexo") {
      anexarEm = id;
      document.getElementById("arquivo-extra").click();
    } else if (acao === "tentar") {
      if (!lancando) executar([achar(id)]);
    } else if (acao === "abrir-sienge") {
      e.preventDefault();
      anunciar("No protótipo, este link não abre o Sienge. No produto, ele leva direto à medição.");
    }
  });

  document.addEventListener("input", function (e) {
    var campo = e.target.getAttribute("data-campo");
    if (!campo) return;
    var m = achar(e.target.getAttribute("data-id"));
    if (!m) return;
    if (campo === "valor") { m.valor = e.target.value; m.confirmado.centavos = false; }
    else if (campo === "observacao") m.observacao = e.target.value;
    else if (campo === "contrato") m.contratoTexto = e.target.value;
    else return;
    salvar();
    atualizarLinha(m);
    renderBarra();
  });

  document.addEventListener("change", function (e) {
    var t = e.target;
    var m = achar(t.getAttribute("data-id"));
    if (!m) return;
    var campo = t.getAttribute("data-campo");
    if (campo === "contrato") {
      var c = buscarContrato(t.value);
      m.contrato = c ? c.numero : null;
      m.contratoTexto = c ? "" : t.value;
      m.observacao = null;
      m.confirmado = { centavos: false, duplicado: false };
      salvar();
      renderTudo();
      var proximo = document.getElementById((c ? "valor-" : "contrato-") + m.id);
      if (proximo) proximo.focus();
    } else if (campo === "valor") {
      var centavos = paraCentavos(t.value);
      if (centavos && !isNaN(centavos)) { m.valor = numeroBR(centavos); t.value = m.valor; }
      salvar();
      atualizarLinha(m);
      renderBarra();
    } else if (campo === "tipo") {
      m.docs.forEach(function (d) { if (d.id === t.getAttribute("data-doc")) d.tipo = t.value; });
      salvar();
      renderCartoes();
      renderLista();
    } else if (t.hasAttribute("data-confirma")) {
      m.confirmado[t.getAttribute("data-confirma")] = t.checked;
      salvar();
      atualizarLinha(m);
      renderBarra();
    }
  });

  // Soltar arquivos: na área de soltar viram cartões novos; em cima de um cartão, entram naquela medição.
  var areaSoltar = document.getElementById("soltar");
  function temArquivos(e) { return e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types, "Files") >= 0; }

  window.addEventListener("dragover", function (e) { e.preventDefault(); });
  window.addEventListener("drop", function (e) { e.preventDefault(); });

  areaSoltar.addEventListener("dragover", function (e) {
    if (!temArquivos(e)) return;
    e.preventDefault();
    areaSoltar.classList.add("ativo");
  });
  areaSoltar.addEventListener("dragleave", function () { areaSoltar.classList.remove("ativo"); });
  areaSoltar.addEventListener("drop", function (e) {
    e.preventDefault();
    areaSoltar.classList.remove("ativo");
    if (temArquivos(e)) criarDeArquivos(e.dataTransfer.files);
  });

  // Arrastar um cartão para dentro de outro = os documentos são da mesma medição.
  var cartoes = document.getElementById("cartoes");
  cartoes.addEventListener("dragstart", function (e) {
    var cartao = e.target.closest(".cartao");
    if (!cartao) return;
    arrastando = cartao.getAttribute("data-id");
    e.dataTransfer.effectAllowed = "move";
    try { e.dataTransfer.setData("text/plain", arrastando); } catch (erro) { /* navegadores antigos */ }
    setTimeout(function () { cartao.classList.add("arrastando"); }, 0);
  });
  cartoes.addEventListener("dragend", function () {
    arrastando = null;
    Array.prototype.forEach.call(cartoes.querySelectorAll(".arrastando, .alvo"), function (el) {
      el.classList.remove("arrastando", "alvo");
    });
  });
  cartoes.addEventListener("dragover", function (e) {
    var cartao = e.target.closest(".cartao");
    if (!cartao || cartao.classList.contains("travado")) return;
    var id = cartao.getAttribute("data-id");
    if ((arrastando && arrastando !== id) || temArquivos(e)) {
      e.preventDefault();
      e.dataTransfer.dropEffect = arrastando ? "move" : "copy";
      cartao.classList.add("alvo");
    }
  });
  cartoes.addEventListener("dragleave", function (e) {
    var cartao = e.target.closest(".cartao");
    if (cartao && !cartao.contains(e.relatedTarget)) cartao.classList.remove("alvo");
  });
  cartoes.addEventListener("drop", function (e) {
    var cartao = e.target.closest(".cartao");
    if (!cartao) return;
    e.preventDefault();
    e.stopPropagation();
    cartao.classList.remove("alvo");
    var destino = cartao.getAttribute("data-id");
    if (arrastando) juntar(arrastando, destino);
    else if (temArquivos(e)) criarDeArquivos(e.dataTransfer.files, destino);
  });

  document.getElementById("arquivos").addEventListener("change", function (e) {
    criarDeArquivos(e.target.files);
    e.target.value = "";
  });

  var extra = document.createElement("input");
  extra.type = "file";
  extra.multiple = true;
  extra.accept = ".pdf,image/*";
  extra.id = "arquivo-extra";
  extra.className = "oculto";
  extra.setAttribute("aria-hidden", "true");
  extra.tabIndex = -1;
  extra.addEventListener("change", function () {
    if (anexarEm) criarDeArquivos(extra.files, anexarEm);
    anexarEm = null;
    extra.value = "";
  });
  document.body.appendChild(extra);

  document.getElementById("exemplo").addEventListener("click", carregarExemplo);
  document.getElementById("lancar").addEventListener("click", abrirConfirmacao);
  document.getElementById("imprimir").addEventListener("click", function () { window.print(); });

  document.getElementById("confirmar").addEventListener("close", function () {
    if (this.returnValue === "lancar") executar(prontas());
  });

  var limpar = document.getElementById("limpar");
  var limparTimer = null;
  limpar.addEventListener("click", function () {
    if (lancando) return;
    if (!limpar.classList.contains("confirmar")) {
      limpar.classList.add("confirmar");
      limpar.textContent = "Clique de novo para limpar";
      limparTimer = setTimeout(function () { limpar.classList.remove("confirmar"); limpar.textContent = "Limpar lote"; }, 3000);
      return;
    }
    clearTimeout(limparTimer);
    limpar.classList.remove("confirmar");
    limpar.textContent = "Limpar lote";
    estado.medicoes = [];
    estado.aberta = null;
    salvar();
    renderTudo();
    anunciar("Lote limpo.");
  });

  // ---------- início ----------

  var sugestoes = document.createElement("datalist");
  sugestoes.id = "sugestoes-contratos";
  sugestoes.innerHTML = CONTRATOS.map(function (c) { return '<option value="' + esc(rotuloContrato(c)) + '"></option>'; }).join("");
  document.body.appendChild(sugestoes);

  var hoje = dataLocal(HOJE).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  document.getElementById("data-hoje").textContent = hoje.charAt(0).toUpperCase() + hoje.slice(1);

  carregar();
  renderTudo();
})();
