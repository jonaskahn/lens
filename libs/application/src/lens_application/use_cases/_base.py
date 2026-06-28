"""Use case base class and shared helpers.

A use case is a single-method object: ``async execute(input_dto) -> output_dto``.
The base class wires the UoW so each concrete use case only declares the
operation logic.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lens_application.ports import UnitOfWork

__all__ = [
    "UseCase",
]


class UseCase[Input, Output]:
    """Base class for application-layer use cases.

    Subclasses override :meth:`run`; the public :meth:`execute` runs the UoW
    in a single transaction and applies a uniform exception-translation
    policy (so transport layers only need to know about ApplicationError).
    """

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def execute(self, input_dto: Input) -> Output:
        """Run the use case inside a unit of work and return its output."""
        async with self._uow_factory() as uow:
            result = await self.run(input_dto, uow)
            await uow.commit()
            return result

    async def run(self, input_dto: Input, uow: UnitOfWork) -> Output:  # pragma: no cover
        raise NotImplementedError


_AnyInput: Any = object()
_AnyOutput: Any = object()
