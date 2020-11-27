"""How would a perfect predictor perform?"""
from ethicml import DataTuple, InAlgorithm, Prediction, TestTuple, implements


class Oracle(InAlgorithm):
    """A perfect predictor.

    Can only be used if test is a DataTuple, rather than the usual TestTuple.
    This model isn't inetended for general use,
    but can be useful if you want to either do a sanity check, or report potential values.
    """

    @implements(InAlgorithm)
    def __init__(self) -> None:
        super().__init__(name="Oracle", is_fairness_algo=False)

    @implements(InAlgorithm)
    def run(self, train: DataTuple, test: TestTuple) -> Prediction:
        assert isinstance(test, DataTuple), "test must be a DataTuple."
        return Prediction(hard=test.y[test.y.columns[0]])