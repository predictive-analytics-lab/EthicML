"""Functions that are common to PyTorch models"""
import numpy as np
import torch
from torch.utils.data import Dataset

from ethicml.utility.data_structures import DataTuple, TestTuple
from itertools import groupby


class TestDataset(Dataset):
    """Shared Dataset for pytorch models without labels"""

    def __init__(self, data: TestTuple):
        self.features = np.array(data.x.values, dtype=np.float32)
        self.sens_labels = np.array(data.s.values, dtype=np.float32)
        self.num = data.s.shape[0]
        self.s_size = data.s.shape[1]
        self.size = data.x.shape[1]
        self.x_names = data.x.columns
        self.s_names = data.s.columns
        self.column_lookup = {col: i for i, col in enumerate(self.x_names)}
        self.groups = [list(group) for key, group in groupby(self.x_names, lambda x: x.split('_')[0])]
        self.group_columns = [[self.column_lookup[g] for g in group] for group in self.groups]
        print('kkk')

    def __getitem__(self, index):
        return self.features[index], self.sens_labels[index]

    def __len__(self):
        return self.num

    def names(self):
        return self.x_names, self.s_names


class CustomDataset(TestDataset):
    """Shared Dataset for pytorch models"""

    def __init__(self, data: DataTuple):
        super().__init__(data.remove_y())
        self.class_labels = np.array(data.y.values, dtype=np.float32)
        self.y_size = data.y.shape[1]
        self.y_names = data.y.columns

    def __getitem__(self, index):
        return self.features[index], self.sens_labels[index], self.class_labels[index]#, [self.features[:, group][index] for group in self.group_columns]

    def names(self):
        return self.x_names, self.s_names, self.y_names


def quadratic_time_mmd(data_first, data_second, sigma):
    """

    Args:
        data_first:
        data_second:
        sigma:

    Returns:

    """
    xx_gm = data_first @ data_first.t()
    xy_gm = data_first @ data_second.t()
    yy_gm = data_second @ data_second.t()
    x_sqnorms = torch.diagonal(xx_gm)
    y_sqnorms = torch.diagonal(yy_gm)

    pad_first = lambda x: torch.unsqueeze(x, 0)
    pad_second = lambda x: torch.unsqueeze(x, 1)

    gamma = 1 / (2 * sigma ** 2)
    # use the second binomial formula
    kernel_xx = torch.exp(-gamma * (-2 * xx_gm + pad_second(x_sqnorms) + pad_first(x_sqnorms)))
    kernel_xy = torch.exp(-gamma * (-2 * xy_gm + pad_second(x_sqnorms) + pad_first(y_sqnorms)))
    kernel_yy = torch.exp(-gamma * (-2 * yy_gm + pad_second(y_sqnorms) + pad_first(y_sqnorms)))

    xx_num = float(kernel_xx.shape[0])
    yy_num = float(kernel_yy.shape[0])

    mmd2 = (
        kernel_xx.sum() / (xx_num * xx_num)
        + kernel_yy.sum() / (yy_num * yy_num)
        - 2 * kernel_xy.sum() / (xx_num * yy_num)
    )
    return mmd2
