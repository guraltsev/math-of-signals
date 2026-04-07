"""Utilities for converting interactive numeric inputs.

``InputConvert`` centralizes parsing and truncation logic used by widgets and
APIs that accept either Python numeric values or symbolic string expressions.
"""

# === SECTION: InputConvert [id: InputConvert]===
from __future__ import annotations

from typing import Any, Type, TypeVar
import sympy as sp

T = TypeVar("T", int, float, complex)


def InputConvert(obj: Any, dest_type: Type[T] = float, truncate: bool = True) -> T:
    """
    Convert `obj` to `dest_type`.

    Supported destination types:
    - float (strictly real)
    - int
    - complex

    Rules:
    - If `obj` is a number: cast via dest_type(obj).
    - If `obj` is a string:
        1) try float(s) or complex(s)
        2) else parse as a SymPy expression, then evaluate.

    Truncation Rules (`truncate`):
    - When converting Complex -> Real (float/int):
        - If `truncate=True`: Discard imaginary part (projection to real).
        - If `truncate=False`: Raise ValueError if imaginary part != 0.
    - When converting Float -> Int:
        - If `truncate=True`: Truncate decimal part (e.g., 3.9 -> 3).
        - If `truncate=False`: Require exact integer (e.g., 3.0 -> 3, 3.1 -> Error).

    Raises
    ------
    NotImplementedError
        If dest_type is unsupported.
    ValueError
        If conversion fails or violates truncation rules.
    """
    if dest_type not in (float, int, complex):
        raise NotImplementedError(
            f"Unsupported destination type: {dest_type!r}. Only float, int, and complex are supported."
        )

    def _coerce_numeric_value(x: complex) -> T:
        """
        Coerce a numeric value 'x' (normalized to complex) to 'dest_type'
        respecting the 'truncate' flag.
        """
        # 1. Handle Complex Destination
        if dest_type is complex:
            return complex(x)  # type: ignore[return-value]

        # 2. Handle Real Destination (float or int)
        # Check for imaginary part presence
        if x.imag != 0:
            if not truncate:
                raise ValueError(
                    f"Could not convert non-real {x!r} to {dest_type.__name__}: imaginary part is non-zero."
                )
            # If truncate=True, we implicitly discard the imaginary part
        
        r_val = x.real

        # 3. If target is float, we are done
        if dest_type is float:
            return float(r_val)  # type: ignore[return-value]

        # 4. Handle Int Destination
        # We are now dealing with a real float 'r_val'
        if not r_val.is_integer():
            if not truncate:
                raise ValueError(
                    f"Could not convert {x!r} to int: value is not an exact integer."
                )
            # If truncate=True, int() truncates towards zero
        
        return int(r_val)  # type: ignore[return-value]

    # Fast path: numeric types (exclude bool)
    if isinstance(obj, (int, float, complex)) and not isinstance(obj, bool):
        try:
            return _coerce_numeric_value(complex(obj))
        except Exception as e:
            raise ValueError(f"Could not convert {obj!r} to {dest_type.__name__}.") from e

    # String path
    if isinstance(obj, str):
        s = obj.strip()
        if s == "":
            raise ValueError(f"Cannot convert empty string to {dest_type.__name__}.")

        # 1) Plain native conversion
        # Try float first (most common)
        try:
            return _coerce_numeric_value(complex(float(s)))
        except ValueError:
            pass
            
        # Try complex string parsing (e.g. "1+2j")
        try:
            return _coerce_numeric_value(complex(s))
        except ValueError:
            pass

        # 2) SymPy path
        try:
            expr = sp.sympify(s)
            # evalf() returns a SymPy Number. Complex cast handles both Float and Complex sympy types.
            val = complex(expr.evalf())
            return _coerce_numeric_value(val)
        except Exception as e:
            raise ValueError(
                f"Could not convert {obj!r} to {dest_type.__name__} (neither directly nor via SymPy)."
            ) from e

    # Fallback: try converting to complex generically
    try:
        return _coerce_numeric_value(complex(obj))
    except Exception as e:
        raise ValueError(f"Could not convert {obj!r} to {dest_type.__name__}.") from e

# === END OF SECTION: InputConvert [id: InputConvert]===