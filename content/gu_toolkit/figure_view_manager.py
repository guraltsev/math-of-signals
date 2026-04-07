"""View registry and active-selection policy for :class:`gu_toolkit.Figure`.

`ViewManager` owns the pure registry-level concerns for public ``View``
objects: registration, active id bookkeeping, validation, and stale-state
tracking. It does not construct widgets or decide layout behavior.
"""

from __future__ import annotations

from collections.abc import Iterable

from .figure_view import View


class ViewManager:
    """Own workspace views and active-view selection state.
    
    Full API
    --------
    ``ViewManager(default_view_id: str=DEFAULT_VIEW_ID)``
    
    Public members exposed from this class: ``active_view_id``, ``views``, ``default_view_id``, ``active_view``, ``require_view``,
        ``register_view``, ``set_active_view``, ``remove_view``, ``mark_stale``,
        ``clear_stale``
    
    Parameters
    ----------
    default_view_id : str, optional
        Identifier for the default view or fallback view. Defaults to ``DEFAULT_VIEW_ID``.
    
    Returns
    -------
    ViewManager
        New ``ViewManager`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``default_view_id=DEFAULT_VIEW_ID``: Identifier for the default view or fallback view.
    
    Architecture note
    -----------------
    ``ViewManager`` lives in ``gu_toolkit.figure_view_manager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_view_manager import ViewManager
        obj = ViewManager(...)
    
    Discovery-oriented use::
    
        help(ViewManager)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(ViewManager)`` and ``dir(ViewManager)`` to inspect adjacent members.
    """

    DEFAULT_VIEW_ID = "main"

    def __init__(self, *, default_view_id: str = DEFAULT_VIEW_ID) -> None:
        self._default_view_id = str(default_view_id)
        self._views: dict[str, View] = {}
        self._active_view_id = self._default_view_id

    @property
    def active_view_id(self) -> str:
        """Return the currently active view id.
        
        Full API
        --------
        ``obj.active_view_id -> str``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ViewManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ViewManager(...)
            current = obj.active_view_id
        
        Discovery-oriented use::
        
            help(ViewManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ViewManager)`` and ``dir(ViewManager)`` to inspect adjacent members.
        """
        return self._active_view_id

    @property
    def views(self) -> dict[str, View]:
        """Return the mutable view registry.
        
        Full API
        --------
        ``obj.views -> dict[str, View]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        dict[str, View]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ViewManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ViewManager(...)
            current = obj.views
        
        Discovery-oriented use::
        
            help(ViewManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ViewManager)`` and ``dir(ViewManager)`` to inspect adjacent members.
        """
        return self._views

    @property
    def default_view_id(self) -> str:
        """Return the stable default view id.
        
        Full API
        --------
        ``obj.default_view_id -> str``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ViewManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ViewManager(...)
            current = obj.default_view_id
        
        Discovery-oriented use::
        
            help(ViewManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ViewManager)`` and ``dir(ViewManager)`` to inspect adjacent members.
        """
        return self._default_view_id

    def active_view(self) -> View:
        """Return the active public view object.
        
        Full API
        --------
        ``obj.active_view() -> View``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        View
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ViewManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ViewManager(...)
            result = obj.active_view(...)
        
        Discovery-oriented use::
        
            help(ViewManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ViewManager)`` and ``dir(ViewManager)`` to inspect adjacent members.
        """
        return self._views[self._active_view_id]

    def require_view(self, view_id: str) -> View:
        """Return ``view_id`` or raise ``KeyError``.
        
        Full API
        --------
        ``obj.require_view(view_id: str) -> View``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        View
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ViewManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ViewManager(...)
            result = obj.require_view(...)
        
        Discovery-oriented use::
        
            help(ViewManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ViewManager)`` and ``dir(ViewManager)`` to inspect adjacent members.
        """
        if view_id not in self._views:
            raise KeyError(f"Unknown view: {view_id}")
        return self._views[view_id]

    def register_view(self, view: View) -> View:
        """Register an already-created :class:`View` object.
        
        Full API
        --------
        ``obj.register_view(view: View) -> View``
        
        Parameters
        ----------
        view : View
            View identifier or view-scoped target. When omitted, the active view is used. Required.
        
        Returns
        -------
        View
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ViewManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ViewManager(...)
            result = obj.register_view(...)
        
        Discovery-oriented use::
        
            help(ViewManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ViewManager)`` and ``dir(ViewManager)`` to inspect adjacent members.
        """
        key = str(view.id)
        if key in self._views:
            raise ValueError(f"View '{key}' already exists")
        is_first = not self._views
        view.is_active = is_first
        if is_first:
            self._active_view_id = key
        self._views[key] = view
        return view

    def set_active_view(
        self,
        view_id: str,
        *,
        current_viewport_x: tuple[float, float] | None = None,
        current_viewport_y: tuple[float, float] | None = None,
    ) -> tuple[View, View] | None:
        """Switch the active view id and update per-view active flags.
        
        Full API
        --------
        ``obj.set_active_view(view_id: str, *, current_viewport_x: tuple[float, float] | None=None, current_viewport_y: tuple[float, float] | None=None) -> tuple[View, View] | None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        current_viewport_x : tuple[float, float] | None, optional
            Value for ``current_viewport_x`` in this API. Defaults to ``None``.
        
        current_viewport_y : tuple[float, float] | None, optional
            Value for ``current_viewport_y`` in this API. Defaults to ``None``.
        
        Returns
        -------
        tuple[View, View] | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``current_viewport_x=None``: Value for ``current_viewport_x`` in this API.
        - ``current_viewport_y=None``: Value for ``current_viewport_y`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``ViewManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ViewManager(...)
            result = obj.set_active_view(...)
        
        Discovery-oriented use::
        
            help(ViewManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ViewManager)`` and ``dir(ViewManager)`` to inspect adjacent members.
        """
        key = str(view_id)
        if key not in self._views:
            raise KeyError(f"Unknown view: {key}")
        if key == self._active_view_id:
            return None

        current = self.active_view()
        if current_viewport_x is not None:
            current.viewport_x_range = tuple(float(v) for v in current_viewport_x)
        if current_viewport_y is not None:
            current.viewport_y_range = tuple(float(v) for v in current_viewport_y)
        current.is_active = False

        self._active_view_id = key
        nxt = self.active_view()
        nxt.is_active = True
        return current, nxt

    def remove_view(self, view_id: str) -> None:
        """Remove a non-active, non-default view if present.
        
        Full API
        --------
        ``obj.remove_view(view_id: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ViewManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ViewManager(...)
            obj.remove_view(...)
        
        Discovery-oriented use::
        
            help(ViewManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ViewManager)`` and ``dir(ViewManager)`` to inspect adjacent members.
        """
        key = str(view_id)
        if key == self._active_view_id:
            raise ValueError("Cannot remove active view")
        if key == self._default_view_id:
            raise ValueError("Cannot remove default view")
        self._views.pop(key, None)

    def mark_stale(
        self,
        *,
        view_id: str | None = None,
        except_views: Iterable[str] = (),
    ) -> None:
        """Mark one or more views stale.
        
        Full API
        --------
        ``obj.mark_stale(*, view_id: str | None=None, except_views: Iterable[str]=()) -> None``
        
        Parameters
        ----------
        view_id : str | None, optional
            Identifier for the relevant view inside a figure. Defaults to ``None``.
        
        except_views : Iterable[str], optional
            Value for ``except_views`` in this API. Defaults to ``()``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``view_id=None``: Identifier for the relevant view inside a figure.
        - ``except_views=()``: Value for ``except_views`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``ViewManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ViewManager(...)
            obj.mark_stale(...)
        
        Discovery-oriented use::
        
            help(ViewManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ViewManager)`` and ``dir(ViewManager)`` to inspect adjacent members.
        """
        excluded = {str(v) for v in except_views}
        targets = [str(view_id)] if view_id is not None else list(self._views.keys())
        for target in targets:
            if target in excluded:
                continue
            view = self._views.get(target)
            if view is not None:
                view.is_stale = True

    def clear_stale(self, view_id: str) -> None:
        """Reset the stale flag for ``view_id`` if present.
        
        Full API
        --------
        ``obj.clear_stale(view_id: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ViewManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ViewManager(...)
            obj.clear_stale(...)
        
        Discovery-oriented use::
        
            help(ViewManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ViewManager)`` and ``dir(ViewManager)`` to inspect adjacent members.
        """
        view = self._views.get(str(view_id))
        if view is not None:
            view.is_stale = False
