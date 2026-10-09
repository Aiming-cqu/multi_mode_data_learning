#!/usr/bin/env -S pixi run -e vllm -- test

from __future__ import absolute_import, annotations

import abc, typing as tp

from functools import partial
from typing_extensions import override

## numpy backend ##

if 0:
    import numpy

    xt = numpy
    tensor = xt.array

    if tp.TYPE_CHECKING:
        from numpy.typing import NDArray as Tensor

    norm: tp.Callable[[Tensor], Tensor] = partial(numpy.linalg.norm, axis=-1, keepdims=True)
    normalize: tp.Callable[[Tensor], Tensor] = lambda x_xc: x_xc / norm(x_xc)

## torch backend ##

if 1:
    import torch
    import torch.nn.functional as F

    xt = torch
    tensor = xt.tensor

    if tp.TYPE_CHECKING:
        from torch import Tensor

    norm: tp.Callable[[Tensor], Tensor] = partial(torch.norm, p=2, dim=-1, keepdim=True)
    normalize: tp.Callable[[Tensor], Tensor] = partial(F.normalize, p=2, dim=-1)


class EmbeddingSimilarityBase(abc.ABC):
    r"""
    Abstract base class for embedding similarity metrics.

    Provides a registry pattern for similarity metric implementations
    and defines the interface for computing similarity between embeddings.

    Attributes:
        Registry: Class-level dictionary mapping metric names to classes.
    """
    Registry: tp.ClassVar[dict[str, type[EmbeddingSimilarityBase]]] = dict()

    def __init_subclass__(cls, *, registry_name: str = '', **kwds) -> None:
        r"""
        Register subclasses in the Registry.

        Automatically registers any subclass with the specified registry_name
        or the class name if not provided.

        Args:
            registry_name: Name to use for registration. Defaults to class name.
            **kwds: Additional keyword arguments passed to `super().__init_subclass__`.
        """
        super().__init_subclass__(**kwds)
        cls.Registry[registry_name or cls.__name__] = cls

    @abc.abstractmethod
    def compute(self, x_xc: 'Tensor', y_xc: 'Tensor') -> 'Tensor':
        r"""
        Compute similarity between two sets of embeddings.

        Args:
            x_xc: First set of embeddings with shape ``(..., C)``.
            y_xc: Second set of embeddings with shape ``(..., C)``.

        Returns:
            Similarity scores with shape ``(...)``.
        """
        ...


class CosineSimilarity(EmbeddingSimilarityBase, registry_name="Cosine"):
    r"""
    Cosine similarity metric for embeddings.

    Computes the cosine similarity between normalized embeddings.
    Returns values in range [-1, 1] where 1 means identical direction.

    Examples:
        >>> x_n2 = tensor([[+1.0, 0.0]])
        >>> y_n2 = tensor([[0.0, +2.0]])
        >>> z_n2 = tensor([[-2.0, 0.0]])
        >>> op = CosineSimilarity()
        >>> xt.testing.assert_allclose(op.compute(x_n2, x_n2), [1])
        >>> xt.testing.assert_allclose(op.compute(x_n2, y_n2), [0])
        >>> xt.testing.assert_allclose(op.compute(x_n2, z_n2), [-1])
    """

    @override
    @classmethod
    def compute(cls, x_xc: 'Tensor', y_xc: 'Tensor') -> 'Tensor':
        r"""
        Compute cosine similarity between embeddings.

        Args:
            x_xc: First set of embeddings with shape ``(..., C)``.
            y_xc: Second set of embeddings with shape ``(..., C)``.

        Returns:
            Cosine similarity scores with shape ``(...)`` in range [-1, 1].
        """
        x_xc = normalize(x_xc)
        y_xc = normalize(y_xc)
        return xt.sum(x_xc * y_xc, -1)


class L2Similarity(EmbeddingSimilarityBase, registry_name="L2"):
    r"""
    L2 distance-based similarity metric for embeddings.

    Computes similarity based on L2 (Euclidean) distance between embeddings.
    The distance is normalized and converted to a similarity score in [0, 1].

    Examples:
        >>> x_n2 = tensor([[+1.0, 0.0]])
        >>> y_n2 = tensor([[0.0, +2.0]])
        >>> z_n2 = tensor([[-2.0, 0.0]])

        >>> op = L2Similarity()
        >>> xt.testing.assert_allclose(op.compute(x_n2, x_n2), [1])
        >>> xt.testing.assert_allclose(op.compute(x_n2, y_n2), [0.292893])
        >>> xt.testing.assert_allclose(op.compute(x_n2, z_n2), [0])

        >>> op = L2Similarity(normalized_max=None)
        >>> xt.testing.assert_allclose(op.compute(x_n2, x_n2), [1])
        >>> xt.testing.assert_allclose(op.compute(x_n2, y_n2), [0.254643])
        >>> xt.testing.assert_allclose(op.compute(x_n2, z_n2), [0])
    """

    def __init__(self, normalized_max: tp.Optional[float] = 2.0):
        r"""
        Initialize L2 similarity metric.

        Args:
            normalized_max: Maximum distance for normalization. If None,
                uses sum of norms of input vectors. Defaults to 2.0.
        """
        self.normalized_max: tp.Optional[float] = normalized_max

    @override
    def compute(self, x_xc: 'Tensor', y_xc: 'Tensor') -> 'Tensor':
        r"""
        Compute L2-based similarity between embeddings.

        Args:
            x_xc: First set of embeddings with shape ``(..., C)``.
            y_xc: Second set of embeddings with shape ``(..., C)``.

        Returns:
            Similarity scores with shape ``(...)`` in range [0, 1].
        """
        x_xc = self.maybe_normalize(x_xc)
        y_xc = self.maybe_normalize(y_xc)
        d_xc = norm(x_xc - y_xc)
        m = self.normalized_max
        if m is None: m = norm(x_xc) + norm(y_xc)  # fmt: skip
        return 1 - xt.squeeze(d_xc / m, -1)

    def maybe_normalize(self, x_xc: 'Tensor') -> 'Tensor':
        r"""
        Normalize embeddings if normalized_max is set.

        Args:
            x_xc: Input embeddings with shape ``(..., C)``.

        Returns:
            Normalized embeddings if normalized_max is not None,
            otherwise returns original embeddings.
        """
        return x_xc if self.normalized_max is None else normalize(x_xc)
