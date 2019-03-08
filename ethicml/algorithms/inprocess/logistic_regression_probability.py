"""
Logistic regaression with soft output
"""

import pandas as pd
from sklearn.linear_model import LogisticRegression

from ethicml.algorithms.inprocess.in_algorithm import InAlgorithm


class LRProb(InAlgorithm):
    """Logistic regression with soft output"""
    def _run(self, train, test):
        clf = LogisticRegression(solver='liblinear', random_state=888)
        clf.fit(train.x, train.y.values.ravel())
        return pd.DataFrame(clf.predict_proba(test.x)[:, 1], columns=["preds"])

    @property
    def name(self) -> str:
        return "Logistic Regression Prob"


def main():
    """main method to run model"""
    model = LRProb()
    train, test = model.load_data()
    model.save_predictions(model.run(train, test))


if __name__ == "__main__":
    main()