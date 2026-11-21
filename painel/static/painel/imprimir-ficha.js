(function () {
  document.addEventListener("click", function (evento) {
    var alvo = evento.target.closest("a[data-imprimir-ficha]");
    if (!alvo) return;
    var url = alvo.getAttribute("href");
    if (!url) return;
    var janela = window.open(url, "ficha-impressao");
    if (janela) {
      evento.preventDefault();
      janela.focus();
    }
  });
})();
