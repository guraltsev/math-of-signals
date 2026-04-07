"""Compatibility re-export for the canonical identifier subpackage.

Prefer ``gu_toolkit.identifiers`` or ``gu_toolkit.identifiers.policy``
for new code. This module remains to avoid breaking existing imports.
"""

from .identifiers.policy import *
from .identifiers.policy import __all__
