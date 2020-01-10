"""For assessing ProbPos."""

import pandas as pd

from ethicml.common import implements
from ethicml.utility.data_structures import DataTuple
from .confusion_matrix import confusion_matrix
from .metric import Metric


class ProbPos(Metric):
    """Probability of positive prediction."""

    @implements(Metric)
    def score(self, prediction: pd.DataFrame, actual: DataTuple) -> float:
        _, f_pos, _, t_pos = confusion_matrix(prediction, actual, pos_cls=self.positive_class)

        return (t_pos + f_pos) / prediction.size

    @property
    def name(self) -> str:
        """Getter for the metric name."""
        return "prob_pos"
