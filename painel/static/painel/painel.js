(function () {
  const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";

  function pintar(select) {
    const opcao = select.selectedOptions[0];
    const cor = (opcao && opcao.dataset.cor) || select.style.getPropertyValue("--status-cor");
    if (cor) select.style.setProperty("--status-cor", cor);
  }

  document.querySelectorAll("[data-status-url]").forEach((select) => {
    pintar(select);
    select.addEventListener("change", async () => {
      const anterior = select.dataset.atual;
      pintar(select);
      select.disabled = true;
      const corpo = new URLSearchParams();
      corpo.set("status", select.value);
      corpo.set("csrfmiddlewaretoken", csrf);
      try {
        const resposta = await fetch(select.dataset.statusUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "X-CSRFToken": csrf,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: corpo.toString(),
        });
        const dados = await resposta.json().catch(() => ({}));
        if (!resposta.ok || !dados.ok) {
          select.value = anterior;
          pintar(select);
          window.alert(dados.detail || "Não foi possível atualizar o status.");
          return;
        }
        select.dataset.atual = String(dados.status);
        select.style.setProperty("--status-cor", dados.status_cor);
      } catch (erro) {
        select.value = anterior;
        pintar(select);
        window.alert("Sem conexão para atualizar o status.");
      } finally {
        select.disabled = false;
      }
    });
  });
})();
