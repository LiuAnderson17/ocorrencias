import re
from html import escape, unescape
from html.parser import HTMLParser

TAGS = {"b", "strong", "i", "em", "u", "s", "br", "p", "div", "span", "ul", "ol", "li"}
COR = re.compile(r"^(#[0-9a-fA-F]{3,8}|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)|[a-zA-Z]+)$")


def texto_puro(html):
    texto = re.sub(r"(?i)<br\s*/?>", "\n", html or "")
    texto = re.sub(r"(?i)</p>", "\n", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    return unescape(re.sub(r"\s+", " ", texto)).strip()


def _estilo(valor):
    partes = []
    for trecho in (valor or "").split(";"):
        if ":" not in trecho:
            continue
        chave, dado = trecho.split(":", 1)
        chave, dado = chave.strip().lower(), dado.strip()
        if chave == "color" and COR.match(dado.replace(" ", "")):
            partes.append(f"color: {dado}")
        elif chave == "font-weight" and dado.lower() in {"bold", "700", "600", "800"}:
            partes.append("font-weight: 700")
    return "; ".join(partes)


class _Limpador(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []
        self.ignorar = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style"}:
            self.ignorar += 1
            return
        if self.ignorar:
            return
        mapa = {k.lower(): v for k, v in attrs}
        if tag == "font" and mapa.get("color"):
            cor = mapa["color"].strip()
            if COR.match(cor.replace(" ", "")):
                self.partes.append(f'<span style="color: {escape(cor, quote=True)}">')
            return
        if tag not in TAGS:
            return
        if tag == "br":
            self.partes.append("<br>")
            return
        extra = ""
        if tag == "span":
            estilo = _estilo(mapa.get("style", ""))
            if estilo:
                extra = f' style="{escape(estilo, quote=True)}"'
        self.partes.append(f"<{tag}{extra}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style"}:
            self.ignorar = max(0, self.ignorar - 1)
            return
        if self.ignorar:
            return
        if tag == "font":
            self.partes.append("</span>")
            return
        if tag in TAGS and tag != "br":
            self.partes.append(f"</{tag}>")

    def handle_data(self, data):
        if self.ignorar:
            return
        self.partes.append(escape(data, quote=False))

    def handle_entityref(self, name):
        self.partes.append(f"&{name};")

    def handle_charref(self, name):
        self.partes.append(f"&#{name};")


def sanitizar(html):
    bruto = (html or "").strip()
    if not bruto:
        return ""
    if "<" not in bruto:
        return escape(bruto).replace("\n", "<br>")
    limpador = _Limpador()
    try:
        limpador.feed(bruto)
        limpador.close()
    except Exception:
        return escape(texto_puro(bruto)).replace("\n", "<br>")
    return "".join(limpador.partes)


def descricao_html(html):
    return sanitizar(html)
