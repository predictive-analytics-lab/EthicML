"""
Test the loading data capability
"""

from typing import Dict
import pandas as pd

from ethicml.common import ROOT_DIR
from ethicml.data.adult import Adult
from ethicml.data.compas import Compas
from ethicml.data.dataset import Dataset
from ethicml.data.german import German
from ethicml.data.load import load_data, create_data_obj
from ethicml.data.sqf import Sqf
from ethicml.data.test import Test
from ethicml.data.violent_recidivism import Violent


def test_can_load_test_data():
    data_loc: str = "{}/data/csvs/test.csv".format(ROOT_DIR)
    data: pd.DataFrame = pd.read_csv(data_loc)
    assert data is not None


def test_load_data():
    data: Dict[str, pd.DataFrame] = load_data(Test())
    assert (2000, 2) == data['x'].shape
    assert (2000, 1) == data['s'].shape
    assert (2000, 1) == data['y'].shape


def test_discrete_data():
    data: Dict[str, pd.DataFrame] = load_data(Adult())
    assert (48842, 102) == data['x'].shape
    assert (48842, 1) == data['s'].shape
    assert (48842, 1) == data['y'].shape
    assert 97 == len(Adult().discrete_features)
    assert 94 == len(Adult(split='Race').discrete_features)
    assert 58 == len(Adult(split='Nationality').discrete_features)


def test_load_data_as_a_function():
    data_loc: str = "{}/data/csvs/test.csv".format(ROOT_DIR)
    data_obj: Dataset = create_data_obj(data_loc, s_columns=["s"], y_columns=["y"])
    assert data_obj is not None
    assert data_obj.feature_split['x'] == ['a1', 'a2']
    assert data_obj.feature_split['s'] == ['s']
    assert data_obj.feature_split['y'] == ['y']
    assert data_obj.filename == "test.csv"


def test_joining_2_load_functions():
    data_loc: str = "{}/data/csvs/test.csv".format(ROOT_DIR)
    data_obj: Dataset = create_data_obj(data_loc, s_columns=["s"], y_columns=["y"])
    data: Dict[str, pd.DataFrame] = load_data(data_obj)
    assert (2000, 2) == data['x'].shape
    assert (2000, 1) == data['s'].shape
    assert (2000, 1) == data['y'].shape


def test_load_adult():
    data: Dict[str, pd.DataFrame] = load_data(Adult())
    assert (48842, 102) == data['x'].shape
    assert (48842, 1) == data['s'].shape
    assert (48842, 1) == data['y'].shape


def test_load_compas():
    data: Dict[str, pd.DataFrame] = load_data(Compas())
    assert (6167, 404) == data['x'].shape
    assert (6167, 1) == data['s'].shape
    assert (6167, 1) == data['y'].shape


def test_load_sqf():
    data: Dict[str, pd.DataFrame] = load_data(Sqf())
    assert (12344, 144) == data['x'].shape
    assert (12344, 1) == data['s'].shape
    assert (12344, 1) == data['y'].shape


def test_load_german():
    data: Dict[str, pd.DataFrame] = load_data(German())
    assert (1000, 51) == data['x'].shape
    assert (1000, 1) == data['s'].shape
    assert (1000, 1) == data['y'].shape


def test_load_violent():
    data: Dict[str, pd.DataFrame] = load_data(Violent())
    assert (4010, 326) == data['x'].shape
    assert (4010, 1) == data['s'].shape
    assert (4010, 1) == data['y'].shape


def test_load_adult_explicitly_sex():
    data: Dict[str, pd.DataFrame] = load_data(Adult("Sex"))
    assert (48842, 102) == data['x'].shape
    assert (48842, 1) == data['s'].shape
    assert (48842, 1) == data['y'].shape


def test_load_compas_explicitly_sex():
    data: Dict[str, pd.DataFrame] = load_data(Compas("Sex"))
    assert (6167, 400) == data['x'].shape
    assert (6167, 1) == data['s'].shape
    assert (6167, 1) == data['y'].shape


def test_load_adult_race():
    data: Dict[str, pd.DataFrame] = load_data(Adult("Race"))
    assert (48842, 99) == data['x'].shape
    assert (48842, 5) == data['s'].shape
    assert (48842, 1) == data['y'].shape


def test_load_compas_race():
    data: Dict[str, pd.DataFrame] = load_data(Compas("Race"))
    assert (6167, 404) == data['x'].shape
    assert (6167, 1) == data['s'].shape
    assert (6167, 1) == data['y'].shape


def test_load_adult_race_sex():
    data: Dict[str, pd.DataFrame] = load_data(Adult("Race-Sex"))
    assert (48842, 97) == data['x'].shape
    assert (48842, 6) == data['s'].shape
    assert (48842, 1) == data['y'].shape


def test_load_compas_race_sex():
    data: Dict[str, pd.DataFrame] = load_data(Compas("Race-Sex"))
    assert (6167, 403) == data['x'].shape
    assert (6167, 2) == data['s'].shape
    assert (6167, 1) == data['y'].shape


def test_load_adult_nationality():
    data: Dict[str, pd.DataFrame] = load_data(Adult("Nationality"))
    assert (48842, 63) == data['x'].shape
    assert (48842, 41) == data['s'].shape
    assert (48842, 1) == data['y'].shape


def test_race_feature_split():
    adult: Adult = Adult()
    adult.set_s(["race_White"])
    adult.set_s_prefix(["race"])
    adult.set_y(["salary_>50K"])
    adult.set_y_prefix(["salary"])

    data: Dict[str, pd.DataFrame] = load_data(adult)

    assert (48842, 99) == data['x'].shape
    assert (48842, 1) == data['s'].shape
    assert (48842, 1) == data['y'].shape


def test_additional_columns_load():
    data_loc: str = "{}/data/csvs/adult.csv".format(ROOT_DIR)
    data_obj: Dataset = create_data_obj(data_loc,
                                        s_columns=["race_White"],
                                        y_columns=["salary_>50K"],
                                        additional_to_drop=[
                                            "race_Black",
                                            "salary_<=50K"
                                        ])
    data: Dict[str, pd.DataFrame] = load_data(data_obj)

    assert (48842, 102) == data['x'].shape
    assert (48842, 1) == data['s'].shape
    assert (48842, 1) == data['y'].shape
