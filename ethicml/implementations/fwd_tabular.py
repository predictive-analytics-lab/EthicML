from pathlib import Path
from typing import List

import pandas as pd
import torch
from torch import optim
from torch.optim.optimizer import Optimizer
from torch.utils.data import DataLoader

from ethicml.implementations.beutel import set_seed
from ethicml.implementations.fwd_modules.fwd_classifier import FWDClassifier
from ethicml.implementations.pytorch_common import CustomDataset, TestDataset
from ethicml.implementations.utils import InAlgoArgs, load_data_from_flags
from ethicml.utility import (
    DataTuple,
    Prediction,
    SoftPrediction,
    TestTuple,
    get_dataset_obj_by_name,
)


class FwdArgs(InAlgoArgs):
    batch_size: int
    epochs: int
    eta: float
    network_size: List[int]


def train_model(
    epoch: int, model: FWDClassifier, train_loader: DataLoader, optimizer: Optimizer, args: FwdArgs
):
    model.train()
    train_loss = 0.0
    for batch_idx, (data_x, data_s, data_y) in enumerate(train_loader):
        data_x = data_x.to("cpu")
        data_s = data_s.to("cpu")
        data_y = data_y.to("cpu")
        optimizer.zero_grad()
        y_prob = model.forward(data_x)
        loss = model.loss(y_prob, data_y)
        loss.backward()
        optimizer.step()
        train_loss += loss.item()
        if batch_idx % 100 == 0:
            print(
                f"train Epoch: {epoch} [{batch_idx * len(data_x)}/{len(train_loader.dataset)}"
                f"\t({100. * batch_idx / len(train_loader):.0f}%)]"
                f"\tLoss: {loss.item() / len(data_x):.6f}"
            )

    print(f"====> Epoch: {epoch} Average loss: {train_loss / len(train_loader.dataset):.4f}")


def train_and_predict(train: DataTuple, test: TestTuple, args: FwdArgs) -> SoftPrediction:

    # Set up the data
    train_data = CustomDataset(train)
    train_loader = DataLoader(train_data, batch_size=args.batch_size)

    test_data = TestDataset(test)
    test_loader = DataLoader(test_data, batch_size=args.batch_size)

    # Build Network
    model = FWDClassifier(
        in_size=train_data.xdim,
        out_size=train_data.ydim,
        network_size=args.network_size,
        eta=args.eta,
    ).to("cpu")
    optimizer = optim.Adam(model.parameters(), lr=1e-3)

    # Run Network
    for epoch in range(int(args.epochs)):
        train_model(epoch, model, train_loader, optimizer, args)

    # Transform output
    post_test: List[List[float]] = []
    model.eval()
    with torch.no_grad():
        for _x, _s in test_loader:
            out = model.forward(_x)
            post_test += out.data.tolist()

    return SoftPrediction(soft=pd.Series([j for i in post_test for j in i]))


def main():
    """This function runs the SVM model as a standalone program."""
    set_seed(888)
    args = FwdArgs().parse_args()
    train, test = load_data_from_flags(args)
    train_and_predict(train, test, args).to_npz(Path(args.predictions))


if __name__ == "__main__":
    main()
