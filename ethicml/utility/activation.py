"""
Activations are applied to
"""

from abc import ABC, abstractmethod
import numpy


class Activation(ABC):
    """Base class for decision functions"""
    @abstractmethod
    def apply(self, soft_output: numpy.array) -> numpy.array:
        """Apply the decision function to a soft prediction

        Args:
            soft_output: soft prediction (i.e. a probability or logits)

        Returns:
            decision
        """

    @abstractmethod
    def get_name(self) -> str:
        """Name of activation function"""