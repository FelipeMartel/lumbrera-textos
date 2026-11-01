"""Instala en el motor local la Biblia libre mas completa de cada idioma y la exporta.

Uso: python tools/tanda.py <carpeta mods.d de CrossWire> [--lista]
Con --lista solo muestra lo elegido.
"""
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from exportar import LICENCIAS_LIBRES, MOTOR, RAIZ

# Escrituras que el libro aun no puede mostrar bien: fuentes extra o derecha a izquierda
PENDIENTES = {"", "hbo", "syr", "zh", "lzh", "ja", "ko", "hy", "my", "cop", "got", "chr", "cu", "tlh", "mlf", "ksw"}

# Estos idiomas ya tienen version exportada
HECHOS = {"es", "en"}

# Por debajo de esto el modulo suele ser solo una parte de la Biblia
TAMANO_MINIMO = 1_500_000


def elegir(carpeta):
    mejores = {}
    for ruta in glob.glob(os.path.join(carpeta, "*.conf")):
        with open(ruta, encoding="utf-8", errors="ignore") as archivo:
            texto = archivo.read()
        campo = lambda clave: (re.search(rf"^{clave}=(.*)$", texto, re.M | re.I) or [None, ""])[1].strip()
        if campo("ModDrv").lower() not in ("rawtext", "ztext", "rawtext4", "ztext4"):
            continue
        if not campo("DistributionLicense").lower().startswith(LICENCIAS_LIBRES):
            continue
        idioma = campo("Lang").split("-")[0]
        if idioma in PENDIENTES or idioma in HECHOS:
            continue
        tamano = int(campo("InstallSize") or 0)
        if idioma not in mejores or tamano > mejores[idioma][1]:
            mejores[idioma] = (os.path.basename(ruta)[:-5], tamano, campo("Description"))
    return mejores


def pedir(ruta):
    with urllib.request.urlopen(f"{MOTOR}/{ruta}", timeout=120) as respuesta:
        return json.load(respuesta)


def instalar(sigla):
    urllib.request.urlopen(f"{MOTOR}/setup/installBible/-1/{urllib.parse.quote(sigla)}", timeout=120).read()
    for _ in range(200):
        avance = pedir(f"setup/getProgressOnInstallation/{urllib.parse.quote(sigla)}")
        if float(avance[0] if isinstance(avance, list) else avance) >= 1:
            return
        time.sleep(3)
    raise TimeoutError(sigla)


def main():
    mejores = elegir(sys.argv[1])
    instaladas = {m["initials"].lower() for m in pedir("module/getAllModules")}
    disponibles = {m["initials"].lower(): m["initials"] for m in pedir("module/getAllInstallableModules/-1/BIBLE,COMMENTARY")}
    siglas = []
    for idioma, (modulo, tamano, descripcion) in sorted(mejores.items()):
        nota = "" if tamano >= TAMANO_MINIMO else " (parcial)"
        print(f"{idioma}: {modulo} {tamano // 1000} KB{nota} - {descripcion}", flush=True)
        if modulo in instaladas:
            siglas.append(modulo)
        elif modulo in disponibles:
            siglas.append(disponibles[modulo])
        else:
            print(f"  no disponible en el motor: {modulo}", flush=True)
    if "--lista" in sys.argv:
        return

    resultado = {}
    for sigla in siglas:
        try:
            if sigla.lower() not in instaladas:
                instalar(sigla)
            subprocess.run([sys.executable, os.path.join(RAIZ, "tools", "exportar.py"), sigla], check=True)
            resultado[sigla] = "ok"
        except Exception as error:
            resultado[sigla] = str(error)
            print(f"FALLO {sigla}: {error}", flush=True)
    print(json.dumps(resultado, indent=1), flush=True)


if __name__ == "__main__":
    main()
