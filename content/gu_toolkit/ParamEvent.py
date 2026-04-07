"""Standardized parameter-change event payloads.

This module defines ``ParamEvent``, the immutable structure emitted by
``ParamRef.observe`` and consumed by Figure parameter hooks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sympy.core.symbol import Symbol

if TYPE_CHECKING:
    from .ParamRef import ParamRef


@dataclass(frozen=True)
class ParamEvent:
    """Normalized parameter change event emitted by ParamRef observers.
    
    Full API
    --------
    ``ParamEvent(parameter: Symbol, old: Any, new: Any, ref: ParamRef, raw: Any=None)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    parameter : Symbol
        Parameter symbol or parameter reference associated with this API. Required.
    
    old : Any
        Value for ``old`` in this API. Required.
    
    new : Any
        Value for ``new`` in this API. Required.
    
    ref : ParamRef
        Value for ``ref`` in this API. Required.
    
    raw : Any, optional
        Value for ``raw`` in this API. Defaults to ``None``.
    
    Returns
    -------
    ParamEvent
        New ``ParamEvent`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``raw=None``: Value for ``raw`` in this API.
    
    Architecture note
    -----------------
    ``ParamEvent`` lives in ``gu_toolkit.ParamEvent``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.ParamEvent import ParamEvent
        obj = ParamEvent(...)
    
    Discovery-oriented use::
    
        help(ParamEvent)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(ParamEvent)`` and ``dir(ParamEvent)`` to inspect adjacent members.
    """

    parameter: Symbol
    old: Any
    new: Any
    ref: ParamRef
    raw: Any = None
