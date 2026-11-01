# lumbrera-textos

Textos de la Biblia en archivos estaticos para un libro dentro de un mundo de VRChat.
Se generan desde un motor local de STEPBible con `tools/exportar.py`.

Solo se incluyen versiones cuyo modulo declara una licencia libre (dominio publico, CC0, CC BY,
CC BY-SA, GPL o GFDL). La licencia y la descripcion de cada una estan en `textos/<version>/acerca.json`.

## Formato

`textos/<version>/<libro>.txt`: la primera linea es `Nombre|capitulos|pagina de inicio de cada capitulo`,
y cada linea siguiente es una pagina, con `<br>` como salto de linea.

Este proyecto no contiene codigo de STEPBible.
