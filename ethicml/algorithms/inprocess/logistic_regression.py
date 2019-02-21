"""
Wrapper around Sci-Kit Learn Logistic Regression
"""

from typing import Dict
import pandas as pd
from sklearn.linear_model import LogisticRegression
from .in_algorithm import InAlgorithm


class LR(InAlgorithm):
    """Logistic regression with hard predictions"""
    def run(self, train: Dict[str, pd.DataFrame], test: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        clf = LogisticRegression(random_state=888)
        clf.fit(train['x'], train['y'].values.ravel())
        return pd.DataFrame(clf.predict(test['x']), columns=["preds"])

    @property
    def name(self) -> str:
        return "Logistic Regression"


class LRProb(InAlgorithm):
    """Logistic regression with soft output"""
    def run(self, train: Dict[str, pd.DataFrame], test: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        clf = LogisticRegression(random_state=888)
        clf.fit(train['x'], train['y'].values.ravel())
        return pd.DataFrame(clf.predict_proba(test['x'])[:, 1], columns=["preds"])

    @property
    def name(self) -> str:
        return "Logistic Regression- prob out"
