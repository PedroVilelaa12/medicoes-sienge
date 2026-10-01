/* Tutorial de primeiro acesso (PLANEJAMENTO §6.1): um passo por vez, o alvo aceso e o resto escuro. */
(function () {
  "use strict";

  var CHAVE = "medicoes.tutorial.visto";
  var PASSOS = [
    { alvo: "#soltar", titulo: "Solte os documentos",
      texto: "Comece soltando aqui os boletos e as notas fiscais da semana. Cada arquivo vira um cartão." },
    { alvo: "#cartoes", titulo: "Junte o que é da mesma medição",
      texto: "Boleto e nota do mesmo fornecedor? Arraste um cartão para dentro do outro: eles viram uma medição só." },
    { alvo: "#lista-bloco", titulo: "Confira e complete",
      texto: "Abra cada medição: o documento fica à esquerda e os campos à direita. Você só informa contrato, valor e observação." },
    { alvo: ".linha-cab", titulo: "Acompanhe a situação",
      texto: "A situação mostra o que falta. Só as medições prontas podem ser lançadas." },
    { alvo: "#lancar", alternativo: "#barra", titulo: "Lance as prontas",
      texto: "Quando quiser, lance as prontas. Você confirma o total antes, e nada é gravado sem isso." },
    { alvo: null, titulo: "Pronto!",
      texto: "Depois de lançar, o comprovante mostra o número de cada medição e o que ainda falta no Sienge." }
  ];
  var FOLGA = 8;
  var MARGEM = 16;

  var camada, recorte, caixa, elIndicador, elTitulo, elTexto, btPular, btVoltar, btProximo;
  var indice = 0;
  var ativo = false;
  var alvoAtual = null;

  function jaViu() {
    try { return localStorage.getItem(CHAVE) === "1"; } catch (e) { return false; }
  }

  function marcarVisto() {
    try { localStorage.setItem(CHAVE, "1"); } catch (e) { /* sem armazenamento: o tutorial volta na próxima visita */ }
  }

  function criar() {
    camada = document.createElement("div");
    camada.className = "tour-camada";
    camada.hidden = true;

    recorte = document.createElement("div");
    recorte.className = "tour-recorte";
    recorte.setAttribute("aria-hidden", "true");

    caixa = document.createElement("div");
    caixa.className = "tour-caixa";
    caixa.setAttribute("role", "dialog");
    caixa.setAttribute("aria-modal", "true");
    caixa.setAttribute("aria-labelledby", "tour-titulo");
    caixa.tabIndex = -1;
    caixa.innerHTML =
      '<p class="tour-indicador"></p>' +
      '<h2 class="tour-titulo" id="tour-titulo"></h2>' +
      '<p class="tour-texto" aria-live="polite"></p>' +
      '<div class="tour-acoes">' +
        '<button type="button" class="tour-pular">Pular</button>' +
        '<span class="tour-espaco"></span>' +
        '<button type="button" class="tour-voltar">Voltar</button>' +
        '<button type="button" class="tour-proximo">Próximo</button>' +
      "</div>";

    camada.appendChild(recorte);
    camada.appendChild(caixa);
    document.body.appendChild(camada);

    elIndicador = caixa.querySelector(".tour-indicador");
    elTitulo = caixa.querySelector(".tour-titulo");
    elTexto = caixa.querySelector(".tour-texto");
    btPular = caixa.querySelector(".tour-pular");
    btVoltar = caixa.querySelector(".tour-voltar");
    btProximo = caixa.querySelector(".tour-proximo");

    btPular.addEventListener("click", encerrar);
    btVoltar.addEventListener("click", voltar);
    btProximo.addEventListener("click", proximo);
    // Clique fora da caixa não faz nada: a camada absorve.
    camada.addEventListener("click", function (ev) {
      if (!caixa.contains(ev.target)) { ev.preventDefault(); ev.stopPropagation(); }
    });
    document.addEventListener("keydown", teclado, true);
    window.addEventListener("resize", posicionar);
    window.addEventListener("scroll", posicionar, true);
  }

  function limitar(valor, minimo, maximo) {
    return Math.min(Math.max(valor, minimo), Math.max(minimo, maximo));
  }

  function posicionar() {
    if (!ativo) { return; }
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var w = caixa.offsetWidth;
    var h = caixa.offsetHeight;

    if (!alvoAtual) {
      recorte.classList.add("tour-recorte-vazio");
      recorte.style.top = vh / 2 + "px";
      recorte.style.left = vw / 2 + "px";
      recorte.style.width = "0px";
      recorte.style.height = "0px";
      caixa.style.top = Math.max(MARGEM, (vh - h) / 2) + "px";
      caixa.style.left = Math.max(MARGEM, (vw - w) / 2) + "px";
      return;
    }

    recorte.classList.remove("tour-recorte-vazio");
    var r = alvoAtual.getBoundingClientRect();
    var topo = Math.max(r.top - FOLGA, 4);
    var esquerda = Math.max(r.left - FOLGA, 4);
    var base = Math.min(r.bottom + FOLGA, vh - 4);
    var direita = Math.min(r.right + FOLGA, vw - 4);
    recorte.style.top = topo + "px";
    recorte.style.left = esquerda + "px";
    recorte.style.width = Math.max(0, direita - esquerda) + "px";
    recorte.style.height = Math.max(0, base - topo) + "px";

    // A caixa vai ao lado do alvo, sem cobri-lo e sem sair da tela.
    var x, y;
    if (vh - base >= h + MARGEM * 2) {
      y = base + MARGEM; x = limitar(esquerda, MARGEM, vw - w - MARGEM);
    } else if (topo >= h + MARGEM * 2) {
      y = topo - MARGEM - h; x = limitar(esquerda, MARGEM, vw - w - MARGEM);
    } else if (vw - direita >= w + MARGEM * 2) {
      x = direita + MARGEM; y = limitar(topo, MARGEM, vh - h - MARGEM);
    } else if (esquerda >= w + MARGEM * 2) {
      x = esquerda - MARGEM - w; y = limitar(topo, MARGEM, vh - h - MARGEM);
    } else {
      x = vw - w - MARGEM; y = vh - h - MARGEM;
    }
    caixa.style.top = y + "px";
    caixa.style.left = x + "px";
  }

  function mostrar() {
    var passo = PASSOS[indice];
    alvoAtual = null;
    if (passo.alvo) {
      alvoAtual = document.querySelector(passo.alvo) ||
        (passo.alternativo ? document.querySelector(passo.alternativo) : null);
    }
    elIndicador.textContent = (indice + 1) + " de " + PASSOS.length;
    elTitulo.textContent = passo.titulo;
    elTexto.textContent = passo.texto;
    btVoltar.disabled = indice === 0;
    btProximo.textContent = indice === PASSOS.length - 1 ? "Concluir" : "Próximo";

    if (alvoAtual) {
      try { alvoAtual.scrollIntoView({ block: "center", inline: "nearest" }); } catch (e) { alvoAtual.scrollIntoView(); }
    }
    posicionar();
    try { btProximo.focus({ preventScroll: true }); } catch (e) { btProximo.focus(); }
  }

  function proximo() {
    if (indice < PASSOS.length - 1) { indice += 1; mostrar(); } else { encerrar(); }
  }

  function voltar() {
    if (indice > 0) { indice -= 1; mostrar(); }
  }

  function encerrar() {
    if (!ativo) { return; }
    ativo = false;
    camada.hidden = true;
    marcarVisto();
    var botao = document.getElementById("ver-tutorial");
    if (botao) { botao.focus(); }
  }

  function teclado(ev) {
    if (!ativo) { return; }
    if (ev.key === "Escape") { ev.preventDefault(); encerrar(); return; }
    if (ev.key === "ArrowRight") { ev.preventDefault(); proximo(); return; }
    if (ev.key === "ArrowLeft") { ev.preventDefault(); voltar(); return; }
    if (ev.key === "Enter") {
      var ativoEl = document.activeElement;
      // Em um botão da caixa, o Enter já vira clique; fora dele, avança.
      if (!ativoEl || ativoEl.tagName !== "BUTTON" || !caixa.contains(ativoEl)) { ev.preventDefault(); proximo(); }
      return;
    }
    if (ev.key === "Tab") {
      var focaveis = [btPular, btVoltar, btProximo].filter(function (b) { return !b.disabled; });
      var i = focaveis.indexOf(document.activeElement);
      ev.preventDefault();
      var n = ev.shiftKey ? (i <= 0 ? focaveis.length - 1 : i - 1) : (i === -1 || i === focaveis.length - 1 ? 0 : i + 1);
      focaveis[n].focus();
    }
  }

  function iniciar() {
    if (ativo) { return; }
    // Sem lote, carrega o exemplo para os passos terem o que mostrar.
    if (!document.querySelector(".linha-cab")) {
      var exemplo = document.getElementById("exemplo");
      if (exemplo) { exemplo.click(); }
    }
    if (!camada) { criar(); }
    indice = 0;
    ativo = true;
    camada.hidden = false;
    // Primeiro passo aparece no lugar, sem deslizar do canto da tela.
    recorte.classList.add("tour-sem-transicao");
    caixa.classList.add("tour-sem-transicao");
    setTimeout(function () {
      mostrar();
      setTimeout(function () {
        recorte.classList.remove("tour-sem-transicao");
        caixa.classList.remove("tour-sem-transicao");
      }, 50);
    }, 60);
  }

  var botao = document.getElementById("ver-tutorial");
  if (botao) { botao.addEventListener("click", iniciar); }
  if (!jaViu()) { setTimeout(iniciar, 400); }

  window.TutorialMedicoes = { iniciar: iniciar };
})();
