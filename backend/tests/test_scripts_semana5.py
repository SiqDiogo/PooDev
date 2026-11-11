from pathlib import Path
import runpy

import pytest


@pytest.mark.parametrize("arquivo", sorted(Path(__file__).parent.glob("teste_*semana5.py")), ids=lambda p: p.stem)
def test_scripts_da_semana5(arquivo):
    runpy.run_path(str(arquivo), run_name="__main__")
