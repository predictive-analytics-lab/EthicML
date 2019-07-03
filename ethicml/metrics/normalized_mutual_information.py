"""
For assessing Nomralized Mutual Information
"""
import pandas as pd
from sklearn.metrics import normalized_mutual_info_score as nmis

from ethicml.utility.data_structures import DataTuple, Predictions
from .metric import Metric


class NMI(Metric):
    """Normalized Mutual Information"""

    def __init__(self, pos_class: int = 1, base: str = "y"):
        super().__init__(pos_class=pos_class)
        if base not in ["s", "y"]:
            raise NotImplementedError("Can only calculate NMI of predictions with regard to y or s")
        self.base = base

    def score(self, prediction: Predictions, actual: DataTuple) -> float:
        assert isinstance(prediction.hard, pd.DataFrame)
        if self.base == "y":
            base_values = actual.y.values.flatten()
        else:
            base_values = actual.s.values.flatten()
        return nmis(base_values, prediction.hard.values.flatten(), average_method="geometric")

    @property
    def name(self) -> str:
        return f"NMI preds and {self.base}"
