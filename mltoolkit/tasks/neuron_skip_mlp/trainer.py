"""
this is an example trainer class that inherits TrainerBase
"""
# external imports
import torch
import numpy as np
import datasets
from tqdm import tqdm
from torch import nn
from datasets import Dataset
from torch.utils.data import DataLoader

# for typing
from torch.optim.optimizer import Optimizer
from torch.optim.lr_scheduler import LRScheduler
from typing import Tuple, List, Dict, TypeVar
T = TypeVar('T')

# local imports
from mltoolkit.templates import Trainer
from mltoolkit.utils import (
    files,
    strings,
    display,
)
from mltoolkit.nn_modules import LinearNeuronSkip

class TrainerNeuronSkipMLP(Trainer):
    def __init__(self, config_path, debug=False , accelerator=None):
        super().__init__(
            config_path,
            debug,
            accelerator=accelerator
        )

    def setup(self):
        cfg = self.cfg

        # define model
        model = torch.nn.Sequential(
            torch.nn.Flatten(),
            nn.Linear(
                cfg.params['in_size'],
                cfg.params['hidden_dim'],
            ),
            LinearNeuronSkip(cfg.params['hidden_dim']),
            torch.nn.ReLU(),
            torch.nn.Linear(
                cfg.params['hidden_dim'],
                cfg.params['num_classes'],
            ),
        )

        # load mnist dataset
        ds = datasets.load_dataset(
            'mnist',
            cache_dir=cfg.paths['cache']
        ).with_format('torch')
        in_size = cfg.params['hidden_dim']

        # preprocess
        def normalize(batch):
            batch.update({
                'image' : batch['image'].to(torch.float32)/255.
            })
            return batch

        ds = ds.map(
            normalize,
            batched=True,
            batch_size=1000,
            num_proc=cfg.params['num_proc'],
        )

        train_loader = DataLoader(
            ds['train'],
            shuffle=cfg.params['shuffle'],
            batch_size=cfg.params['batch_size'],
        )

        val_loader = DataLoader(
            ds['test'],
            shuffle=cfg.params['shuffle'],
            batch_size=cfg.params['batch_size'],
        )

        # optimizer
        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=self.cfg.params['lr'],
            weight_decay=self.cfg.params['weight_decay']
        )

        # scheduler
        scheduler = torch.optim.lr_scheduler.StepLR(
            optimizer,
            cfg.params['sched_step_size'],
            gamma=cfg.params['sched_gamma'],
        )

        self.loss_fn = nn.CrossEntropyLoss()

        return {
            'model': model,
            'train_loader': train_loader,
            'val_loader': val_loader,
            'optimizer': optimizer,
            'scheduler': scheduler
        }

    def step(self, batch: T, mode='train'):

        # compute scores and calculate loss
        scores = self.train_vars['model'](batch['image'])
        labels = batch['label']
        loss = self.loss_fn(scores, labels)
        accuracy = torch.sum(torch.argmax(scores, dim=-1) == labels)/len(labels)

        return loss, accuracy

    def train_step(self, batch: T) -> Tuple[torch.Tensor, Dict]:
        """
        This function is used to compute the loss and training statistics

        Input
            model[nn.Module]: this is the model you previously assigned.
            batch[T]: a batch sampled from the previously assigned train dataloader

        Return
            loss[torch.Tensor]: the computed loss
            metrics[Dict]: the metrics you would like to track.
                refer to {project_root}/mltoolkit/trainers/base.py for the currently supported keyword trackers
        """

        loss, accuracy = self.step(batch, mode='train')

        return loss, {
            'scalar' : {
                'loss' : loss,
                'accuracy' : accuracy
            }
        }

    def eval_step(self, batch: T, loader_name):
        """
        same as train_step but batch comes from previously assigned val_loader (test_loader evaluation not implemented yet)
        NOTE: in this function, torch.Tensor values need to be converted to float/int 

        Input
            batch[T]: a batch sampled from the previously assigned train dataloader
            mode[str]: string that will be either 'val' or 'train' depending on the procedure. 

        Return
            metrics[Dict]: the metrics you would like to track. Each run of eval_step() will 
                accumulate these metrics into a Dataset object and will be used as input 
                to on_eval_end() for final aggregation
        """
        loss, accuracy = self.step(batch, mode='val')

        return {
            'loss': float(loss),
            'accuracy': float(accuracy),
        }

    def on_eval_end(self, metrics: List, mode: str):
        """
        use this to aggregate your metrics collected from the outputs of eval_step()

        Input:
            metrics[Dict[str, list]]: the set of metrics collected from eval_step()

        Return
            target_metric[T]: the metric that will be used to determine if the current model should be 
                checkpointed to {cfg.params['results']}/best_model.pt.
            log_values[Dict[Dict[str, T]]]: 
        """

        metrics_ds = Dataset.from_list(metrics['val_loader'])
        loss = np.mean(metrics_ds['loss'])
        accuracy = np.mean(metrics_ds['accuracy'])

        return accuracy, {
            'scalar' : {
                'loss' : loss,
                'accuracy' : accuracy
            }
        }

    def save_criterion(self, new_score, prev_best):
        return new_score > prev_best
