(function () {
  const form = document.querySelector("[data-ocorrencia-form]");
  if (!form) return;

  const notaInput = form.querySelector("[name=numero_nota]");
  const cliente = form.querySelector("[name=cliente]");
  const peso = form.querySelector("[name=peso]");
  const valor = form.querySelector("[name=valor]");
  const placa = form.querySelector("[name=placa]");
  const tipo = form.querySelector("[name=tipo_devolucao]");
  const hidden = form.querySelector("[name=produtos_json]");
  const aviso = document.getElementById("nota-aviso");
  const caixa = document.getElementById("produtos-caixa");
  const botaoManual = document.getElementById("adicionar-produto");
  const xmlInput = document.getElementById("xml-nota");
  const base = form.dataset.notasUrl.replace(/0\/$/, "");
  const xmlUrl = form.dataset.xmlUrl;
  const abertasBase = (form.dataset.abertasUrl || "").replace(/0\/abertas\/$/, "");
  const ocorrenciaId = form.dataset.ocorrenciaId || "";
  const duplicada = document.getElementById("nota-duplicada");
  const csrf = form.querySelector("[name=csrfmiddlewaretoken]");
  const agora = document.querySelector("[data-agora]");

  let nota = null;
  let notaCarregada = "";
  let manuais = [];
  const selecionados = new Map();
  const iniciais = JSON.parse(document.getElementById("produtos-iniciais").textContent || "[]");
  iniciais.forEach((item) => {
    if (item.item_nota) selecionados.set(String(item.item_nota), item);
    else manuais.push(item);
  });

  function brNumero(valor, casas) {
    if (valor === null || valor === undefined || valor === "") return "";
    const normalizado = String(valor).trim().replace(/\./g, "").replace(",", ".");
    const numero = Number(String(valor).includes(",") ? normalizado : String(valor));
    if (Number.isNaN(numero)) return String(valor);
    return numero.toLocaleString("pt-BR", {
      minimumFractionDigits: casas,
      maximumFractionDigits: casas,
    });
  }

  function tick() {
    if (!agora) return;
    agora.textContent = new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
      timeZone: "America/Sao_Paulo",
    }).format(new Date());
  }
  tick();
  window.setInterval(tick, 30000);

  function el(tag, attrs, texto) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([chave, valorAttr]) => {
      if (valorAttr !== null && valorAttr !== undefined) node.setAttribute(chave, valorAttr);
    });
    if (texto) node.textContent = texto;
    return node;
  }

  function lerDom() {
    if (!caixa.querySelector("[data-item]") && !caixa.querySelector("[data-manual]")) return;
    if (nota) {
      selecionados.clear();
      caixa.querySelectorAll("[data-item]").forEach((row) => {
        const marcado = row.querySelector("[data-check]");
        if (!marcado || !marcado.checked) return;
        selecionados.set(row.dataset.item, {
          item_nota: Number(row.dataset.item),
          quantidade: row.querySelector("[data-qtd]").value,
        });
      });
      return;
    }
    manuais = [...caixa.querySelectorAll("[data-manual]")].map((row) => ({
      descricao: row.querySelector("[data-desc]").value,
      quantidade: row.querySelector("[data-qtd]").value,
      unidade: row.querySelector("[data-un]").value,
    }));
  }

  function desenharNota() {
    botaoManual.hidden = true;
    caixa.replaceChildren();
    const total = tipo.value === "total";
    const intro = el("p", { class: "dica" });
    intro.textContent = total
      ? "Devolução total: todos os produtos da nota entram com a quantidade original."
      : "Marque os produtos devolvidos e ajuste a quantidade se a recusa for parcial.";
    caixa.append(intro);

    const tabela = el("table", { class: "tabela" });
    const cabeca = document.createElement("thead");
    const linhaCabeca = document.createElement("tr");
    ["", "Produto", "Na nota", "Devolvido"].forEach((titulo) => {
      linhaCabeca.append(el("th", {}, titulo));
    });
    cabeca.append(linhaCabeca);
    tabela.append(cabeca);
    const corpo = document.createElement("tbody");

    nota.itens.forEach((item) => {
      const salvo = selecionados.get(String(item.id));
      const linha = el("tr", {
        "data-item": item.id,
        "data-descricao": item.descricao,
        "data-codigo": item.codigo || "",
        "data-unidade": item.unidade || "UN",
      });
      const celulaMarca = document.createElement("td");
      const check = el("input", { type: "checkbox", "data-check": "1" });
      check.checked = total || Boolean(salvo);
      check.disabled = total;
      celulaMarca.append(check);

      const qtd = el("input", {
        class: "input",
        "data-qtd": "1",
        inputmode: "decimal",
        value: brNumero(total ? item.quantidade : (salvo ? salvo.quantidade : item.quantidade), 3),
      });
      qtd.disabled = total || !check.checked;
      check.addEventListener("change", () => {
        qtd.disabled = !check.checked;
      });

      linha.append(
        celulaMarca,
        el("td", {}, item.descricao),
        el("td", {}, `${brNumero(item.quantidade, 3)} ${item.unidade}`),
      );
      const celulaQtd = document.createElement("td");
      celulaQtd.append(qtd);
      linha.append(celulaQtd);
      corpo.append(linha);
    });
    tabela.append(corpo);
    caixa.append(tabela);
  }

  function desenharManuais() {
    botaoManual.hidden = false;
    if (!manuais.length) manuais = [{ descricao: "", quantidade: "", unidade: "UN" }];
    caixa.replaceChildren();
    const intro = el("p", { class: "dica" });
    intro.textContent = "Sem nota no cadastro. Informe os produtos devolvidos.";
    caixa.append(intro);
    manuais.forEach((item) => caixa.append(linhaManual(item)));
  }

  function linhaManual(item) {
    const linha = el("div", { class: "manual", "data-manual": "1" });
    const desc = el("input", {
      class: "input",
      "data-desc": "1",
      placeholder: "Produto",
      value: item.descricao || "",
    });
    const qtd = el("input", {
      class: "input",
      "data-qtd": "1",
      inputmode: "decimal",
      placeholder: "Qtd",
      value: item.quantidade ? brNumero(item.quantidade, 3) : "",
    });
    const un = el("input", {
      class: "input",
      "data-un": "1",
      placeholder: "UN",
      value: item.unidade || "UN",
    });
    const remover = el("button", { class: "botao botao-fantasma", type: "button" }, "Tirar");
    remover.addEventListener("click", () => {
      linha.remove();
      if (!caixa.querySelector("[data-manual]")) caixa.append(linhaManual({}));
    });
    linha.append(desc, qtd, un, remover);
    return linha;
  }

  function produtosComoManuais(lista) {
    return lista.map((item) => ({
      descricao: item.descricao || "",
      quantidade: item.quantidade || "",
      unidade: item.unidade || "UN",
    }));
  }

  function aplicarNota(dados, origem, preencherCampos = true) {
    nota = dados;
    notaCarregada = String(dados.numero);
    manuais = [];
    if (preencherCampos) {
      notaInput.value = dados.numero;
      cliente.value = dados.cliente;
      peso.value = brNumero(dados.peso, 3);
      valor.value = brNumero(dados.valor, 2);
      placa.value = dados.placa || "";
      aviso.textContent = dados.placa
        ? `${origem} Cliente, valor, peso, placa e produtos preenchidos.`
        : `${origem} Cliente, valor, peso e produtos preenchidos. A placa não veio no XML.`;
    } else {
      aviso.textContent = "Produtos da nota carregados. Ajuste o que foi devolvido.";
    }
    desenharNota();
  }

  async function checarDuplicada(numero) {
    if (!duplicada || !abertasBase) return;
    duplicada.hidden = true;
    duplicada.replaceChildren();
    if (!numero) return;
    try {
      const query = ocorrenciaId ? `?ignorar=${ocorrenciaId}` : "";
      const resposta = await fetch(`${abertasBase}${numero}/abertas/${query}`, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!resposta.ok) return;
      const dados = await resposta.json();
      const lista = dados.abertas || [];
      if (!lista.length) return;
      duplicada.hidden = false;
      const texto = document.createElement("p");
      texto.textContent =
        lista.length === 1
          ? "Já existe uma ocorrência em aberto com esta nota. Você ainda pode lançar outra, se for o caso."
          : `Já existem ${lista.length} ocorrências em aberto com esta nota. Você ainda pode lançar outra, se for o caso.`;
      duplicada.append(texto);
      const ul = document.createElement("ul");
      lista.forEach((item) => {
        const li = document.createElement("li");
        const link = document.createElement("a");
        link.href = item.url;
        const quando = item.data_hora
          ? new Date(item.data_hora).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })
          : "";
        link.textContent = `${item.equipe_nome || "Equipe"} · ${item.status_label || ""} · ${quando}`.trim();
        li.append(link);
        ul.append(li);
      });
      duplicada.append(ul);
    } catch (erro) {
      /* o aviso da nota já cobre falha de rede */
    }
  }

  async function buscar(substituir) {
    const numero = notaInput.value.replace(/\D/g, "");
    if (!numero) return;
    lerDom();
    aviso.textContent = "Consultando a nota…";
    checarDuplicada(numero);
    try {
      const resposta = await fetch(`${base}${numero}/`, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (resposta.status === 404) {
        nota = null;
        notaCarregada = numero;
        aviso.textContent = substituir
          ? "Nota não encontrada na origem. Preencha cliente, peso, valor e produtos."
          : "Produtos desta ocorrência carregados. A nota não está na origem agora.";
        if (!manuais.length && iniciais.length) manuais = produtosComoManuais(iniciais);
        desenharManuais();
        return;
      }
      if (!resposta.ok) {
        aviso.textContent = "Não foi possível consultar a nota.";
        if (iniciais.length && !caixa.querySelector("[data-item], [data-manual]")) {
          manuais = produtosComoManuais(iniciais);
          desenharManuais();
        }
        return;
      }
      const dados = await resposta.json();
      aplicarNota(dados, "Nota encontrada.", substituir || !cliente.value);
    } catch (erro) {
      aviso.textContent = "Sem conexão para consultar a nota.";
      if (iniciais.length && !caixa.querySelector("[data-item], [data-manual]")) {
        manuais = produtosComoManuais(iniciais);
        desenharManuais();
      }
    }
  }

  function tokenCsrf() {
    if (csrf && csrf.value) return csrf.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  async function importarXml(arquivo) {
    if (!arquivo) return;
    aviso.classList.remove("erro");
    aviso.textContent = "Lendo XML…";
    const corpo = new FormData();
    corpo.append("arquivo", arquivo);
    try {
      const resposta = await fetch(xmlUrl, {
        method: "POST",
        body: corpo,
        credentials: "same-origin",
        headers: {
          "X-CSRFToken": tokenCsrf(),
        },
      });
      const dados = await resposta.json().catch(() => ({}));
      if (!resposta.ok) {
        aviso.classList.add("erro");
        aviso.textContent = dados.detail || "Não foi possível ler este XML. Envie o XML da NF-e, não o PDF da DANFE.";
        return;
      }
      aplicarNota(dados, "XML importado.");
    } catch (erro) {
      aviso.classList.add("erro");
      aviso.textContent = "Sem conexão para enviar o XML.";
    } finally {
      xmlInput.value = "";
    }
  }

  function coletar() {
    if (nota && tipo.value === "total") return [];
    if (nota) {
      return [...caixa.querySelectorAll("[data-item]")]
        .filter((row) => row.querySelector("[data-check]").checked)
        .map((row) => ({
          item_nota: Number(row.dataset.item),
          codigo: row.dataset.codigo,
          descricao: row.dataset.descricao,
          quantidade: row.querySelector("[data-qtd]").value,
          unidade: row.dataset.unidade,
          selecionado: true,
        }));
    }
    return [...caixa.querySelectorAll("[data-manual]")]
      .map((row) => ({
        descricao: row.querySelector("[data-desc]").value.trim(),
        quantidade: row.querySelector("[data-qtd]").value,
        unidade: (row.querySelector("[data-un]").value || "UN").trim(),
        selecionado: true,
      }))
      .filter((item) => item.descricao || item.quantidade);
  }

  if (xmlInput) {
    xmlInput.addEventListener("change", () => importarXml(xmlInput.files[0]));
  }
  notaInput.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter") {
      evento.preventDefault();
      buscar(true);
    }
  });
  notaInput.addEventListener("blur", () => {
    const numero = notaInput.value.replace(/\D/g, "");
    checarDuplicada(numero);
    if (numero.length >= 6 && numero !== notaCarregada) buscar(true);
  });
  tipo.addEventListener("change", () => {
    lerDom();
    if (nota) desenharNota();
  });
  if (botaoManual) {
    botaoManual.addEventListener("click", () => {
      lerDom();
      manuais.push({ descricao: "", quantidade: "", unidade: "UN" });
      desenharManuais();
    });
  }
  const fonte = form.querySelector(".editor-fonte");
  const caixaEditor = document.getElementById("editor-descricao");
  let quill = null;

  function htmlDoEditor() {
    if (!quill) return fonte ? fonte.value : "";
    const texto = (quill.getText() || "").replace(/\u00a0/g, " ").trim();
    if (!texto) return "";
    return quill.root.innerHTML;
  }

  function sincronizarEditor() {
    if (fonte) fonte.value = htmlDoEditor();
    if (hidden) hidden.value = JSON.stringify(coletar());
  }

  if (fonte && caixaEditor && window.Quill) {
    quill = new window.Quill(caixaEditor, {
      theme: "snow",
      placeholder: "O que aconteceu, onde, e o que o cliente recusou.",
      modules: {
        toolbar: [["bold", "italic", "underline"], [{ color: [] }]],
      },
    });
    if (fonte.value) {
      quill.clipboard.dangerouslyPasteHTML(fonte.value);
    }
    quill.on("text-change", sincronizarEditor);
  }

  form.addEventListener(
    "submit",
    () => {
      sincronizarEditor();
    },
    true,
  );

  const erros = document.getElementById("erros-form");
  if (erros) erros.scrollIntoView({ behavior: "smooth", block: "center" });

  const numeroInicial = notaInput.value.replace(/\D/g, "");
  if (manuais.length) desenharManuais();
  else if (iniciais.length) {
    manuais = produtosComoManuais(iniciais);
    desenharManuais();
  }
  if (numeroInicial) buscar(false);
})();
