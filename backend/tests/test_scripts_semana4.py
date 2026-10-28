from pathlib import Path
import runpy

import pytest


@pytest.mark.parametrize("arquivo", sorted(Path(__file__).parent.glob("teste_*semana4.py")), ids=lambda p: p.stem)
def test_scripts_da_semana4(arquivo):
    # Executa também as verificações que foram escritas como scripts.
    runpy.run_path(str(arquivo), run_name="__main__")
