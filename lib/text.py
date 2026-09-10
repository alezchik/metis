#!/usr/bin/env python3
"""
Tokenizador lexical compartido -- extraido de lib/index.py para que
lib/evaluate.py (Fase 8, docs/adr/0022) pueda reusar exactamente el mismo
tokenizador al elegir palabras clave para acotar la busqueda de codigo candidato en
evaluate_implementation, en vez de reimplementarlo (seccion 5.2, "no hay cuatro
implementaciones, hay una logica"). lib/index.py sigue siendo el unico lugar que
arma el indice TF-IDF en si -- este modulo es solo el tokenizador de base.
"""
from __future__ import annotations

import re

TOKEN_RE = re.compile(r"[a-z0-9áéíóúñü]+", re.IGNORECASE)

# Stopwords minimas (es/en) para que ni el indice lexical (lib/index.py) ni la
# extraccion de palabras clave de lib/evaluate.py "matcheen" cualquier cosa por
# palabras funcionales -- sin esto se violaria en la practica "evidencia o
# silencio" (seccion 1, principio 3).
STOPWORDS = frozenset(
    """
    a al algo algunas algunos ante antes como con contra cual cuando de del desde donde
    durante e el ella ellas ellos en entre era erais eramos eran eras eres es esa esas
    ese esos esta estaba estabais estabamos estaban estabas estad estada estadas estado
    estados estamos estan estando estar estara estaran estaras estare estareis estaremos
    estaria estariais estariamos estarian estarias este esto estos estoy fue fuera
    fuerais fueramos fueran fueras fueron fuese fueseis fuesemos fuesen fueses fui fuimos
    ha habia habiais habiamos habian habias habida habidas habido habidos habiendo
    habla habla hasta hay la las le les lo los mas me mi mia mias mientras mio mios mis
    misma mismas mismo mismos mucho muchos muy nada ni no nos nosotras nosotros nuestra
    nuestras nuestro nuestros o os otra otras otro otros para pero poco por porque que
    quien quienes se sea seamos sean seas sentid ser sera seran seras sere sereis
    seremos seria seriais seriamos serian serias si sido siendo sin sobre sois somos
    son soy su sus suya suyas suyo suyos tambien tanto te tendra tendran tendras tendre
    tendreis tendremos tendria tendriais tendriamos tendrian tendrias tened teneis
    tenemos tener tenga tengamos tengan tengas tengo tenia teniais teniamos tenian
    tenias ti tiene tienen tienes todo todos tu tus tuya tuyas tuyo tuyos un una uno
    unos vosotras vosotros vuestra vuestras vuestro vuestros y ya yo
    the a an is are was were be been being to of in on for with at by from as it its
    this that these those and or but if then else not no
    """.split()
)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOPWORDS]
