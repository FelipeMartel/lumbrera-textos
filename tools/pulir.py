"""Arregla lo que el motor no resuelve, sin volver a exportar.

Nombres de libro: el motor solo los traduce a algunos idiomas y en el resto usa los de su idioma
por defecto, asi que esas versiones pasan a los nombres en ingles de la KJV.
Esperanto: el modulo trae un caracter invalido dentro de palabras como "kor?oj" y como apostrofo final.
"""
import glob
import json
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTOS = os.path.join(RAIZ, "textos")


def leer(ruta):
    with open(ruta, encoding="utf-8") as archivo:
        return archivo.read()


def escribir(ruta, texto):
    with open(ruta, "w", encoding="utf-8", newline="\n") as archivo:
        archivo.write(texto)


def cambiar_nombres(version):
    for ruta in glob.glob(os.path.join(TEXTOS, version, "*.txt")):
        libro = os.path.basename(ruta)
        nuevo = leer(os.path.join(TEXTOS, "KJV", libro)).split("|", 1)[0]
        texto = leer(ruta)
        viejo = texto.split("|", 1)[0]
        texto = nuevo + texto[len(viejo):]
        texto = re.sub(rf"<b>{re.escape(viejo)}( \d+)?</b>", lambda m: f"<b>{nuevo}{m.group(1) or ''}</b>", texto)
        escribir(ruta, texto)

    ruta = os.path.join(TEXTOS, version, "acerca.json")
    datos = json.loads(leer(ruta))
    for entrada in datos["libros"]:
        entrada["nombre"] = leer(os.path.join(TEXTOS, "KJV", entrada["id"] + ".txt")).split("|", 1)[0]
    escribir(ruta, json.dumps(datos, ensure_ascii=False, indent=1))


def arreglar_esperanto():
    for ruta in glob.glob(os.path.join(TEXTOS, "Esperanto", "*.txt")):
        texto = re.sub(r"�(?=\w)", "", leer(ruta)).replace("�", "'")
        escribir(ruta, texto)


def sin_traducir(version):
    """Compara con la Reina-Valera: un idioma distinto con sus mismos nombres no esta traducido."""
    iguales = 0
    rutas = glob.glob(os.path.join(TEXTOS, version, "*.txt"))
    for ruta in rutas:
        espanol = leer(os.path.join(TEXTOS, "SpaRV", os.path.basename(ruta))).split("|", 1)[0]
        iguales += leer(ruta).split("|", 1)[0] == espanol
    return iguales == len(rutas)


arreglar_esperanto()
for carpeta in sorted(os.listdir(TEXTOS)):
    if carpeta != "SpaRV" and os.path.isdir(os.path.join(TEXTOS, carpeta)) and sin_traducir(carpeta):
        print(carpeta)
        cambiar_nombres(carpeta)
