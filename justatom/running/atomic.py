import torch
import torch.nn as nn

from justatom.modeling.mask import ILanguageModel
from justatom.running.mask import IMODELRunner


class ATOMICLMRunner(IMODELRunner, torch.nn.Module):
    """
    A Transformer Orchestration Model Involving Classification module to dissect queries for better Information Retrieval.
    """  # noqa: E501

    def __init__(
        self,
        query_model: ILanguageModel,
        ic_model: nn.Module,
        passage_model: ILanguageModel | None = None,
    ):  # noqa: E501
        self.query_model = query_model
        self.ic_model = ic_model
        self.passage_model = passage_model

    def forward_lm(self):
        pass
