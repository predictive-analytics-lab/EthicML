"""
Evaluator for a metric per sensitive attribute class
"""

from typing import Dict, List
import numpy as np
import pandas as pd

from ethicml.metrics.metric import Metric


def metric_per_sensitive_attribute(
        predictions: np.array,
        actual: Dict[str, pd.DataFrame],
        metric: Metric) -> Dict[int, float]:

    predictions: pd.DataFrame = pd.DataFrame(predictions, columns=["preds"])
    amalgamated = pd.concat([actual['x'],
                             actual['s'],
                             actual['y'],
                             predictions], axis=1)

    assert amalgamated.shape[0] == actual['x'].shape[0]

    per_sensitive_attr: Dict[int, float] = {}

    s_columns: List[str] = [s_col for s_col in actual['s'].columns]
    y_columns: List[str] = [y_col for y_col in actual['y'].columns]
    assert len(y_columns) == 1

    for y_col in y_columns:
        for s_col in s_columns:
            for unique_s in actual['s'][s_col].unique():
                actual_y = {'y': amalgamated[actual['s'][s_col] == unique_s][y_col]}
                pred_y = amalgamated[actual['s'][s_col] == unique_s]['preds']
                per_sensitive_attr[unique_s] = metric.score(pred_y, actual_y)

    return per_sensitive_attr


def diff_per_sensitive_attribute(per_sens_res: Dict[int, float]) -> Dict[str, float]:

    sens_values = list(per_sens_res.keys())
    diff_per_sens = {}

    for _, i in enumerate(sens_values):
        for j in range(i+1, len(sens_values)):
            key: str = "{}-{}".format(sens_values[i], sens_values[j])
            i_value: float = per_sens_res[sens_values[i]]
            j_value: float = per_sens_res[sens_values[j]]
            diff_per_sens[key] = abs(i_value - j_value)

    return diff_per_sens