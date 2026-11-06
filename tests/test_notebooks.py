"""Los notebooks del repo son exactamente los que genera scripts/gen_notebooks.py, son válidos y su código compila."""
import ast
import importlib.util
import json
from pathlib import Path

import nbformat

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gen_notebooks", RAIZ / "scripts" / "gen_notebooks.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def test_notebooks_actualizados():
    for nombre, nb in gen.generar().items():
        ruta = RAIZ / "notebooks" / nombre
        assert ruta.exists(), f"Falta {ruta}: correr python scripts/gen_notebooks.py"
        assert ruta.read_text(encoding="utf-8") == gen.serializar(nb), \
            f"{nombre} no coincide con gen_notebooks.py: regenerar con python scripts/gen_notebooks.py"


def test_notebooks_validos_y_compilan():
    for nombre in gen.generar():
        ruta = RAIZ / "notebooks" / nombre
        nb = nbformat.read(str(ruta), as_version=4)
        nbformat.validate(nb)
        for celda in nb.cells:
            if celda.cell_type == "code":
                assert not celda.outputs, f"{nombre}: el notebook debe versionarse sin salidas"
                ast.parse(celda.source)


def test_badges_apuntan_al_repo():
    for nombre in gen.generar():
        texto = json.dumps(json.loads((RAIZ / "notebooks" / nombre).read_text(encoding="utf-8")))
        assert f"colab.research.google.com/github/santiagoriverti/oportunidades_inversion/blob/main/notebooks/{nombre}" in texto
