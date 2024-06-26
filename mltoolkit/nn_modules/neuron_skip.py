"""
Multlayer Perceptron with Neuron Skipping 
"""
import torch
import math
from torch import nn, Tensor
from torch.distributions import Bernoulli

class LinearNeuronSkip(nn.Module):

    def __init__(self, d_model: int):
        super().__init__()

        """
        self.w_skip = nn.Linear(d_model, d_model)
        self.w      = nn.Linear(d_model, d_model)
        """
        self.affine = nn.Linear(d_model, 2*d_model)

    # TODO this doesn't backprop. thinking about using RNN with RL for training
    def forward(self, X: Tensor) -> Tensor:
        """
        Arguments:
            X[Tensor]: input data of shape (-1, d_model)
        """
        """
        f_skip = self.w_skip(X)
        f_out = self.w(X)

        skip_mask = Bernoulli(logits=f_skip).sample().bool()

        out = X*skip_mask + f_out*~skip_mask 
        """
        out1, out2 = self.affine(X).chunk(2, dim=-1)
        out2 = torch.sigmoid(out2)

        out = out1*out2+X*(1-out2)

        return out

