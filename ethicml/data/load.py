"""
Loads Data from .csv files
"""

import os
from typing import List, Dict
import pandas as pd

from ..common import ROOT_DIR
from ..algorithms.utils import DataTuple
from .configurable_dataset import ConfigurableDataset
from .dataset import Dataset


def load_data(dataset: Dataset) -> DataTuple:
    """Load dataset from its CSV file

    Args:
        dataset: dataset object

    Returns:
        DataTuple with dataframes of features, labels and sensitive attributes
    """
    filename = dataset.filename
    data_loc: str = "{}/data/csvs/{}".format(ROOT_DIR, filename)
    dataframe: pd.DataFrame = pd.read_csv(data_loc)
    assert isinstance(dataframe, pd.DataFrame)

    feature_split = dataset.feature_split

    x_data = dataframe[feature_split['x']]
    s_data = dataframe[feature_split['s']]
    y_data = dataframe[feature_split['y']]

    return DataTuple(x=x_data, s=s_data, y=y_data)


def create_data_obj(filepath: str,
                    s_columns: List[str],
                    y_columns: List[str],
                    additional_to_drop=None) -> Dataset:
    """

    Args:
        filepath:
        s_columns:
        y_columns:
        additional_to_drop:

    Returns:

    """
    if additional_to_drop is None:
        additional_to_drop = []

    conf: ConfigurableDataset = ConfigurableDataset()
    conf.filename = os.path.basename(filepath)

    dataframe: pd.DataFrame = pd.read_csv(filepath)

    columns: List[str] = dataframe.columns.values.tolist()
    for s_col in s_columns:
        columns.remove(s_col)
    for y_col in y_columns:
        columns.remove(y_col)
    for additional in additional_to_drop:
        columns.remove(additional)

    feat_split: Dict[str, List[str]] = {
        'x': columns,
        's': s_columns,
        'y': y_columns
    }
    conf.feature_split = feat_split

    return conf