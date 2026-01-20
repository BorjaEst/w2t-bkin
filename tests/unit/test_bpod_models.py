from __future__ import annotations

from dataclasses import dataclass

from w2t_bkin.models import BpodData


@dataclass
class _DummyMatStruct:
    """Minimal stand-in for scipy.io.matlab.mat_struct.

    scipy's mat_struct exposes fields via attributes (stored in __dict__),
    not mapping methods like dict.get().
    """

    nTrials: int


def test_bpoddata_n_trials_with_mat_struct_sessiondata() -> None:
    data = {"SessionData": _DummyMatStruct(nTrials=7)}
    bpod = BpodData(data=data, source_files=[])
    assert bpod.n_trials == 7


def test_bpoddata_n_trials_with_dict_sessiondata() -> None:
    data = {"SessionData": {"nTrials": 5}}
    bpod = BpodData(data=data, source_files=[])
    assert bpod.n_trials == 5
