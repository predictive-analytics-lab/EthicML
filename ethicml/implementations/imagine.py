import math
import os
import shutil
from pathlib import Path
from typing import Sequence, Tuple, List

import torch
from dataclasses import dataclass
from torch import nn, optim
from torch.autograd import Function
from torch.utils.data import DataLoader
import torch.distributions as td
import torch.nn.functional as F
import numpy as np
import pandas as pd
from ethicml.algorithms.inprocess import LR

from ethicml.data import Dataset
from ethicml.evaluators import run_metrics
from ethicml.implementations.beutel import set_seed
from ethicml.implementations.imagine_modules.adversary import FeatAdversary, PredAdversary
from ethicml.implementations.imagine_modules.features import Features
from ethicml.implementations.imagine_modules.predictor import Predictor
from ethicml.implementations.pytorch_common import TestDataset, CustomDataset, RAdam
from ethicml.implementations.utils import (
    pre_algo_argparser,
    load_data_from_flags,
    save_transformations,
)
from ethicml.implementations.vfae import get_dataset_obj_by_name
from ethicml.metrics import ProbPos, Accuracy, TPR
from ethicml.preprocessing import LabelBinarizer, train_test_split
from ethicml.preprocessing.adjust_labels import assert_binary_labels
from ethicml.utility import DataTuple, TestTuple, Heaviside

_PRED_LD = 1
FEAT_LD = 60


@dataclass(frozen=True)  # "frozen" makes it immutable
class ImagineSettings:
    """Settings for the Imagined Examples algorithm. This is basically a type-safe flag-object."""

    enc_size: Sequence[int]
    adv_size: Sequence[int]
    pred_size: Sequence[int]
    batch_size: int
    epochs: int
    adv_weight: float
    validation_pcnt: float
    dataset: str
    sample: int
    start_from: int


def train_and_transform(
    train: DataTuple, test: TestTuple, flags: ImagineSettings
) -> Tuple[DataTuple, TestTuple]:
    dataset = get_dataset_obj_by_name(flags.dataset)

    device = torch.device("cuda:0" if (torch.cuda.is_available()) else "cpu")

    set_seed(888, torch.cuda.is_available())

    post_process = False

    try:
        assert_binary_labels(train)
    except AssertionError:
        processor = LabelBinarizer()
        train = processor.adjust(train)
        post_process = True

    # print(f"Batch Size: {flags.batch_size}")

    # Set up the data
    _train, validate = train_test_split(train, train_percentage=0.9)

    train_data = CustomDataset(_train)
    train_loader = DataLoader(train_data, batch_size=flags.batch_size)

    valid_data = CustomDataset(validate)
    valid_loader = DataLoader(valid_data, batch_size=flags.batch_size)

    all_data = CustomDataset(train)
    all_data_loader = DataLoader(all_data, batch_size=flags.batch_size)

    test_data = TestDataset(test)
    test_loader = DataLoader(test_data, batch_size=flags.batch_size)

    # Build Network
    current_epoch = 0
    model = Imagine(data=train_data, dataset=dataset).to(device)
    optimizer = RAdam(model.parameters(), lr=1e-3)
    if int(flags.start_from) >= 0:
        current_epoch = int(flags.start_from)
        filename = 'checkpoint_%03d.pth.tar' % current_epoch
        PATH = Path(".") / "checkpoint" / filename
        dict_ = torch.load(PATH)
        # print(f"loaded: {dict_['epoch']}")
        model.load_state_dict(dict_['model'])
        optimizer.load_state_dict(dict_['optimizer'])
    else:
        PATH = Path(".") / "checkpoint"
        import shutil

        if PATH.exists():
            shutil.rmtree(PATH)

    # scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=flags.epochs)
    scheduler = optim.lr_scheduler.ExponentialLR(optimizer, gamma=0.995)

    prob_pos = ProbPos()
    prob_pos = prob_pos.score(_train.y, _train)
    # print(f"prob pos: {prob_pos}")

    # Run Network
    for epoch in range(current_epoch, current_epoch + int(flags.epochs)):
        train_model(epoch, model, train_loader, valid_loader, optimizer, device, prob_pos, flags)
        # if epoch % 15 == 0:
        scheduler.step(epoch)

    PATH = Path(".") / "checkpoint" / 'model_best.pth.tar'
    dict_ = torch.load(PATH)
    # print(f"Best model was at step: {dict_['epoch']}")
    model.load_state_dict(dict_['model'])
    model.eval()

    # Transform output
    actual_feats: pd.DataFrame = pd.DataFrame(columns=_train.x.columns)
    feats_encs: pd.DataFrame = pd.DataFrame(columns=list(range(FEAT_LD)))
    feats_train: pd.DataFrame = pd.DataFrame(columns=_train.x.columns)
    s_1_list: pd.DataFrame = pd.DataFrame(columns=_train.s.columns)
    s_2_list: pd.DataFrame = pd.DataFrame(columns=_train.s.columns)
    actual_labels: pd.DataFrame = pd.DataFrame(columns=_train.y.columns)
    direct_preds_train: pd.DataFrame = pd.DataFrame(columns=_train.y.columns)
    preds_encs: pd.DataFrame = pd.DataFrame(columns=_train.y.columns)
    preds_train: pd.DataFrame = pd.DataFrame(columns=_train.y.columns)

    SAMPLES = flags.sample

    with torch.no_grad():
        for _x, _s, _y, _out in all_data_loader:

            _x = _x.to(device)
            _s = _s.to(device)
            _y = _y.to(device)
            _out = [out.to(device) for out in _out]

            ###
            # original data
            ###
            _s_1 = _s.detach().clone()
            _s_2 = _s.detach().clone()
            feat_enc, feat_dec, feat_s_pred, pred_enc, pred_dec, pred_s_pred, direct_prediction = model(
                _x, _s_1, _s_2
            )
            for i in range(SAMPLES):
                feats_train = pd.concat(
                    [feats_train, pd.DataFrame(_x.cpu().numpy(), columns=_train.x.columns)],
                    axis='rows',
                    ignore_index=True,
                )
                feats_encs = pd.concat(
                    [
                        feats_encs,
                        pd.DataFrame(feat_enc.sample().cpu().numpy(), columns=list(range(FEAT_LD))),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                direct_preds_train = pd.concat(
                    [
                        direct_preds_train,
                        pd.DataFrame(
                            direct_prediction.probs.cpu().numpy(), columns=_train.y.columns
                        ),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                preds_train = pd.concat(
                    [preds_train, pd.DataFrame(_y.cpu().numpy(), columns=_train.y.columns)],
                    axis='rows',
                    ignore_index=True,
                )
                s_1_list = pd.concat(
                    [
                        s_1_list,
                        pd.DataFrame(_s_1.cpu().numpy(), columns=_train.s.columns, dtype=np.int64),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                s_2_list = pd.concat(
                    [
                        s_2_list,
                        pd.DataFrame(_s_2.cpu().numpy(), columns=_train.s.columns, dtype=np.int64),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                actual_labels = pd.concat(
                    [
                        actual_labels,
                        pd.DataFrame(_y.cpu().numpy(), columns=_train.y.columns, dtype=np.int64),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                preds_encs = pd.concat(
                    [
                        preds_encs,
                        pd.DataFrame(pred_enc.sample().cpu().numpy(), columns=_train.y.columns),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                actual_feats = pd.concat(
                    [actual_feats, pd.DataFrame(_x.cpu().numpy(), columns=_train.x.columns)],
                    axis='rows',
                    ignore_index=True,
                )

            ###
            # flippedx, og y
            ###
            _s_1 = (_s.detach().clone() - 1) ** 2
            _s_2 = _s.detach().clone()
            feat_enc, feat_dec, feat_s_pred, pred_enc, pred_dec, pred_s_pred, direct_prediction = model(
                _x, _s_1, _s_2
            )
            for i in range(SAMPLES):
                feats_train = pd.concat(
                    [
                        feats_train,
                        pd.DataFrame(
                            torch.cat([feat.sample() for feat in feat_dec], 1).cpu().numpy(),
                            columns=_train.x.columns,
                        ),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                # feats_train += torch.cat([feat.sample() for feat in feat_dec], 1).data.tolist()
                direct_preds_train = pd.concat(
                    [
                        direct_preds_train,
                        pd.DataFrame(
                            direct_prediction.probs.cpu().numpy(), columns=_train.y.columns
                        ),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                preds_train = pd.concat(
                    [preds_train, pd.DataFrame(_y.cpu().numpy(), columns=_train.y.columns)],
                    axis='rows',
                    ignore_index=True,
                )
                s_1_list = pd.concat(
                    [
                        s_1_list,
                        pd.DataFrame(_s_1.cpu().numpy(), columns=_train.s.columns, dtype=np.int64),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                s_2_list = pd.concat(
                    [
                        s_2_list,
                        pd.DataFrame(_s_2.cpu().numpy(), columns=_train.s.columns, dtype=np.int64),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                actual_labels = pd.concat(
                    [
                        actual_labels,
                        pd.DataFrame(_y.cpu().numpy(), columns=_train.y.columns, dtype=np.int64),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                actual_feats = pd.concat(
                    [actual_feats, pd.DataFrame(_x.cpu().numpy(), columns=_train.x.columns)],
                    axis='rows',
                    ignore_index=True,
                )

            ###
            # flipped x, flipped y
            ###
            _s_1 = (_s.detach().clone() - 1) ** 2
            _s_2 = (_s.detach().clone() - 1) ** 2
            feat_enc, feat_dec, feat_s_pred, pred_enc, pred_dec, pred_s_pred, direct_prediction = model(
                torch.cat([feat.sample() for feat in feat_dec], 1), _s_1, _s_2
            )
            for i in range(SAMPLES):
                feats_train = pd.concat(
                    [
                        feats_train,
                        pd.DataFrame(
                            torch.cat([feat.sample() for feat in feat_dec], 1).cpu().numpy(),
                            columns=_train.x.columns,
                        ),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                direct_preds_train = pd.concat(
                    [
                        direct_preds_train,
                        pd.DataFrame(
                            direct_prediction.probs.cpu().numpy(), columns=_train.y.columns
                        ),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                preds_train = pd.concat(
                    [
                        preds_train,
                        pd.DataFrame(pred_dec.probs.cpu().numpy(), columns=_train.y.columns),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                s_1_list = pd.concat(
                    [
                        s_1_list,
                        pd.DataFrame(_s_1.cpu().numpy(), columns=_train.s.columns, dtype=np.int64),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                s_2_list = pd.concat(
                    [
                        s_2_list,
                        pd.DataFrame(_s_2.cpu().numpy(), columns=_train.s.columns, dtype=np.int64),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                actual_labels = pd.concat(
                    [
                        actual_labels,
                        pd.DataFrame(_y.cpu().numpy(), columns=_train.y.columns, dtype=np.int64),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                actual_feats = pd.concat(
                    [actual_feats, pd.DataFrame(_x.cpu().numpy(), columns=_train.x.columns)],
                    axis='rows',
                    ignore_index=True,
                )

            ###
            # og x, flipped y
            ###
            _s_1 = _s.detach().clone()
            _s_2 = (_s.detach().clone() - 1) ** 2
            feat_enc, feat_dec, feat_s_pred, pred_enc, pred_dec, pred_s_pred, direct_prediction = model(
                _x, _s_1, _s_2
            )
            for i in range(SAMPLES):
                feats_train = pd.concat(
                    [feats_train, pd.DataFrame(_x.cpu().numpy(), columns=_train.x.columns)],
                    axis='rows',
                    ignore_index=True,
                )
                direct_preds_train = pd.concat(
                    [
                        direct_preds_train,
                        pd.DataFrame(
                            direct_prediction.probs.cpu().numpy(), columns=_train.y.columns
                        ),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                preds_train = pd.concat(
                    [
                        preds_train,
                        pd.DataFrame(pred_dec.probs.cpu().numpy(), columns=_train.y.columns),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                s_1_list = pd.concat(
                    [
                        s_1_list,
                        pd.DataFrame(_s_1.cpu().numpy(), columns=_train.s.columns, dtype=np.int64),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                s_2_list = pd.concat(
                    [
                        s_2_list,
                        pd.DataFrame(_s_2.cpu().numpy(), columns=_train.s.columns, dtype=np.int64),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                actual_labels = pd.concat(
                    [
                        actual_labels,
                        pd.DataFrame(_y.cpu().numpy(), columns=_train.y.columns, dtype=np.int64),
                    ],
                    axis='rows',
                    ignore_index=True,
                )
                actual_feats = pd.concat(
                    [actual_feats, pd.DataFrame(_x.cpu().numpy(), columns=_train.x.columns)],
                    axis='rows',
                    ignore_index=True,
                )

    feats = feats_train
    direct_labels = direct_preds_train
    direct_labels = direct_labels.applymap(lambda x: 1 if x >= 0.5 else 0)
    s_1_total = s_1_list
    s_2_total = s_2_list
    actual_labels = actual_labels

    labels = preds_train
    labels = labels.applymap(lambda x: 1 if x >= 0.5 else 0)

    # print(
    #     f"there are {train.y.count()} labels in the original training set and {labels.count()} in the augmented set"
    # )

    s_col = _train.s.columns[0]
    y_col = _train.y.columns[0]

    # print(
    #     labels[(s_1_total[s_col] == 0) & (labels[y_col] == 0)].count(),
    #     actual_labels[(s_1_total[s_col] == 0) & (actual_labels[y_col] == 0)].count(),
    # )
    # print(
    #     labels[(s_1_total[s_col] == 0) & (labels[y_col] == 1)].count(),
    #     actual_labels[(s_1_total[s_col] == 0) & (actual_labels[y_col] == 1)].count(),
    # )
    # print(
    #     labels[(s_1_total[s_col] == 1) & (labels[y_col] == 0)].count(),
    #     actual_labels[(s_1_total[s_col] == 1) & (actual_labels[y_col] == 0)].count(),
    # )
    # print(
    #     labels[(s_1_total[s_col] == 1) & (labels[y_col] == 1)].count(),
    #     actual_labels[(s_1_total[s_col] == 1) & (actual_labels[y_col] == 1)].count(),
    # )
    to_return = DataTuple(x=feats, s=s_1_total, y=labels, name=f"Imagined: {train.name}")

    # print(
    #     direct_labels[(s_1_total[s_col] == 0) & (direct_labels[y_col] == 0)].count(),
    #     actual_labels[(s_1_total[s_col] == 0) & (actual_labels[y_col] == 0)].count(),
    # )
    # print(
    #     direct_labels[(s_1_total[s_col] == 0) & (direct_labels[y_col] == 1)].count(),
    #     actual_labels[(s_1_total[s_col] == 0) & (actual_labels[y_col] == 1)].count(),
    # )
    # print(
    #     direct_labels[(s_1_total[s_col] == 1) & (direct_labels[y_col] == 0)].count(),
    #     actual_labels[(s_1_total[s_col] == 1) & (actual_labels[y_col] == 0)].count(),
    # )
    # print(
    #     direct_labels[(s_1_total[s_col] == 1) & (direct_labels[y_col] == 1)].count(),
    #     actual_labels[(s_1_total[s_col] == 1) & (actual_labels[y_col] == 1)].count(),
    # )
    to_observe = DataTuple(x=feats, s=s_1_total, y=direct_labels, name=f"Imagined: {train.name}")

    from ethicml.visualisation.plot import save_label_plot

    save_label_plot(to_return, './labels_preds.png')
    save_label_plot(to_observe, './labels_direct.png')
    save_label_plot(_train, './labels_og.png')

    if post_process:
        to_return = processor.post(to_return)
        to_observe = processor.post(to_observe)

    return (to_return, TestTuple(x=test.x, s=test.s, name=f"Imagined: {test.name}"))


class GradReverse(Function):
    @staticmethod
    def forward(ctx, x):
        return x.view_as(x)

    @staticmethod
    def backward(ctx, grad_output):
        return grad_output.neg()


def grad_reverse(features):
    return GradReverse.apply(features)


class FeatureEncoder(nn.Module):
    def __init__(self, in_size: int):
        super().__init__()
        self.hid_1 = nn.Linear(in_size, 100)
        self.bn_1 = nn.BatchNorm1d(100)
        self.hid_2 = nn.Linear(100, 100)
        self.bn_2 = nn.BatchNorm1d(100)
        self.hid_3 = nn.Linear(100, 100)
        self.bn_3 = nn.BatchNorm1d(100)

        self.mu = nn.Linear(100, FEAT_LD)
        self.logvar = nn.Linear(100, FEAT_LD)

    def forward(self, x: torch.Tensor):
        x = self.bn_1(torch.relu(self.hid_1(x)))
        x = self.bn_2(torch.relu(self.hid_2(x)))
        x = self.bn_3(torch.relu(self.hid_3(x)))
        return td.Normal(loc=self.mu(x), scale=torch.exp(self.logvar(x)))


class FeatureDecoder(nn.Module):
    def __init__(self, out_groups):
        super().__init__()
        self.hid_1 = nn.Linear(FEAT_LD + 1, 100)
        self.bn_1 = nn.BatchNorm1d(100)
        self.hid_2 = nn.Linear(100, 100)
        self.bn_2 = nn.BatchNorm1d(100)
        self.hid_3 = nn.Linear(100, 100)
        self.bn_3 = nn.BatchNorm1d(100)

        self.out = nn.ModuleList([nn.Linear(100, len(out)) for out in out_groups])

    def forward(self, z: td.Distribution, s: torch.Tensor):
        x = self.bn_1(torch.relu(self.hid_1(torch.cat([z.mean, s], dim=1))))
        x = self.bn_2(torch.relu(self.hid_2(x)))
        x = self.bn_3(torch.relu(self.hid_3(x)))
        return [td.OneHotCategorical(logits=f(x)) for f in self.out]


class FeatureAdv(nn.Module):
    def __init__(self):
        super().__init__()
        self.hid = nn.Linear(FEAT_LD, 100)
        self.hid_1 = nn.Linear(100, 100)
        self.bn_1 = nn.BatchNorm1d(100)
        self.hid_2 = nn.Linear(100, 100)
        self.bn_2 = nn.BatchNorm1d(100)
        self.out = nn.Linear(100, 1)

    def forward(self, z: td.Distribution):
        z = torch.relu(self.hid(grad_reverse(z.mean)))
        z = self.bn_1(torch.relu(self.hid_1(z)))
        z = self.bn_2(torch.relu(self.hid_2(z)))
        z = self.out(z)
        return td.Bernoulli(z)


class PredictionEncoder(nn.Module):
    def __init__(self, in_size: int):
        super().__init__()
        self.hid_1 = nn.Linear(in_size, 100)
        self.bn_1 = nn.BatchNorm1d(100)
        self.hid_2 = nn.Linear(100, 100)
        self.bn_2 = nn.BatchNorm1d(100)
        self.hid_3 = nn.Linear(100, 100)
        self.bn_3 = nn.BatchNorm1d(100)
        self.mu = nn.Linear(100, _PRED_LD)

    def forward(self, x: torch.Tensor):
        x = self.bn_1(torch.relu(self.hid_1(x)))
        x = self.bn_2(torch.relu(self.hid_2(x)))
        x = self.bn_3(torch.relu(self.hid_3(x)))
        return td.Bernoulli(probs=torch.sigmoid(self.mu(x)))


class PredictionDecoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.hid_1 = nn.Linear(_PRED_LD + 1, 100)
        self.bn_1 = nn.BatchNorm1d(100)
        self.hid_2 = nn.Linear(100, 100)
        self.bn_2 = nn.BatchNorm1d(100)
        self.hid_3 = nn.Linear(100, 100)
        self.bn_3 = nn.BatchNorm1d(100)
        self.out = nn.Linear(100, 1)

    def forward(self, z: td.Distribution, s: torch.Tensor):
        x = self.bn_1(self.hid_1(torch.cat([z.probs, s], dim=1)))
        x = self.bn_2(self.hid_2(x))
        x = self.bn_3(self.hid_3(x))
        mean = z.probs + self.out(x)
        return td.Bernoulli(torch.sigmoid(mean))


class DirectPredictor(nn.Module):
    def __init__(self, in_size: int):
        super().__init__()
        self.hid = nn.Linear(in_size + 1, 100)
        self.hid_1 = nn.Linear(100, 100)
        self.bn_1 = nn.BatchNorm1d(100)
        self.hid_2 = nn.Linear(100, 100)
        self.bn_2 = nn.BatchNorm1d(100)
        self.out = nn.Linear(100, 1)

    def forward(self, x: torch.Tensor, s: torch.Tensor):
        mean = torch.relu(self.hid(torch.cat([x, s], dim=1)))
        mean = self.bn_1(torch.relu(self.hid_1(mean)))
        mean = self.bn_2(torch.relu(self.hid_2(mean)))
        mean = self.out(mean)
        return td.Bernoulli(probs=torch.sigmoid(torch.tanh(mean)))


class PredictionAdv(nn.Module):
    def __init__(self):
        super().__init__()
        self.hid = nn.Linear(_PRED_LD, 100)
        self.hid_1 = nn.Linear(100, 100)
        self.bn_1 = nn.BatchNorm1d(100)
        self.hid_2 = nn.Linear(100, 100)
        self.bn_2 = nn.BatchNorm1d(100)
        self.out = nn.Linear(100, 1)

    def forward(self, z: td.Distribution):
        z = torch.relu(self.hid(grad_reverse(z.probs)))
        z = self.bn_1(torch.relu(self.hid_1(z)))
        z = self.bn_2(torch.relu(self.hid_2(z)))
        z = self.out(z)
        return td.Bernoulli(z)


class Imagine(nn.Module):
    def __init__(self, data: CustomDataset, dataset: Dataset):
        super().__init__()
        self.feature_encoder = FeatureEncoder(in_size=data.size)
        self.feature_decoder = FeatureDecoder(data.groups)
        self.feature_adv = FeatureAdv()

        self.prediction_encoder = PredictionEncoder(in_size=data.size)
        self.prediction_decoder = PredictionDecoder()
        self.direct_pred = DirectPredictor(in_size=data.size)
        self.prediction_adv = PredictionAdv()

    def forward(self, x, s_1, s_2):

        feat_enc: td.Distribution = self.feature_encoder(x)
        feat_dec = self.feature_decoder(feat_enc, s_1)

        pred_enc: td.Distribution = self.prediction_encoder(x)
        pred_dec: td.Distribution = self.prediction_decoder(pred_enc, s_2)

        feat_s_pred = self.feature_adv(feat_enc)
        pred_s_pred = self.prediction_adv(pred_enc)

        direct_prediction: td.Distribution = self.direct_pred(x, s_1)

        return feat_enc, feat_dec, feat_s_pred, pred_enc, pred_dec, pred_s_pred, direct_prediction


def save_checkpoint(checkpoint, filename, is_best, save_path):
    print("===> Saving checkpoint '{}'".format(filename))
    model_filename = save_path / filename
    best_filename = save_path / 'model_best.pth.tar'
    if not os.path.exists(save_path):
        os.mkdir(save_path)
    torch.save(checkpoint, model_filename)
    if is_best:
        shutil.copyfile(model_filename, best_filename)
    print("===> Saved checkpoint '{}'".format(model_filename))


BEST_LOSS = np.inf


def train_model(epoch, model, train_loader, valid_loader, optimizer, device, prob_pos, flags):
    """
    Train the model
    Args:
        epoch:
        model:
        train_loader:
        optimizer:
        flags:

    Returns:

    """

    model.train()
    train_loss = 0
    for batch_idx, (data_x, data_s, data_y, out_groups) in enumerate(train_loader):
        data_x = data_x.to(device)
        data_s_1 = data_s.to(device)
        data_s_2 = data_s.to(device)
        data_y = data_y.to(device)
        out_groups = [out.to(device) for out in out_groups]

        optimizer.zero_grad()
        feat_enc: td.Distribution
        feat_dec: torch.Tensor
        feat_s_pred: td.Distribution
        pred_enc: td.Distribution
        pred_dec: td.Distribution
        pred_s_pred: td.Distribution
        direct_prediction: td.Distribution
        feat_enc, feat_dec, feat_s_pred, pred_enc, pred_dec, pred_s_pred, direct_prediction = model(
            data_x, data_s_1, data_s_2
        )

        ### Features
        recon_loss = (sum([-ohe.log_prob(real) for ohe, real in zip(feat_dec, out_groups)])).mean()

        feat_prior = td.Normal(
            loc=torch.zeros(FEAT_LD).to(device), scale=torch.ones(FEAT_LD).to(device)
        )
        feat_kl_loss = td.kl.kl_divergence(feat_prior, feat_enc)

        feat_sens_loss = -feat_s_pred.log_prob(data_s_1)
        ###

        ### Predictions
        pred_loss_1 = -direct_prediction.log_prob(data_y)
        pred_loss_2 = -pred_dec.log_prob(data_y)
        pred_loss = (pred_loss_1 + pred_loss_2).mean()

        pred_prior = td.Bernoulli((data_x.new_ones(pred_enc.probs.shape) * (prob_pos)))
        pred_kl_loss = td.kl.kl_divergence(pred_prior, pred_enc)

        pred_sens_loss = -pred_s_pred.log_prob(data_s_1)
        ###

        ### Direct Pred
        direct_loss = td.kl.kl_divergence(direct_prediction, pred_dec)
        ###

        kl_loss = feat_kl_loss.mean() + (pred_kl_loss + direct_loss).mean()
        sens_loss = (feat_sens_loss + pred_sens_loss).mean()

        loss = recon_loss + kl_loss + sens_loss + pred_loss
        loss.backward()

        train_loss += loss.item()
        optimizer.step()
        if batch_idx % 100 == 0:
            print(
                f'train Epoch: {epoch} [{batch_idx * len(data_x)}/{len(train_loader.dataset)}'
                f'({100. * batch_idx / len(train_loader):.0f}%)]\t'
                f'Loss: {loss.item() / len(data_x):.6f}\t'
                f'recon_loss: {recon_loss.sum().item():.6f}\t'
                f'pred_loss_xs: {pred_loss_1.sum().item():.6f}\t'
                f'pred_loss_ybs: {pred_loss_2.sum().item():.6f}\t'
                f'kld_loss feats: {feat_kl_loss.sum().item():.6f}\t'
                f'kld_loss prior: {pred_kl_loss.sum().item():.6f}\t'
                f'kld_loss outps: {direct_loss.sum().item():.6f}\t'
                f'adv_feat_loss: {feat_sens_loss.sum().item():.6f}\t'
                f'adv_pred_loss: {pred_sens_loss.sum().item():.6f}\t'
            )

    print(f'====> Epoch: {epoch} Average loss: {train_loss / len(train_loader.dataset):.4f}')

    model.eval()

    valid_loss = 0
    with torch.no_grad():
        for data_x, data_s, data_y, out_groups in valid_loader:
            data_x = data_x.to(device)
            data_s_1 = data_s.to(device)
            data_s_2 = data_s.to(device)
            data_y = data_y.to(device)
            out_groups = [out.to(device) for out in out_groups]

            feat_enc, feat_dec, feat_s_pred, pred_enc, pred_dec, pred_s_pred, direct_prediction = model(
                data_x, data_s_1, data_s_2
            )

            ### Features
            recon_loss = (
                sum([-ohe.log_prob(real) for ohe, real in zip(feat_dec, out_groups)])
            ).mean()  # F.mse_loss(data_x, feat_dec, reduction='mean')

            feat_prior = td.Normal(
                loc=torch.zeros(FEAT_LD).to(device), scale=torch.ones(FEAT_LD).to(device)
            )
            feat_kl_loss = td.kl.kl_divergence(feat_prior, feat_enc)

            feat_sens_loss = -feat_s_pred.log_prob(data_s_1)
            ###

            ### Predictions
            pred_loss_1 = -direct_prediction.log_prob(data_y)
            pred_loss_2 = -pred_dec.log_prob(data_y)
            pred_loss = (pred_loss_1 + pred_loss_2).mean()

            pred_prior = td.Bernoulli((data_x.new_ones(pred_enc.probs.shape) * prob_pos))
            pred_kl_loss = td.kl.kl_divergence(pred_prior, pred_enc)

            pred_sens_loss = -pred_s_pred.log_prob(data_s_1)
            ###

            ### Direct Pred
            direct_loss = td.kl.kl_divergence(direct_prediction, pred_dec)
            ###

            kl_loss = feat_kl_loss.mean() + (pred_kl_loss + direct_loss).mean()
            sens_loss = (feat_sens_loss + pred_sens_loss).mean()

            valid_loss += recon_loss + kl_loss + pred_loss - sens_loss

    is_best = valid_loss < BEST_LOSS
    best_loss = min(valid_loss, BEST_LOSS)

    # Save checkpoint
    save_path = Path(".") / "checkpoint"
    model_filename = 'checkpoint_%03d.pth.tar' % epoch
    checkpoint = {
        'epoch': epoch,
        'model': model.state_dict(),
        'optimizer': optimizer.state_dict(),
        'best_loss': best_loss,
    }
    save_checkpoint(checkpoint, model_filename, is_best, save_path)


def main():
    """Load data from feather files, pass it to `train_and_transform` and then save the result"""
    parser = pre_algo_argparser()

    # model parameters
    parser.add_argument("--dataset", type=str, required=True)
    parser.add_argument("--enc_size", type=int, nargs="+", required=True)
    parser.add_argument("--adv_size", type=int, nargs="+", required=True)
    parser.add_argument("--pred_size", type=int, nargs="+", required=True)
    parser.add_argument("--batch_size", type=int, required=True)
    parser.add_argument("--epochs", type=int, required=True)
    parser.add_argument("--adv_weight", type=float, required=True)
    parser.add_argument("--validation_pcnt", type=float, required=True)
    parser.add_argument("--sample", type=int, required=True)
    parser.add_argument("--start_from", type=int, required=True)
    args = parser.parse_args()
    # convert args object to a dictionary and load the feather files from the paths
    train, test = load_data_from_flags(vars(args))

    # make the argparse object type-safe (is there an easier way to do this?)
    flags = ImagineSettings(
        enc_size=args.enc_size,
        adv_size=args.adv_size,
        pred_size=args.pred_size,
        batch_size=args.batch_size,
        epochs=args.epochs,
        adv_weight=args.adv_weight,
        validation_pcnt=args.validation_pcnt,
        sample=args.sample,
        start_from=args.start_from,
    )
    save_transformations(train_and_transform(train, test, flags), args)


if __name__ == "__main__":
    main()
