"""
Testing for plotting functionality
"""
from typing import Tuple, List

from matplotlib import pyplot as plt

import pytest

from ethicml.algorithms.inprocess import SVM, LR, Kamiran
from ethicml.algorithms.preprocess import Upsampler
from ethicml.evaluators import evaluate_models
from ethicml.metrics import Accuracy, CV, TPR, ProbPos, NMI
from ethicml.utility import DataTuple, Results
from ethicml.data import load_data, Adult, Toy
from ethicml.preprocessing import train_test_split
from ethicml.visualisation import save_2d_plot, save_label_plot, save_jointplot, plot_mean_std_box
from tests.run_algorithm_test import get_train_test


@pytest.mark.usefixtures("plot_cleanup")  # fixtures are defined in `tests/conftest.py`
def test_plot():
    """test plot"""
    train, _ = get_train_test()
    save_2d_plot(train, "./plots/test.png")


@pytest.mark.usefixtures("plot_cleanup")
def test_joint_plot():
    """test joint plot"""
    train, _ = get_train_test()
    save_jointplot(train, "./plots/joint.png")


@pytest.mark.usefixtures("plot_cleanup")
def test_label_plot():
    """test label plot"""
    data: DataTuple = load_data(Adult())
    train_test: Tuple[DataTuple, DataTuple] = train_test_split(data)
    train, _ = train_test

    save_label_plot(train, "./plots/labels.png")


@pytest.mark.usefixtures("plot_cleanup")
def test_plot_evals():
    """test plot evals"""
    results: Results = evaluate_models(
        datasets=[Adult(), Toy()],
        preprocess_models=[Upsampler(strategy="preferential")],
        inprocess_models=[LR(), SVM(kernel='linear'), Kamiran()],
        metrics=[Accuracy(), CV()],
        per_sens_metrics=[TPR(), ProbPos()],
        repeats=3,
        test_mode=True,
        delete_prev=True,
    )

    figs_and_plots: List[Tuple[plt.Figure, plt.Axes]]

    # plot with metrics
    figs_and_plots = plot_mean_std_box(results, Accuracy(), ProbPos())
    # num(datasets) * num(preprocess) * num(accuracy combinations) * num(prop_pos combinations)
    assert len(figs_and_plots) == 2 * 2 * 1 * 2

    # plot with column names
    figs_and_plots = plot_mean_std_box(results, "Accuracy", "prob_pos_s_0")
    assert len(figs_and_plots) == 1 * 2 * 1 * 1

    with pytest.raises(ValueError, match='No matching columns found for Metric "NMI preds and y".'):
        plot_mean_std_box(results, Accuracy(), NMI())

    with pytest.raises(ValueError, match='No column named "unknown metric".'):
        plot_mean_std_box(results, "unknown metric", Accuracy())
