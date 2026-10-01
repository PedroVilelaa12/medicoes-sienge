import pytest
from apoio import relogio_fixo

from medicoes.config import Config
from medicoes.estado import Armazem
from medicoes.orquestrador import Orquestrador
from medicoes.sienge.falso import ClienteFalso


@pytest.fixture
def cliente() -> ClienteFalso:
    return ClienteFalso()


@pytest.fixture
def armazem() -> Armazem:
    return Armazem()


@pytest.fixture
def orquestrador(cliente, armazem) -> Orquestrador:
    return Orquestrador(cliente, armazem, Config(), relogio_fixo)
