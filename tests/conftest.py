"""This file is automatically imported by pytest (no need to import it) and defines shared fixtures."""
import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pandas as pd
import pytest

import ethicml as em
from ethicml import DataTuple, TrainTestPair


@pytest.fixture(scope="session")
def toy_train_test() -> TrainTestPair:
    """By making this a fixture, pytest can cache the result."""
    data: DataTuple = em.toy().load()
    train: DataTuple
    test: DataTuple
    train, test = em.train_test_split(data)
    return TrainTestPair(train, test.remove_y())


@pytest.fixture(scope="session")
def toy_train_val() -> TrainTestPair:
    """By making this a fixture, pytest can cache the result."""
    data: DataTuple = em.toy().load()
    train: DataTuple
    test: DataTuple
    train, test = em.train_test_split(data)
    return TrainTestPair(train, test)


@pytest.fixture(scope="module")
def plot_cleanup():
    """Clean up after the tests by removing the `plots` and `results` directories."""
    yield None
    print("remove generated directory")
    plt_dir = Path(".") / "plots"
    res_dir = Path(".") / "results"
    if plt_dir.exists():
        shutil.rmtree(plt_dir)
    if res_dir.exists():
        shutil.rmtree(res_dir)


@pytest.fixture(scope="function")
def results_cleanup():
    """Clean up after the tests by removing the `results` directory."""
    yield None
    print("remove generated directory")
    res_dir = Path(".") / "results"
    if res_dir.exists():
        shutil.rmtree(res_dir)


@pytest.fixture(scope="session")
def simple_data() -> DataTuple:
    """Simple data for testing splitting methods."""
    # visual representation of the data:
    # s: ...111111111111111111111111111111111111111111111111111111111111110000000000000000000000000
    # y: ...111111111111111111111111111111111111110000000000000000000000001111111111000000000000000
    return DataTuple(
        x=pd.DataFrame([0] * 1000, columns=["x"]),
        s=pd.DataFrame([1] * 750 + [0] * 250, columns=["s"]),
        y=pd.DataFrame([1] * 500 + [0] * 250 + [1] * 100 + [0] * 150, columns=["y"]),
        name="TestData",
    )


@pytest.fixture(scope="session")
def data_root() -> Path:
    """Common data root."""
    return em.ROOT_PATH / "data" / "csvs"


@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """Clean up after the tests by removing the `results` directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def get_id(value):
    """Get ID."""
    return getattr(value, "name", value)


@pytest.fixture(scope="function")
def simulate_no_torch() -> Generator[None, None, None]:
    # ======= set up ========
    torch_available = em.common.TORCH_AVAILABLE
    torchvision_available = em.common.TORCHVISION_AVAILABLE
    em.common.TORCH_AVAILABLE = False
    em.common.TORCHVISION_AVAILABLE = False

    yield  # run test

    # ====== tear down =======
    em.common.TORCH_AVAILABLE = torch_available
    em.common.TORCHVISION_AVAILABLE = torchvision_available
