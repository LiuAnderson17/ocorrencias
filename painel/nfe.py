import re
import zipfile
from decimal import Decimal, InvalidOperation
from io import BytesIO
from xml.etree import ElementTree as ET

from django.core.exceptions import ValidationError

from painel.origens import salvar_nota_local
from painel.services import normalizar_nota, normalizar_placa

LIMITE_XML = 8 * 1024 * 1024


def _local(tag):
    return tag.split("}", 1)[-1] if tag else ""


def _texto(el):
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def _filho(pai, nome):
    if pai is None:
        return None
    for child in list(pai):
        if _local(child.tag) == nome:
            return child
    return None


def _todos(pai, nome):
    if pai is None:
        return []
    return [el for el in pai.iter() if _local(el.tag) == nome]


def _achar(raiz, *nomes):
    procurados = set(nomes)
    for el in raiz.iter():
        if _local(el.tag) in procurados:
            return el
    return None


def _primeiro_texto(pai, *nomes):
    for nome in nomes:
        for el in _todos(pai, nome):
            texto = _texto(el)
            if texto:
                return texto
    return ""


def _decimal(texto, casas):
    if not texto:
        return Decimal("0").quantize(Decimal("1").scaleb(-casas))
    try:
        return Decimal(str(texto).replace(",", ".")).quantize(Decimal("1").scaleb(-casas))
    except (InvalidOperation, AttributeError):
        return Decimal("0").quantize(Decimal("1").scaleb(-casas))


def _placa(texto):
    try:
        return normalizar_placa(texto)
    except ValidationError:
        limpa = re.sub(r"[^A-Za-z0-9]", "", texto or "").upper()
        return limpa[:8] if len(limpa) >= 7 else ""


def _nnf_da_chave(chave):
    digitos = re.sub(r"\D", "", chave or "")
    if len(digitos) == 44:
        return digitos[25:34]
    return ""


def _abrir_zip(bruto):
    try:
        with zipfile.ZipFile(BytesIO(bruto)) as arquivo:
            nomes = [nome for nome in arquivo.namelist() if nome.lower().endswith(".xml")]
            if not nomes:
                return None
            return arquivo.read(nomes[0])
    except zipfile.BadZipFile:
        return None


def _ler_bytes(arquivo):
    if arquivo is None:
        raise ValidationError({"arquivo": "Escolha o XML da nota fiscal."})
    tamanho = getattr(arquivo, "size", None)
    if tamanho is not None and tamanho > LIMITE_XML:
        raise ValidationError({"arquivo": "O XML é grande demais (máximo 8 MB)."})
    bruto = arquivo.read()
    if len(bruto) > LIMITE_XML:
        raise ValidationError({"arquivo": "O XML é grande demais (máximo 8 MB)."})
    if not bruto:
        raise ValidationError({"arquivo": "O arquivo está vazio."})
    if bruto[:4] == b"%PDF":
        raise ValidationError(
            {"arquivo": "Isso é um PDF da DANFE. Envie o XML da NF-e (ou CT-e), não o PDF."}
        )
    if bruto[:2] == b"PK":
        extraido = _abrir_zip(bruto)
        if extraido is None:
            raise ValidationError({"arquivo": "O ZIP não contém um XML de nota."})
        bruto = extraido
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return bruto.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError({"arquivo": "Não foi possível ler o arquivo."})


def _raiz_xml(xml_texto):
    texto = xml_texto.strip()
    if "<" in texto:
        texto = texto[texto.find("<") :]
    baixo = texto[:400].lower()
    if "<html" in baixo or "<!doctype html" in baixo:
        raise ValidationError(
            {"arquivo": "Isso é a página da DANFE, não o XML. No emissor, exporte o XML da NF-e."}
        )
    try:
        return ET.fromstring(texto)
    except ET.ParseError as exc:
        raise ValidationError(
            {"arquivo": "XML inválido. Use o arquivo XML baixado da NF-e ou do CT-e."}
        ) from exc


_UNIDADES_MASSA = {
    "KG",
    "KGM",
    "KGS",
    "KILO",
    "KILOS",
    "QUILO",
    "QUILOS",
    "T",
    "TON",
    "TONELADA",
    "TONELADAS",
}


def _eh_massa(unidade):
    limpa = re.sub(r"[^A-Z]", "", (unidade or "").upper())
    return limpa in _UNIDADES_MASSA or limpa.startswith("KG")


def _peso_item_nfe(prod):
    ucom = _primeiro_texto(prod, "uCom")
    utrib = _primeiro_texto(prod, "uTrib")
    qcom = _decimal(_primeiro_texto(prod, "qCom"), 3)
    qtrib = _decimal(_primeiro_texto(prod, "qTrib"), 3)
    if _eh_massa(utrib) and qtrib > 0:
        return qtrib
    if _eh_massa(ucom) and qcom > 0:
        return qcom
    return Decimal("0.000")


def _completar_peso_itens(itens, peso_total):
    if not itens:
        return itens
    usados = sum((item["peso"] or Decimal("0") for item in itens), Decimal("0"))
    resto = (peso_total or Decimal("0")) - usados
    faltam = [item for item in itens if not item["peso"]]
    if not faltam or resto <= 0:
        return itens
    base = sum((item["valor"] or Decimal("0") for item in faltam), Decimal("0"))
    chave = "valor"
    if base <= 0:
        base = sum((item["quantidade"] or Decimal("0") for item in faltam), Decimal("0"))
        chave = "quantidade"
    if base <= 0:
        return itens
    acumulado = Decimal("0")
    for indice, item in enumerate(faltam):
        if indice == len(faltam) - 1:
            item["peso"] = (resto - acumulado).quantize(Decimal("0.001"))
        else:
            parte = (resto * (item[chave] or Decimal("0")) / base).quantize(Decimal("0.001"))
            item["peso"] = parte
            acumulado += parte
    return itens


def _itens_nfe(inf):
    itens = []
    for det in _todos(inf, "det"):
        prod = _filho(det, "prod") or det
        descricao = _primeiro_texto(prod, "xProd")
        if not descricao:
            continue
        itens.append(
            {
                "codigo": _primeiro_texto(prod, "cProd")[:40],
                "descricao": descricao[:180],
                "quantidade": _decimal(_primeiro_texto(prod, "qCom", "qTrib"), 3),
                "unidade": (_primeiro_texto(prod, "uCom", "uTrib") or "UN")[:12],
                "peso": _peso_item_nfe(prod),
                "valor": _decimal(_primeiro_texto(prod, "vProd"), 2),
            }
        )
    return itens


def _itens_cte(inf):
    itens = []
    for infq in _todos(inf, "infQ"):
        descricao = _primeiro_texto(infq, "tpMed") or "Carga do CT-e"
        itens.append(
            {
                "codigo": "",
                "descricao": descricao[:180],
                "quantidade": _decimal(_primeiro_texto(infq, "qCarga"), 3),
                "unidade": (_primeiro_texto(infq, "cUnid") or "UN")[:12],
                "peso": _decimal(_primeiro_texto(infq, "qCarga"), 3),
                "valor": Decimal("0.00"),
            }
        )
    if itens:
        return itens
    pred = _primeiro_texto(inf, "proPred", "xOutCat")
    if pred:
        return [
            {
                "codigo": "",
                "descricao": pred[:180],
                "quantidade": Decimal("1.000"),
                "unidade": "UN",
                "peso": _decimal(_primeiro_texto(inf, "qCarga"), 3),
                "valor": _decimal(_primeiro_texto(inf, "vCarga", "vTPrest"), 2),
            }
        ]
    return []


def extrair_documento(xml_texto):
    raiz = _raiz_xml(xml_texto)
    inf = _achar(raiz, "infNFe", "infNFeProc")
    if inf is not None:
        return _de_nfe(inf)
    inf = _achar(raiz, "infCte", "infCTe")
    if inf is not None:
        return _de_cte(inf)
    nomes = sorted({_local(el.tag) for el in list(raiz)[:12] if _local(el.tag)})
    detalhe = f" Tags encontradas: {', '.join(nomes[:8])}." if nomes else ""
    raise ValidationError(
        {
            "arquivo": (
                "Este XML não é uma NF-e nem um CT-e. "
                "Envie o XML baixado no emissor/SEFAZ, não o PDF da DANFE."
                + detalhe
            )
        }
    )


def _de_nfe(inf):
    ide = _filho(inf, "ide")
    dest = _filho(inf, "dest")
    emit = _filho(inf, "emit")
    entrega = _filho(inf, "entrega")
    transp = _filho(inf, "transp")
    total = _achar(inf, "ICMSTot") or _filho(_filho(inf, "total"), "ICMSTot")

    numero = _primeiro_texto(ide, "nNF") or _nnf_da_chave(inf.attrib.get("Id", ""))
    cliente = (
        _primeiro_texto(dest, "xNome")
        or _primeiro_texto(entrega, "xNome")
        or _primeiro_texto(emit, "xNome")
        or _primeiro_texto(dest, "CNPJ", "CPF")
    )
    valor = _decimal(_primeiro_texto(total, "vNF") or _primeiro_texto(inf, "vNF"), 2)
    peso = Decimal("0.000")
    for vol in _todos(transp if transp is not None else inf, "vol"):
        candidato = _primeiro_texto(vol, "pesoB", "pesoL")
        if candidato:
            peso += _decimal(candidato, 3)
    itens = _itens_nfe(inf)
    if peso <= 0:
        peso = sum((item["peso"] or Decimal("0") for item in itens), Decimal("0"))
    else:
        itens = _completar_peso_itens(itens, peso)
    placa = _placa(_primeiro_texto(transp if transp is not None else inf, "placa"))
    return _fechar(numero, cliente, peso, valor, placa, itens, "NF-e")


def _de_cte(inf):
    numero = _primeiro_texto(inf, "nCT") or _nnf_da_chave(inf.attrib.get("Id", ""))
    cliente = (
        _primeiro_texto(_filho(inf, "dest"), "xNome")
        or _primeiro_texto(_filho(inf, "receb"), "xNome")
        or _primeiro_texto(_filho(inf, "rem"), "xNome")
        or _primeiro_texto(inf, "xNome")
    )
    valor = _decimal(_primeiro_texto(inf, "vTPrest", "vCarga"), 2)
    peso = _decimal(_primeiro_texto(inf, "qCarga"), 3)
    placa = _placa(_primeiro_texto(inf, "placa"))
    itens = _itens_cte(inf)
    return _fechar(numero, cliente, peso, valor, placa, itens, "CT-e")


def _fechar(numero, cliente, peso, valor, placa, itens, tipo):
    if not numero:
        raise ValidationError({"arquivo": f"O {tipo} não informa o número do documento."})
    if not cliente:
        raise ValidationError({"arquivo": f"O {tipo} não informa o nome do destinatário."})
    if not itens:
        raise ValidationError({"arquivo": f"O {tipo} não tem produtos ou carga para listar."})
    return {
        "numero": normalizar_nota(numero),
        "cliente": cliente[:160],
        "peso": peso,
        "valor": valor,
        "placa": placa,
        "itens": itens,
    }


def gravar_nota_xml(dados):
    return salvar_nota_local(dados)


def importar_xml(arquivo):
    dados = extrair_documento(_ler_bytes(arquivo))
    return gravar_nota_xml(dados)
