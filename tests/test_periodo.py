"""Unit tests for Periodo anio relaxation (2014 lower bound, no DB).

Pure pydantic validation: entity + create/edit DTOs accept 2014, reject 2013,
and keep the 2100 upper bound.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.domain.dto.create import CreatePeriodo
from src.domain.dto.edit import EditPeriodo
from src.domain.models.entities import Periodo


def test_periodo_entity_accepts_2014():
    p = Periodo(nombre="Julio 2014", anio=2014, mes=7)
    assert p.anio == 2014


def test_periodo_entity_rejects_2013():
    with pytest.raises(ValidationError):
        Periodo(nombre="Julio 2013", anio=2013, mes=7)


def test_create_periodo_accepts_2014():
    dto = CreatePeriodo(nombre="Julio 2014", anio=2014, mes=7)
    assert dto.anio == 2014


def test_create_periodo_rejects_2013():
    with pytest.raises(ValidationError):
        CreatePeriodo(nombre="Julio 2013", anio=2013, mes=7)


def test_edit_periodo_accepts_2014():
    dto = EditPeriodo(anio=2014)
    assert dto.anio == 2014


def test_edit_periodo_rejects_2013():
    with pytest.raises(ValidationError):
        EditPeriodo(anio=2013)


def test_periodo_keeps_upper_bound_2100():
    p = Periodo(nombre="Enero 2100", anio=2100, mes=1)
    assert p.anio == 2100
    with pytest.raises(ValidationError):
        Periodo(nombre="Enero 2101", anio=2101, mes=1)
