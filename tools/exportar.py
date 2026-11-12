"""Exporta versiones de la Biblia desde el motor local de STEP a archivos de texto para VRChat.

Uso: python tools/exportar.py SpaRV1909 KJV

Cada libro es un .txt: la primera linea es "Nombre|capitulos|pagina de inicio de cada capitulo",
y cada linea siguiente es una pagina del libro de Reimajo, con <br> como salto de linea.
"""
import html
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request

MOTOR = "http://localhost:8989/rest"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWORD = os.path.join(os.environ["APPDATA"], "Sword", "mods.d")

# Una pagina de la plantilla mide 313x476 con letra 20
CARACTERES_POR_PAGINA = 560

# Idiomas sin espacios entre palabras: se pagina por ancho de caracter y se corta en cualquier sitio.
# Un caracter chino o japones ocupa lo que dos latinos, asi que cabe la mitad por pagina.
SIN_ESPACIOS = ("zh", "ja")
# El coreano si separa palabras, pero sus letras tambien son anchas: se mide igual y se corta en espacios
ANCHOS = SIN_ESPACIOS + ("ko",)
ANCHO_POR_PAGINA = 520
CJK = "⺀-⿿　-ヿ㐀-䶿一-鿿豈-﫿＀-￯"
# Puntuacion tras la que es mejor cortar una pagina
PAUSAS = "。，、；：？！」』）"
# El modulo tradicional separa palabras y pierde a veces el espacio de respeto antes de 神;
# el simplificado es el mismo texto caracter a caracter y lo tiene bien, asi que se copia de ahi
ESPACIOS_DE = {"ChiUn": "ChiUns"}

LICENCIAS_LIBRES = (
    "public domain",
    "creative commons: cc0",
    "creative commons: by 4",
    "creative commons: by-sa",
    "gpl",
    "gfdl",
)

LIBROS = (
    "Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth Job Ps Prov Eccl Song "
    "Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal "
    "Matt Mark Luke John Acts Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm Heb Jas "
    "1Pet 2Pet 1John 2John 3John Jude Rev"
).split()


# En estos libros "Jude.1" significa el versiculo 1, asi que se piden enteros
UN_CAPITULO = {"Obad", "Phlm", "2John", "3John", "Jude"}


def leer_conf(version):
    ruta = os.path.join(SWORD, version.lower() + ".conf")
    with open(ruta, encoding="utf-8", errors="ignore") as archivo:
        texto = archivo.read()
    campo = lambda clave: (re.search(rf"^{clave}=(.*)$", texto, re.M | re.I) or [None, ""])[1].strip()
    return {
        "licencia": campo("DistributionLicense"),
        "descripcion": campo("Description"),
        "fuente": campo("TextSource"),
        "idioma": campo("Lang"),
        "direccion": campo("Direction") or "LtoR",
    }


def pedir_capitulo(version, referencia, idioma):
    consulta = urllib.parse.quote(f"version={version}|reference={referencia}", safe="")
    # El motor toma el idioma de los nombres de libro de esta cabecera
    peticion = urllib.request.Request(
        f"{MOTOR}/search/masterSearch/{consulta}/HVN/NONE",
        headers={"Accept-Language": idioma},
    )
    with urllib.request.urlopen(peticion, timeout=60) as respuesta:
        return json.load(respuesta)


def versiculos(marcado):
    trozos = re.split(r"<span[^>]*class='verse(?: [^']*)?'[^>]*>", marcado)[1:]
    salida = []
    for trozo in trozos:
        numero = re.search(r"class='verseNumber'>([^<]+)<", trozo)
        cuerpo = re.sub(r"<span class='verseNumber'>[^<]*</span>", "", trozo)
        cuerpo = re.sub(r"<[^>]+>", "", cuerpo)
        cuerpo = re.sub(r"\s+", " ", html.unescape(cuerpo)).replace("‏", "").strip()
        if cuerpo:
            salida.append((numero.group(1) if numero else "", cuerpo))
    return salida


def paginar(capitulos):
    """Reparte los capitulos en paginas sin partir versiculos, salvo los que no caben en una."""
    paginas = []
    inicios = []
    actual = ""

    def cerrar():
        nonlocal actual
        if actual:
            paginas.append(actual)
            actual = ""

    for titulo, lista in capitulos:
        cerrar()
        inicios.append(len(paginas))
        actual = f"<b>{titulo}</b><br>"
        for numero, texto in lista:
            trozo = f"<b>{numero}</b> {texto} "
            if len(actual) + len(trozo) > CARACTERES_POR_PAGINA:
                cerrar()
            while len(trozo) > CARACTERES_POR_PAGINA:
                corte = trozo.rfind(" ", 0, CARACTERES_POR_PAGINA)
                paginas.append(trozo[:corte])
                trozo = trozo[corte + 1 :]
            actual += trozo
    cerrar()
    return paginas, inicios


def sin_espacios(idioma):
    return idioma.split("-")[0].lower() in SIN_ESPACIOS


def juntar(texto):
    """Quita los espacios entre caracteres chinos o japoneses. Algunos modulos separan las palabras
    con espacios; el chino deja solo el espacio de respeto antes de 神 (Dios)."""
    por_palabras = re.search(rf"[{CJK}] +(?!神)[{CJK}]", texto)
    if por_palabras:
        # Con palabras separadas, 神 solo es Dios cuando va suelto, no en compuestos como 神蹟
        texto = re.sub(rf"(?<=[{CJK}]) +(?=神(?: |[{PAUSAS}「『]|$))", "\0", texto)
        texto = re.sub(rf"(?<=[{CJK}]) +(?=[{CJK}])", "", texto).replace("\0", " ")
        return texto.strip()
    return texto.strip()


def copiar_espacios(texto, modelo):
    """Pone en texto los espacios de modelo cuando, sin espacios, los dos miden lo mismo."""
    limpio = texto.replace(" ", "")
    if len(limpio) != len(modelo.replace(" ", "")):
        return texto
    salida, i = [], 0
    for c in modelo:
        if c == " ":
            salida.append(" ")
        else:
            salida.append(limpio[i])
            i += 1
    return "".join(salida)


def ancho(texto):
    """Ancho visible: las etiquetas no cuentan y un caracter ancho vale por dos."""
    visible = re.sub(r"<[^>]+>", "", texto.replace("<br>", "\n"))
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in visible)


def ancho_doble(idioma):
    return idioma.split("-")[0].lower() in ANCHOS


def cortar(trozo, espacio, en_espacios=False):
    """Mayor corte de trozo que cabe en espacio, mejor tras puntuacion (o en un espacio) y sin partir etiquetas."""
    corte, medido = 0, 0
    i = 0
    while i < len(trozo):
        if trozo[i] == "<":
            fin = trozo.find(">", i)
            i = fin + 1 if fin >= 0 else len(trozo)
            continue
        medido += 2 if unicodedata.east_asian_width(trozo[i]) in "WF" else 1
        if medido > espacio:
            break
        i += 1
        corte = i
    if en_espacios:
        hueco = trozo.rfind(" ", 0, corte + 1)
        return hueco + 1 if hueco > 0 else corte
    for j in range(corte, max(0, corte - 24), -1):
        if trozo[j - 1] in PAUSAS:
            return j
    return corte


def paginar_ancho(capitulos, en_espacios):
    """Como paginar, midiendo por ancho. Sin espacios entre palabras se corta entre caracteres."""
    separador = " " if en_espacios else ""
    paginas = []
    inicios = []
    actual = ""

    def cerrar():
        nonlocal actual
        if actual:
            paginas.append(actual)
            actual = ""

    for titulo, lista in capitulos:
        cerrar()
        inicios.append(len(paginas))
        actual = f"<b>{titulo}</b><br>"
        for numero, texto in lista:
            trozo = f"<b>{numero}</b>{separador}{texto}{separador}"
            if ancho(actual) + ancho(trozo) > ANCHO_POR_PAGINA:
                cerrar()
            while ancho(trozo) > ANCHO_POR_PAGINA:
                corte = cortar(trozo, ANCHO_POR_PAGINA, en_espacios)
                paginas.append(trozo[:corte].rstrip())
                trozo = trozo[corte:]
            actual += trozo
    cerrar()
    return paginas, inicios


def exportar_libro(version, libro, idioma):
    capitulos = []
    referencia = libro if libro in UN_CAPITULO else f"{libro}.1"
    nombre = libro
    vistos = set()
    while referencia not in vistos:
        vistos.add(referencia)
        datos = pedir_capitulo(version, referencia, idioma)
        lista = versiculos(datos["value"])
        if sin_espacios(idioma):
            lista = [(numero, juntar(texto)) for numero, texto in lista]
            if version in ESPACIOS_DE:
                modelo = dict(versiculos(pedir_capitulo(ESPACIOS_DE[version], referencia, idioma)["value"]))
                lista = [(n, copiar_espacios(t, juntar(modelo[n])) if n in modelo else t) for n, t in lista]
            # Espacio que no corta la linea: si no, Unity salta de linea antes de cada 神 y deja renglones cortos
            lista = [(n, t.replace(" ", " ")) for n, t in lista]
        if not lista:
            break
        titulo = (datos.get("longName") or referencia).replace("‏", "").strip()
        capitulos.append((titulo, lista))
        nombre = re.sub(r"\s+\d+$", "", titulo)
        siguiente = datos.get("nextChapter") or {}
        clave = siguiente.get("osisKeyId") or ""
        if not clave.startswith(libro + "."):
            break
        referencia = clave
    return nombre, capitulos


def exportar(version):
    conf = leer_conf(version)
    if not conf["licencia"].lower().startswith(LICENCIAS_LIBRES):
        print(f"{version}: omitida, licencia no libre: {conf['licencia']}")
        return None

    carpeta = os.path.join(RAIZ, "textos", version)
    os.makedirs(carpeta, exist_ok=True)
    libros = []
    for libro in LIBROS:
        nombre, capitulos = exportar_libro(version, libro, conf["idioma"])
        if not capitulos:
            continue
        if ancho_doble(conf["idioma"]):
            paginas, inicios = paginar_ancho(capitulos, not sin_espacios(conf["idioma"]))
        else:
            paginas, inicios = paginar(capitulos)
        cabecera = f"{nombre}|{len(capitulos)}|{','.join(map(str, inicios))}"
        with open(os.path.join(carpeta, libro + ".txt"), "w", encoding="utf-8", newline="\n") as archivo:
            archivo.write("\n".join([cabecera] + paginas))
        libros.append({"id": libro, "nombre": nombre, "capitulos": len(capitulos), "paginas": len(paginas)})
        print(f"{version} {libro}: {len(capitulos)} capitulos, {len(paginas)} paginas")

    entrada = {"version": version, **conf, "libros": libros}
    with open(os.path.join(carpeta, "acerca.json"), "w", encoding="utf-8", newline="\n") as archivo:
        json.dump(entrada, archivo, ensure_ascii=False, indent=1)
    return entrada


def main():
    indice = os.path.join(RAIZ, "textos", "indice.json")
    versiones = {}
    if os.path.exists(indice):
        with open(indice, encoding="utf-8") as archivo:
            versiones = {v["version"]: v for v in json.load(archivo)}
    for version in sys.argv[1:]:
        entrada = exportar(version)
        if entrada:
            versiones[version] = {k: v for k, v in entrada.items() if k != "libros"} | {"libros": len(entrada["libros"])}
    with open(indice, "w", encoding="utf-8", newline="\n") as archivo:
        json.dump(list(versiones.values()), archivo, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
