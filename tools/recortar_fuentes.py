"""Recorta fuentes chinas y japonesas a los caracteres que usan las Biblias exportadas.

Uso: python tools/recortar_fuentes.py <carpeta de salida> --fuente JP ruta.ttf ChiUn ... [--fuente SC ruta.ttf ...]

Cada --fuente lleva un nombre corto, el archivo de la fuente (estatica o variable, se fija a Regular)
y las versiones cuyos caracteres debe cubrir. La fuente resultante se llama "Biblia <nombre>",
para que Unity la encuentre como respaldo sin confundirla con otras Noto del proyecto.
Necesita: pip install fonttools
"""
import argparse
import glob
import os

from fontTools import subset
from fontTools.ttLib import TTFont

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTOS = os.path.join(RAIZ, "textos")

# Siempre incluidos: puntuacion ancha y numeros de ancho completo, por si aparecen en otros textos
EXTRA = "".join(chr(c) for c in range(0x3000, 0x3040)) + "".join(chr(c) for c in range(0xFF01, 0xFF5F))


def caracteres(versiones):
    vistos = set(EXTRA)
    for version in versiones:
        rutas = glob.glob(os.path.join(TEXTOS, version, "*.txt")) + [os.path.join(TEXTOS, version, "acerca.json")]
        if len(rutas) < 2:
            raise SystemExit(f"No hay textos exportados de {version}")
        for ruta in rutas:
            with open(ruta, encoding="utf-8") as archivo:
                vistos.update(archivo.read())
    # Lo latino lo pone la fuente principal
    return {c for c in vistos if ord(c) >= 0x2E80}


def recortar(nombre, ruta, versiones, salida):
    fuente = TTFont(ruta)
    if "fvar" in fuente:
        from fontTools.varLib import instancer
        fuente = instancer.instantiateVariableFont(fuente, {"wght": 400})
    usados = caracteres(versiones)
    opciones = subset.Options()
    opciones.layout_features = ["*"]
    opciones.name_IDs = ["*"]
    opciones.notdef_outline = True
    recorte = subset.Subsetter(opciones)
    recorte.populate(unicodes=[ord(c) for c in usados])
    recorte.subset(fuente)

    familia = f"Biblia {nombre}"
    for registro in fuente["name"].names:
        if registro.nameID in (1, 16):
            registro.string = familia
        elif registro.nameID in (4,):
            registro.string = familia
        elif registro.nameID == 6:
            registro.string = familia.replace(" ", "")
        elif registro.nameID in (2, 17):
            registro.string = "Regular"

    destino = os.path.join(salida, f"Biblia{nombre}.ttf")
    fuente.save(destino)
    cmap = fuente.getBestCmap()
    faltan = [c for c in usados if ord(c) not in cmap]
    print(f"{destino}: {len(usados)} caracteres pedidos, {len(cmap)} en la fuente, "
          f"{os.path.getsize(destino) // 1024} KB, sin glifo: {len(faltan)} {''.join(sorted(faltan))[:60]}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("salida")
    p.add_argument("--fuente", nargs="+", action="append", required=True, metavar="NOMBRE RUTA VERSION")
    a = p.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    for nombre, ruta, *versiones in a.fuente:
        recortar(nombre, ruta, versiones, a.salida)


if __name__ == "__main__":
    main()
