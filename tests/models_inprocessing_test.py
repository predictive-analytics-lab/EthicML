"""EthicML Tests"""
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Tuple

import pandas as pd
import pytest
from pytest import approx

from ethicml.algorithms import run_blocking
from ethicml.algorithms.inprocess import (
    LR,
    LRCV,
    MLP,
    SVM,
    Agarwal,
    Corels,
    InAlgorithm,
    InAlgorithmAsync,
    InstalledModel,
    Kamiran,
    LRProb,
    Majority,
    SVMAsync,
    ZafarAccuracy,
    ZafarBaseline,
    ZafarEqOdds,
    ZafarEqOpp,
    ZafarFairness,
)
from ethicml.data import compas, toy, load_data
from ethicml.evaluators import CrossValidator, CVResults, evaluate_models_async, run_in_parallel
from ethicml.metrics import AbsCV, Accuracy, Metric
from ethicml.preprocessing import query_dt, train_test_split
from ethicml.utility import DataTuple, Heaviside, Prediction, SoftPrediction, TrainTestPair
from tests.run_algorithm_test import count_true, get_train_test


class InprocessTest(NamedTuple):
    """Define a test for an inprocess model"""

    name: str
    model: InAlgorithm
    num_pos: int


INPROCESS_TESTS = [
    InprocessTest(name="SVM", model=SVM(), num_pos=242),
    InprocessTest(name="Majority", model=Majority(), num_pos=400),
    InprocessTest(name="MLP", model=MLP(), num_pos=242),
    InprocessTest(name="Logistic Regression, C=1.0", model=LR(), num_pos=240),
    InprocessTest(name="LRCV", model=LRCV(), num_pos=241),
]


@pytest.mark.parametrize("name,model,num_pos", INPROCESS_TESTS)
def test_inprocess(name: str, model: InAlgorithm, num_pos: int):
    """Test an inprocess model"""
    train, test = get_train_test()

    assert isinstance(model, InAlgorithm)
    assert model is not None
    assert model.name == name

    predictions: Prediction = model.run(train, test)
    assert count_true(predictions.hard.values == 1) == num_pos
    assert count_true(predictions.hard.values == 0) == len(predictions) - num_pos


def test_corels(toy_train_test: TrainTestPair) -> None:
    """test corels"""
    model: InAlgorithm = Corels()
    assert model is not None
    assert model.name == "CORELS"

    train_toy, test_toy = toy_train_test
    with pytest.raises(RuntimeError):
        model.run(train_toy, test_toy)

    data: DataTuple = load_data(compas())
    train, test = train_test_split(data)

    predictions: Prediction = model.run(train, test)
    expected_num_pos = 428
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == expected_num_pos
    assert (
        predictions.hard.values[predictions.hard.values == 0].shape[0]
        == len(predictions) - expected_num_pos
    )


def test_cv_svm():
    """test cv svm"""
    train, test = get_train_test()

    hyperparams: Dict[str, List[Any]] = {"C": [1, 10, 100], "kernel": ["rbf", "linear"]}

    svm_cv = CrossValidator(SVM, hyperparams, folds=3)

    assert svm_cv is not None

    cv_results = svm_cv.run(train)

    best_model = cv_results.best(Accuracy())
    assert isinstance(best_model, InAlgorithm)

    predictions: Prediction = best_model.run(train, test)
    expected_num_pos = 242
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == expected_num_pos
    assert (
        predictions.hard.values[predictions.hard.values == 0].shape[0]
        == len(predictions) - expected_num_pos
    )


def test_threaded_svm():
    """test threaded svm"""
    train, test = get_train_test()

    model: InAlgorithmAsync = SVMAsync()
    assert model is not None
    assert model.name == "SVM"

    predictions: Prediction = run_blocking(model.run_async(train, test))
    expected_num_pos = 242
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == expected_num_pos
    assert (
        predictions.hard.values[predictions.hard.values == 0].shape[0]
        == len(predictions) - expected_num_pos
    )


def test_cv_lr(toy_train_test: TrainTestPair) -> None:
    """test cv lr"""
    train, test = toy_train_test

    hyperparams: Dict[str, List[float]] = {"C": [0.01, 0.1, 1.0]}

    lr_cv = CrossValidator(LR, hyperparams, folds=3)

    assert lr_cv is not None

    measure = Accuracy()
    cv_results: CVResults = lr_cv.run(train, measures=[measure])

    assert cv_results.best_hyper_params(measure)["C"] == 1.0
    best_model = cv_results.best(measure)
    assert isinstance(best_model, InAlgorithm)

    predictions: Prediction = best_model.run(train, test)
    expected_num_pos = 240
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == expected_num_pos
    assert (
        predictions.hard.values[predictions.hard.values == 0].shape[0]
        == len(predictions) - expected_num_pos
    )


def test_parallel_cv_lr(toy_train_test: TrainTestPair) -> None:
    """test parallel cv lr"""
    train, test = toy_train_test

    hyperparams: Dict[str, List[float]] = {"C": [0.001, 0.01]}

    lr_cv = CrossValidator(LR, hyperparams, folds=2, max_parallel=1)

    assert lr_cv is not None

    measure = Accuracy()
    cv_results: CVResults = run_blocking(lr_cv.run_async(train, measures=[measure]))

    assert cv_results.best_hyper_params(measure)["C"] == 0.01
    best_model = cv_results.best(measure)
    assert isinstance(best_model, InAlgorithm)

    predictions: Prediction = best_model.run(train, test)
    expected_num_pos = 244
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == expected_num_pos
    assert (
        predictions.hard.values[predictions.hard.values == 0].shape[0]
        == len(predictions) - expected_num_pos
    )


def test_fair_cv_lr(toy_train_test: TrainTestPair) -> None:
    """test fair cv lr"""
    train, _ = toy_train_test

    hyperparams: Dict[str, List[float]] = {"C": [1, 1e-1, 1e-2, 1e-3, 1e-4, 1e-5, 1e-6]}

    lr_cv = CrossValidator(LR, hyperparams, folds=3)

    assert lr_cv is not None

    primary = Accuracy()
    fair_measure = AbsCV()
    cv_results = lr_cv.run(train, measures=[primary, fair_measure])

    best_result = cv_results.get_best_in_top_k(primary, fair_measure, top_k=3)
    print(best_result)

    assert best_result.params["C"] == 1e-5
    assert best_result.scores["Accuracy"] == approx(0.9300, rel=1e-4)
    assert best_result.scores["CV absolute"] == approx(0.8485, rel=1e-4)


# @pytest.fixture(scope="module")
# def kamishima():
#     kamishima_algo = Kamishima()
#     yield kamishima_algo
#     print("teardown Kamishima")
#     kamishima_algo.remove()


# def test_kamishima(kamishima):
#     train, test = get_train_test()

#     model: InAlgorithmAsync = kamishima
#     assert model.name == "Kamishima"

#     assert model is not None

#     predictions: Prediction = run_blocking(model.run_async(train, test))
#     assert predictions.hard.values[predictions.hard.values == 1].shape[0] == 208
#     assert predictions.hard.values[predictions.hard.values == -1].shape[0] == 192


@pytest.fixture(scope="module")
def zafar_models():
    """Create and destroy Zafar models

    Returns:
        Tuple of three Zafar model classes
    """
    zafarAcc_algo = ZafarAccuracy
    zafarBas_algo = ZafarBaseline
    zafarFai_algo = ZafarFairness
    yield (zafarAcc_algo, zafarBas_algo, zafarFai_algo)
    print("teardown Zafar Accuracy")
    zafarAcc_algo().remove()


def test_zafar(zafar_models, toy_train_test: TrainTestPair) -> None:
    """

    Args:
        zafarModels:
        toy_train_test:
    """
    train, test = toy_train_test

    model: InAlgorithmAsync = zafar_models[0]()
    assert model.name == "ZafarAccuracy, γ=0.5"

    assert model is not None

    predictions: Prediction = model.run(train, test)
    expected_num_pos = 242
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == expected_num_pos
    assert (
        predictions.hard.values[predictions.hard.values == 0].shape[0]
        == len(predictions) - expected_num_pos
    )

    predictions = run_blocking(model.run_async(train, test))
    expected_num_pos = 242
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == expected_num_pos
    assert (
        predictions.hard.values[predictions.hard.values == 0].shape[0]
        == len(predictions) - expected_num_pos
    )

    hyperparams: Dict[str, List[float]] = {"gamma": [1, 1e-1, 1e-2]}

    model = zafar_models[0]
    zafar_cv = CrossValidator(model, hyperparams, folds=3)

    assert zafar_cv is not None

    primary = Accuracy()
    fair_measure = AbsCV()
    cv_results: CVResults = zafar_cv.run(train, measures=[primary, fair_measure])

    best_result = cv_results.get_best_in_top_k(primary, fair_measure, top_k=3)

    assert best_result.params["gamma"] == 0.01
    assert best_result.scores["Accuracy"] == approx(0.995, abs=0.001)
    assert best_result.scores["CV absolute"] == approx(0.851, abs=0.001)

    model = zafar_models[1]()
    assert model.name == "ZafarBaseline"

    assert model is not None

    predictions = model.run(train, test)
    expected_num_pos = 241
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == expected_num_pos
    assert (
        predictions.hard.values[predictions.hard.values == 0].shape[0]
        == len(predictions) - expected_num_pos
    )

    predictions = run_blocking(model.run_async(train, test))
    expected_num_pos = 241
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == expected_num_pos
    assert (
        predictions.hard.values[predictions.hard.values == 0].shape[0]
        == len(predictions) - expected_num_pos
    )

    model = zafar_models[2]()
    assert model.name == "ZafarFairness, c=0.001"

    assert model is not None

    predictions = model.run(train, test)
    expected_num_pos = 242
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == expected_num_pos
    assert (
        predictions.hard.values[predictions.hard.values == 0].shape[0]
        == len(predictions) - expected_num_pos
    )

    predictions = run_blocking(model.run_async(train, test))
    expected_num_pos = 242
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == expected_num_pos
    assert (
        predictions.hard.values[predictions.hard.values == 0].shape[0]
        == len(predictions) - expected_num_pos
    )

    hyperparams = {"c": [1, 1e-1, 1e-2]}

    model = zafar_models[2]
    zafar_cv = CrossValidator(model, hyperparams, folds=3)

    assert zafar_cv is not None

    primary = Accuracy()
    fair_measure = AbsCV()
    cv_results: CVResults = zafar_cv.run(train, measures=[primary, fair_measure])

    best_result = cv_results.get_best_in_top_k(primary, fair_measure, top_k=3)

    assert best_result.params["c"] == 0.01
    assert best_result.scores["Accuracy"] == approx(0.830, abs=0.001)
    assert best_result.scores["CV absolute"] == approx(0.970, rel=0.001)

    # ==================== Zafar Equality of Opportunity ========================
    zafar_eq_opp: InAlgorithm = ZafarEqOpp()
    assert zafar_eq_opp.name == "ZafarEqOpp, τ=5.0, μ=1.2"

    predictions = zafar_eq_opp.run(train, test)
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == 241

    # ==================== Zafar Equalised Odds ========================
    zafar_eq_odds: InAlgorithm = ZafarEqOdds()
    assert zafar_eq_odds.name == "ZafarEqOdds, τ=5.0, μ=1.2"

    predictions = zafar_eq_odds.run(train, test)
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == 241


def test_local_installed_lr(toy_train_test: TrainTestPair):
    """test local installed lr"""
    train, test = toy_train_test

    class _LocalInstalledLR(InstalledModel):
        def __init__(self):
            super().__init__(
                name="local installed LR", dir_name=".", top_dir="", executable=sys.executable
            )

        def _script_command(
            self, train_path: Path, test_path: Path, pred_path: Path
        ) -> (List[str]):
            script = "./tests/local_installed_lr.py"
            return [
                script,
                str(train_path),
                str(test_path),
                str(pred_path),
            ]

    model: InAlgorithm = _LocalInstalledLR()
    assert model is not None
    assert model.name == "local installed LR"

    predictions: Prediction = model.run(train, test)
    expected_num_pos = 240
    assert count_true(predictions.hard.values == 1) == expected_num_pos
    assert count_true(predictions.hard.values == 0) == len(predictions) - expected_num_pos


def test_agarwal():
    """test agarwal"""
    train, test = get_train_test()

    agarwal_variants: List[InAlgorithmAsync] = []
    model_names: List[str] = []
    expected_results: List[Tuple[int, int]] = []

    agarwal_variants.append(Agarwal())
    model_names.append("Agarwal, LR, DP")
    expected_results.append((241, 159))

    agarwal_variants.append(Agarwal(fairness="EqOd"))
    model_names.append("Agarwal, LR, EqOd")
    expected_results.append((240, 160))

    agarwal_variants.append(Agarwal(classifier="SVM"))
    model_names.append("Agarwal, SVM, DP")
    expected_results.append((241, 159))

    agarwal_variants.append(Agarwal(classifier="SVM", kernel="linear"))
    model_names.append("Agarwal, SVM, DP")
    expected_results.append((242, 158))

    agarwal_variants.append(Agarwal(classifier="SVM", fairness="EqOd"))
    model_names.append("Agarwal, SVM, EqOd")
    expected_results.append((241, 159))

    agarwal_variants.append(Agarwal(classifier="SVM", fairness="EqOd", kernel="linear"))
    model_names.append("Agarwal, SVM, EqOd")
    expected_results.append((241, 159))

    results = run_blocking(
        run_in_parallel(agarwal_variants, [TrainTestPair(train, test)], max_parallel=1)
    )

    for model, results_for_model, model_name, (pred_true, pred_false) in zip(
        agarwal_variants, results, model_names, expected_results
    ):
        assert model.name == model_name
        assert count_true(results_for_model[0].hard.to_numpy() == 1) == pred_true, model_name
        assert count_true(results_for_model[0].hard.to_numpy() == 0) == pred_false, model_name


def test_threaded_agarwal():
    """test threaded agarwal"""
    models: List[InAlgorithmAsync] = [Agarwal(classifier="SVM", fairness="EqOd")]

    class AssertResult(Metric):
        _name = "assert_result"

        def score(self, prediction, actual) -> float:
            return (
                count_true(prediction.hard.values == 1) == 241
                and count_true(prediction.hard.values == 0) == 159
            )

    results = run_blocking(
        evaluate_models_async(
            datasets=[toy()], inprocess_models=models, metrics=[AssertResult()], delete_prev=True
        )
    )
    assert results.data["assert_result"].iloc[0] == 1.0


def test_lr_prob():
    """test lr prob"""
    train, test = get_train_test()

    model: LRProb = LRProb()
    assert model.name == "Logistic Regression Prob, C=1.0"

    heavi = Heaviside()

    predictions: SoftPrediction = model.run(train, test)
    hard_predictions = pd.Series(heavi.apply(predictions.soft.to_numpy()))
    pd.testing.assert_series_equal(hard_predictions, predictions.hard)
    assert hard_predictions.values[hard_predictions.values == 1].shape[0] == 240
    assert hard_predictions.values[hard_predictions.values == 0].shape[0] == 160


def test_kamiran(toy_train_test: TrainTestPair):
    """test kamiran"""
    train, test = toy_train_test

    kamiran_model: InAlgorithm = Kamiran()
    assert kamiran_model is not None
    assert kamiran_model.name == "Kamiran & Calders LR"

    predictions: Prediction = kamiran_model.run(train, test)
    assert predictions.hard.values[predictions.hard.values == 1].shape[0] == 241
    assert predictions.hard.values[predictions.hard.values == 0].shape[0] == 159

    # remove all samples with s=0 & y=1 from the data
    train_no_s0y1 = query_dt(train, "sensitive_attr != 0 | decision != 1")
    predictions = kamiran_model.run(train_no_s0y1, test)
