# Python Coding Conventions

> This document defines the coding standards for all Python code in this project.
> It combines **PEP 8** (the official Python style guide) with **Clean Code** principles
> (adapted from Robert C. Martin). All contributors are expected to follow these conventions.
> They are enforced in code review and, where possible, automated via linting and formatting tools.

**Sources:** [PEP 8 – Style Guide for Python Code](https://peps.python.org/pep-0008/) · *Clean Code* & *Clean
Architecture* — Robert C. Martin

---

## Table of Contents

- [Quick Start](#quick-start)
- [Tooling](#tooling)
- [Code Layout](#code-layout)
    - [Indentation](#indentation)
    - [Line Length](#line-length)
    - [Blank Lines](#blank-lines)
    - [Source File Encoding](#source-file-encoding)
    - [Imports](#imports)
    - [Module-Level Dunders](#module-level-dunders)
- [Whitespace](#whitespace)
    - [In Expressions and Statements](#in-expressions-and-statements)
    - [Other Recommendations](#other-recommendations)
- [Trailing Commas](#trailing-commas)
- [String Quotes](#string-quotes)
- [Naming](#naming)
    - [Naming Style Table](#naming-style-table)
    - [Naming Rules and Intent](#naming-rules-and-intent)
- [Type Annotations](#type-annotations)
- [Functions](#functions)
- [Classes](#classes)
- [SOLID Principles](#solid-principles)
- [Error Handling](#error-handling)
- [Documentation](#documentation)
- [Comments](#comments)
- [Programming Recommendations](#programming-recommendations)
- [Testing](#testing)
- [Concurrency](#concurrency)
- [Quick Reference](#quick-reference)
- [Contributing](#contributing)

---

## Quick Start

```bash
# Install dev dependencies
pip install ruff mypy pytest

# Format
ruff format .

# Lint
ruff check .

# Type-check
mypy .

# Test
pytest
```

---

## Tooling

| Tool     | Purpose                                                  | Config file      |
|----------|----------------------------------------------------------|------------------|
| `ruff`   | Auto-formatting (`ruff format`) and linting              | `pyproject.toml` |
| `mypy`   | Static type checking                                     | `pyproject.toml` |
| `pytest` | Test runner                                              | `pyproject.toml` |

Formatting and linting are enforced in CI. PRs that fail these checks will not be merged.

Recommended `pyproject.toml` baseline:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
docstring-code-format = true

[tool.mypy]
strict = true
python_version = "3.11"
```

---

## Code Layout

### Indentation

Use **4 spaces** per indentation level. Never use tabs.

**Continuation lines** must align with the opening delimiter, or use a hanging indent of 4 spaces with no argument on
the first line:

```python
# ✓ — aligned with opening delimiter
result = some_long_function_name(argument_one,
                                 argument_two,
                                 argument_three)

# ✓ — hanging indent (preferred when delimiter alignment is too deep)
result = some_long_function_name(
    argument_one,
    argument_two,
    argument_three,
)


# ✗ — no visual distinction between arguments and body
def process(
        arg_one, arg_two,
        arg_three):
    do_something()


# ✓ — extra indent level distinguishes signature from body
def process(
        arg_one,
        arg_two,
        arg_three,
) -> None:
    do_something()
```

**Closing brace / bracket / parenthesis** — two accepted styles:

```python
# ✓ — closing brace under last line's first non-whitespace
result = some_function(
    arg_one,
    arg_two,
)

# ✓ — closing brace under the line that opened the construct
result = some_function(
    arg_one,
    arg_two,
)
```

**Operator position in line breaks** — break *before* the binary operator:

```python
# ✗ — operator left behind at end of line
income = (gross_wages +
          taxable_interest +
          dividends)

# ✓ — operator at the start of the continuation line
income = (
        gross_wages
        + taxable_interest
        + dividends
)
```

### Line Length

| Content type | Max length                                            |
|--------------|-------------------------------------------------------|
| All lines    | **100 characters** (enforced by `ruff format`)        |

The 100-character limit is enforced formatter-side (`ruff format`, with `E501` ignored in
`[tool.ruff.lint]`); there is no separate sub-limit for docstrings or comments. If a tighter
docstring limit is required, enable `pycodestyle.max-doc-length` (`W505`) explicitly in
`pyproject.toml`.

Prefer implicit line continuation inside parentheses, brackets, or braces over backslash continuation.

### Blank Lines

- **2 blank lines** between top-level definitions (functions and classes).
- **1 blank line** between method definitions inside a class.
- **1 blank line** (sparingly) inside functions to separate logical sections.

```python
class Foo:
    def method_one(self) -> None:
        ...

    def method_two(self) -> None:
        ...


class Bar:
    ...
```

### Source File Encoding

- Default to **UTF-8**. No encoding declaration needed for UTF-8 files.
- Avoid non-ASCII characters in identifiers unless the domain requires them.

### Imports

**Order** — three groups separated by a blank line:

1. Standard library
2. Third-party packages
3. Local application / library modules

```python
# ✓
import os
import sys
from pathlib import Path

import httpx
from pydantic import BaseModel

from mypackage.core import TradeRepository
from mypackage.models import TradeRecord
```

**Rules:**

- One import per line. Never combine: `import os, sys`.
- Prefer absolute imports. Use explicit relative imports only for intra-package imports.
- Wildcard imports (`from module import *`) are forbidden except in `__init__.py` re-exports accompanied by an explicit
  `__all__`.
- `ruff --select I` (isort) enforces ordering automatically.

```python
# ✗
import os, sys
from mymodule import *

# ✓
import os
import sys
from mymodule import ClassA, ClassB
```

### Module-Level Dunders

Module-level dunders (`__all__`, `__author__`, `__version__`) go **after** the module docstring and **before** any
imports except `from __future__`:

```python
"""Trade processing pipeline."""

from __future__ import annotations

__all__ = ["TradeProcessor"]
__version__ = "1.0.0"

import os
from pathlib import Path
```

---

## Whitespace

### In Expressions and Statements

Avoid extraneous whitespace:

```python
# ✗ — immediately inside brackets
spam(ham[1], {eggs: 2})

# ✓
spam(ham[1], {"eggs": 2})

# ✗ — before colon, semicolon, or comma
if x == 4:
    print(x, y);
    x, y = y, x

# ✓
if x == 4:
    print(x, y)
    x, y = y, x

# ✗ — before the opening parenthesis of a function call or index
spam(1)
dct['key']

# ✓
spam(1)
dct["key"]
```

Surround binary operators with **exactly one space** on each side: `=`, `+=`, `==`, `!=`, `<`, `>`, `<=`, `>=`,
`in`, `not in`, `is`, `is not`, `and`, `or`, `not`.

**No spaces** around `=` for keyword arguments or bare default values:

```python
# ✗
def connect(host="localhost", port=8080): ...


# ✓
def connect(host="localhost", port=8080): ...


# ✓ — annotation present: spaces around =
def connect(host: str = "localhost", port: int = 8080) -> None: ...
```

**Slice notation** — treat `:` as a binary operator; keep spacing consistent:

```python
# ✓
ham[1:9], ham[lower:upper], ham[lower + offset: upper + offset]

# ✗ — inconsistent spacing
ham[lower + offset:upper + offset]
ham[1: 9], ham[1:9]
```

### Other Recommendations

- Do not use semicolons to separate statements on one line.
- Avoid compound statements (multiple statements on one line):

```python
# ✗
if foo: bar(); baz()

# ✓
if foo:
    bar()
    baz()
```

---

## Trailing Commas

Trailing commas are **required** in single-element tuples and **recommended** in multi-line constructs:

```python
# ✓ — single-element tuple
FILES = ("setup.py",)

# ✓ — multi-line: trailing comma enables clean diffs
VALID_STATUSES = (
    "pending",
    "active",
    "cancelled",
)


# ✓ — function definition
def create_user(
        name: str,
        email: str,
        role: str,
) -> User: ...
```

---

## String Quotes

- Use **double quotes** `"..."` consistently (`ruff format` default).
- Use single quotes `'...'` only to avoid backslash escapes when the string contains double quotes.
- Use triple double quotes `"""..."""` for all docstrings.
- Use **f-strings** for interpolation; avoid `%` formatting and `.format()` for new code.

```python
# ✓
name = "alice"
message = f"Hello, {name}!"
path = 'He said "hello"'  # avoids escape
```

---

## Naming

### Naming Style Table

| Identifier          | Style                                     | Example                     |
|---------------------|-------------------------------------------|-----------------------------|
| Packages            | `lowercase` (no underscores if avoidable) | `mypackage`                 |
| Modules             | `lowercase_with_underscores`              | `trade_parser`              |
| Classes             | `CapWords` (PascalCase)                   | `TradeProcessor`            |
| Exceptions          | `CapWords`, suffix `Error`                | `ValidationError`           |
| Functions / Methods | `lowercase_with_underscores`              | `get_balance`               |
| Instance variables  | `lowercase_with_underscores`              | `self._balance`             |
| Constants           | `UPPER_SNAKE_CASE`                        | `MAX_RETRIES`               |
| Type variables      | Short `CapWords`                          | `T`, `KT`, `VT`             |
| Type aliases        | `CapWords`                                | `Vector = list[float]`      |
| Non-public          | prefix `_`                                | `_internal_helper`          |
| Name-mangled        | prefix `__`                               | `__private` (use sparingly) |
| Dunder protocol     | `__double_both__`                         | `__init__`, `__str__`       |

### Naming Rules and Intent

Names must answer: *what it is*, *why it exists*, and *how it is used*. If a name needs a comment, rename it.

**Exception-name suffix.** The table above prescribes the `Error` suffix, but domain- and
application-layer exception classes are exempt: they use the spec / domain term directly
(`InvalidHostname`, `DuplicateUrl`, `NoChannelsBound`, `ValidationFailed`) so the name reads
identically in code, tests, docs, and event payloads. Ruff's `N818` is therefore ignored
globally in `pyproject.toml [tool.ruff.lint].ignore`; do not reintroduce per-line `# noqa: N818`
suppressions.

**Functions and methods** use verbs:

```python
# ✗
def account_balance(): ...


def name_change(new_name): ...


# ✓
def get_balance() -> float: ...


def update_name(new_name: str) -> None: ...
```

**Classes** use nouns — they *represent* things, not actions:

```python
# ✗
class ProcessData: ...


# ✓
class TradeRecord: ...


class PaymentGateway: ...
```

**Constants** are annotated with `Final`:

```python
from typing import Final

MAX_RETRY_ATTEMPTS: Final[int] = 3
WORK_DAYS_PER_WEEK: Final[int] = 5
```

**One word per concept** — pick `fetch`, `get`, or `retrieve` and use it consistently across the entire codebase.

**Avoid abbreviations** unless they are universally understood in the domain (`url`, `id`, `db`, `http`).

**Non-public interface:**

- Single underscore prefix (`_name`) signals internal use — a convention, not language-enforced.
- Double underscore prefix (`__name`) triggers name-mangling; use sparingly and only when subclass naming conflicts
  are a genuine concern.
- Never invent `__dunder__` names — these are reserved for Python itself.

---

## Type Annotations

Type annotations are **required** on all public function and method signatures.

```python
# ✗
def calculate(principal, rate, years):
    ...


# ✓
def calculate_compound_interest(
        principal: float,
        annual_rate: float,
        years: int,
) -> float:
    ...
```

**Variable annotations** — use when the type is not obvious from context:

```python
pending_orders: list[Order] = []
cache: dict[str, User] = {}
```

**Always annotate `None` returns explicitly:**

```python
# ✗
def shutdown(): ...


# ✓
def shutdown() -> None: ...
```

**`Optional` vs union syntax** — prefer `X | None` (Python 3.10+):

```python
# ✓ — Python 3.10+
def find_user(user_id: str) -> User | None: ...


# ✓ — Python < 3.10
from typing import Optional


def find_user(user_id: str) -> Optional[User]: ...
```

**`TYPE_CHECKING` guard** — for annotation-only imports to avoid circular imports:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypackage.models import HeavyModel
```

---

## Functions

### Core Rules

| Rule                      | Guidance                                                                                 |
|---------------------------|------------------------------------------------------------------------------------------|
| **Small**                 | Aim for ≤ 20 lines. If it scrolls, split it.                                             |
| **Single responsibility** | Cannot extract another meaningful named function from it.                                |
| **One abstraction level** | High-level orchestration must not mix with low-level detail.                             |
| **No side effects**       | A function's contract is its signature — no hidden reads or mutations.                   |
| **CQS**                   | Either command (mutate, return `None`) or query (return value, no mutation). Never both. |

### Argument Count

- **0 args** — ideal
- **1 arg** — good
- **2 args** — acceptable
- **3 args** — justify carefully
- **4+ args** — wrap in a `@dataclass` or `TypedDict`

```python
# ✗
def create_user(name, email, role, department, location, is_active): ...


# ✓
@dataclass
class UserCreationRequest:
    name: str
    email: str
    role: str
    department: str
    location: str
    is_active: bool = True


def create_user(request: UserCreationRequest) -> User: ...
```

### Avoid Flag Arguments

```python
# ✗
def render(is_admin: bool) -> str: ...


# ✓
def render_admin_view() -> str: ...


def render_user_view() -> str: ...
```

### Prefer Pure Functions and Immutable Returns

```python
# ✗ — mutates input
def normalize_tags(tags: list[str]) -> None:
    for i, tag in enumerate(tags):
        tags[i] = tag.lower().strip()


# ✓ — returns a new list
def normalize_tags(tags: list[str]) -> list[str]:
    return [tag.lower().strip() for tag in tags]
```

Prefer `sorted()` and `reversed()` over in-place variants.

### Don't Repeat Yourself (DRY)

```python
# ✗ — logic duplicated
class SavingsAccount:
    def has_enough_collateral(self, loan: float) -> bool:
        return self.balance >= loan / 2


class CheckingAccount:
    def has_enough_collateral(self, loan: float) -> bool:
        return self.balance >= loan / 2


# ✓ — single authoritative definition in base class
class BankAccount(ABC):
    @abstractmethod
    def has_enough_collateral(self, loan: float) -> bool: ...


class SavingsAccount(BankAccount):
    def has_enough_collateral(self, loan: float) -> bool:
        return self.balance >= loan / 2


class CheckingAccount(BankAccount):
    def has_enough_collateral(self, loan: float) -> bool:
        return self.balance >= 2 * loan / 3
```

### Vertical Ordering — Newspaper Rule

The most important, highest-level code comes first. Helpers appear below their callers:

```python
def process_trades(filename: str) -> None:  # public entry point — top
    lines = _read_lines(filename)
    trades = _parse_trades(lines)
    _store_trades(trades)


def _read_lines(filename: str) -> list[str]: ...


def _parse_trades(lines: list[str]) -> list[TradeRecord]: ...


def _store_trades(trades: list[TradeRecord]) -> None: ...
```

---

## Classes

### Single Responsibility

A class should have **one reason to change**. If its purpose requires "and", split it.

```python
# ✗ — reads, parses, and stores — three responsibilities
class TradeProcessor:
    def process_trades(self, filename: str) -> None: ...


# ✓ — each class owns one concern
class FileDataProvider(DataProvider): ...


class CommaTradeParser(TradeDataParser): ...


class PostgresTradeRepository(TradeRepository): ...


class TradeProcessor:
    def __init__(
            self,
            provider: DataProvider,
            parser: TradeDataParser,
            repository: TradeRepository,
    ) -> None: ...
```

### Member Ordering

1. Class-level constants and type aliases
2. `__init__`
3. Public methods
4. Protected helpers (`_method`)
5. Private helpers (`__method`)
6. Dunder methods (`__str__`, `__eq__`, `__repr__`)

### Prefer Composition Over Inheritance

Inheritance models IS-A; composition models HAS-A. Favour composition when extending behaviour without modifying
existing classes.

### Data Structures vs. Objects

|             | Data Structure              | Object                         |
|-------------|-----------------------------|--------------------------------|
| **Exposes** | Its fields                  | Behaviour through methods      |
| **Hides**   | Nothing                     | Internal representation        |
| **Use for** | DTOs, config, plain records | Domain entities with behaviour |

```python
@dataclass(frozen=True)
class Money:
    amount: float
    currency: str
```

### Law of Demeter

Only call methods on: yourself, your arguments, objects you create, or your direct instance variables:

```python
# ✗
amount = order.get_customer().get_wallet().get_balance()

# ✓
amount = order.get_customer_balance()
```

---

## SOLID Principles

### S — Single Responsibility

> A class should have only one reason to change.

### O — Open / Closed

> Open for extension, closed for modification.

```python
# ✗ — must edit OnlineCart for every new payment method
class OnlineCart:
    def check_out(self, payment_type: str) -> None:
        if payment_type == "paypal":
            ...
        elif payment_type == "stripe":
            ...


# ✓ — inject the strategy; OnlineCart never changes
class Payment(ABC):
    @abstractmethod
    def pay(self) -> None: ...


class OnlineCart:
    def __init__(self, payment: Payment) -> None:
        self._payment = payment

    def check_out(self) -> None:
        self._payment.pay()
```

### L — Liskov Substitution

> Subtypes must be substitutable for their base types without altering correctness.

```python
# ✗ — subclass rejects method defined by base
class CheckingAccount(BankAccount):
    def add_interest(self) -> None:
        pass


# ✓ — split the interface
class InterestBearing(ABC):
    @abstractmethod
    def add_interest(self) -> None: ...


class SavingsAccount(BankAccount, InterestBearing):
    def add_interest(self) -> None:
        self.deposit(0.1 * self._balance)


class CheckingAccount(BankAccount):
    pass  # correctly does not implement InterestBearing
```

### I — Interface Segregation

> No client should be forced to depend on methods it does not use.

```python
from typing import Protocol


class Drawable(Protocol):
    def draw(self) -> None: ...


class Serializable(Protocol):
    def to_dict(self) -> dict: ...
```

### D — Dependency Inversion

> High-level modules must not depend on low-level modules. Both must depend on abstractions.

```python
# ✗
class TradeProcessor:
    def __init__(self) -> None:
        self._repo = PostgresTradeRepository()


# ✓
class TradeProcessor:
    def __init__(self, repository: TradeRepository) -> None:
        self._repo = repository
```

---

## Error Handling

### Prefer Exceptions to Return Codes

Return codes pollute callers with conditional checks. Exceptions keep the happy path clean.

### Domain Exception Hierarchy

```python
class AppError(Exception):
    """Base exception for all application errors."""


class ValidationError(AppError):
    """Input failed domain validation."""


class NotFoundError(AppError):
    """Requested resource does not exist."""
```

### Do Not Return `None` to Signal Failure

```python
# ✗ — every caller must guard
def find_user(user_id: str) -> User | None: ...


# ✓ — raise when absence is an error
def get_user(user_id: str) -> User:
    user = self._repo.find(user_id)
    if user is None:
        raise NotFoundError(f"User {user_id!r} not found")
    return user
```

**Project exception — repository `get` ports.** Repository / `UnitOfWork` `get_*` methods are
allowed to return `T | None` and the calling use case is responsible for translating absence into
the appropriate domain exception (`InvalidStateTransition`, `UrlNotFound`, etc.) at the application
boundary. This keeps the data-access layer free of domain concerns and lets batch lookups skip the
exception machinery; use-case APIs above the repository still raise, so the "no `None` to signal
failure" rule holds for everything outside `libs/infrastructure` (and the domain ports in
`libs/application/ports.py` they implement).

### Never Swallow Exceptions

```python
# ✗
try:
    parse_record(line)
except Exception:
    pass

# ✓
try:
    parse_record(line)
except MalformedRecordError as e:
    logger.warning("Skipping malformed record: %s", e)
```

### Keep `try` Blocks Narrow

```python
# ✗ — hides which call failed
try:
    data = fetch(url)
    parsed = parse(data)
    store(parsed)
except Exception as e:
    logger.error(e)

# ✓
data = fetch(url)

try:
    parsed = parse(data)
except ParseError as e:
    logger.error("Parse failed: %s", e)
    return

store(parsed)
```

### Exception Chaining

Use `raise ... from` to preserve the original cause:

```python
try:
    result = json.loads(raw)
except json.JSONDecodeError as e:
    raise ParseError("Invalid payload") from e
```

---

## Documentation

Documentation lives in **docstrings only** — never in inline comments inside method bodies.

### File-Level Docstrings

```python
"""Trade processing pipeline: reads, validates, and persists trade records."""
```

### Class Docstrings

```python
class TradeRepository(ABC):
    """Persistence boundary for validated trade records.

    Implementations must guarantee atomicity per batch commit.
    """
```

### Function / Method Docstrings

Use **Google style**:

```python
def parse_trades(lines: list[str]) -> list[TradeRecord]:
    """Parse raw CSV lines into validated trade records.

    Args:
        lines: Raw lines in the format ``SRC_DEST,lots,price``.

    Returns:
        List of valid TradeRecord instances. Malformed lines are skipped.

    Raises:
        ValueError: If ``lines`` is empty.
    """
```

### Docstring Rules

| Rule                         | Detail                                                          |
|------------------------------|-----------------------------------------------------------------|
| **Precise**                  | State the exact contract — no vague phrases like "handles data" |
| **Concise**                  | One-line summary; expand only when the contract is non-obvious  |
| **No implementation detail** | Describe *what* and *why*, never *how*                          |
| **Keep in sync**             | Stale documentation is worse than none                          |
| **Public API only**          | Private helpers (`_method`) rarely need docstrings              |

---

## Comments

### The Only Acceptable Comments

Comments explain **why** — never *what* or *how*.

| Type              | Guidance                                                |
|-------------------|---------------------------------------------------------|
| Legal             | License / copyright headers                             |
| Clarifying intent | Why a non-obvious algorithm or constant is used         |
| Warning           | `# WARNING: not thread-safe — see issue #412`           |
| TODO              | `# TODO(alice): remove after #512 ships`                |
| Regex / format    | Explaining a complex pattern inline with its definition |

**Block comments** — indented to the same level as the code they describe, start with `# ` (one space), complete
sentences:

```python
# Normalise the currency pair before insertion to ensure
# all lookups use the canonical SRC_DEST ordering.
pair = f"{src}_{dest}".upper()
```

**Inline comments** — at least two spaces before `# `, used sparingly:

```python
x = x + 1  # compensate for border
```

### Never Write Internal Comments Inside Methods

```python
# ✗
def process_order(order: Order) -> None:
    # validate before saving
    if not order.items:
        raise ValueError("Order has no items")
    # persist
    db.session.add(order)
    db.session.commit()


# ✓
def process_order(order: Order) -> None:
    validate_order(order)
    persist_order(order)


def validate_order(order: Order) -> None:
    if not order.items:
        raise ValueError("Order has no items")


def persist_order(order: Order) -> None:
    db.session.add(order)
    db.session.commit()
```

### Never Write These

```python
i = 0  # set i to zero           — restates the code
# i = 0                              — commented-out code: delete it, trust VCS
# Added by Alice on 2023-01-10       — journal: use git log
# This function calculates stuff     — too vague to add value
```

---

## Programming Recommendations

### Comparisons to Singletons

Use `is` / `is not` for `None` — never `==`:

```python
# ✗
if result == None: ...

# ✓
if result is None: ...
if result is not None: ...
```

### Boolean Checks

```python
# ✗ — redundant
if len(items) > 0: ...
if items != []: ...

# ✓ — idiomatic
if items: ...
if not items: ...
```

### `isinstance()` Over Type Comparison

```python
# ✗ — does not handle subclasses
if type(x) == int: ...

# ✓
if isinstance(x, int): ...
```

### String Concatenation in Loops

```python
# ✗ — O(n²)
result = ""
for part in parts:
    result += part

# ✓ — O(n)
result = "".join(parts)
```

### Consistent Return Statements

Either all `return` statements return a value, or none do:

```python
# ✗ — inconsistent
def get_value(x):
    if x > 0:
        return x
    # implicit None


# ✓
def get_value(x: int) -> int | None:
    if x > 0:
        return x
    return None
```

### Context Managers for Resources

```python
# ✗
f = open("data.csv")
data = f.read()
f.close()

# ✓
with open("data.csv") as f:
    data = f.read()
```

### Exception Chaining

```python
# ✗ — original cause lost
try:
    json.loads(raw)
except json.JSONDecodeError:
    raise ParseError("Invalid payload")

# ✓ — cause preserved
try:
    json.loads(raw)
except json.JSONDecodeError as e:
    raise ParseError("Invalid payload") from e
```

### Mutable Default Arguments

```python
# ✗ — list is shared across all calls
def append_item(item, target=[]):
    target.append(item)
    return target


# ✓
def append_item(item, target=None):
    if target is None:
        target = []
    target.append(item)
    return target
```

### f-Strings Over Legacy Formatting

```python
# ✗
msg = "Hello, %s!" % name
msg = "Hello, {}!".format(name)

# ✓
msg = f"Hello, {name}!"
```

---

## Testing

### F.I.R.S.T. Rules

| Letter              | Rule                                            |
|---------------------|-------------------------------------------------|
| **F**ast            | Tests run in milliseconds, not seconds          |
| **I**ndependent     | No test depends on the result of another        |
| **R**epeatable      | Same result in any environment                  |
| **S**elf-validating | Pass or fail — no manual inspection             |
| **T**imely          | Written before or alongside the code under test |

### Naming Convention

```
test_given_<context>_when_<action>_then_<expected_outcome>
```

### Structure: Given / When / Then

```python
def test_given_pending_order_when_cancelled_then_status_is_cancelled():
    # Given
    order = Order(status=OrderStatus.PENDING, items=[item])

    # When
    order.cancel()

    # Then
    assert order.status == OrderStatus.CANCELLED
```

### One Concept per Test

```python
# ✗
def test_order():
    order = Order(items=[item], total=50.0)
    assert order.is_valid()
    assert order.total == 50.0
    assert len(order.items) == 1


# ✓
def test_given_items_present_when_validating_then_order_is_valid():
    order = Order(items=[item], total=50.0)
    assert order.is_valid()


def test_given_order_created_when_checking_total_then_reflects_item_sum():
    order = Order(items=[item], total=50.0)
    assert order.total == 50.0
```

### Test the Contract, Not the Implementation

Tests must not break when internal implementation changes but observable behaviour stays the same.

### Use Dependency Injection to Enable Testing

```python
def test_given_valid_trade_line_when_processing_then_trade_is_stored():
    # Given
    fake_provider = FakeDataProvider(lines=["UGAUSD,2,45.3"])
    fake_repo = InMemoryTradeRepository()
    processor = TradeProcessor(fake_provider, CommaTradeParser(), fake_repo)

    # When
    processor.process_trades()

    # Then
    assert len(fake_repo.stored_trades) == 1
```

---

## Concurrency

### Keep Concurrency Code Separate

Isolate concurrent logic from business logic. Never embed threading primitives into domain classes.

### Prefer Immutable Data

```python
from typing import NamedTuple


class TradeRecord(NamedTuple):
    source_currency: str
    dest_currency: str
    lots: int
    price: float
```

### I/O-Bound Work → `asyncio`

```python
async def fetch_all_prices(symbols: list[str]) -> list[float]:
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_price(session, symbol) for symbol in symbols]
        return await asyncio.gather(*tasks)
```

### CPU-Bound Work → `concurrent.futures`

```python
from concurrent.futures import ProcessPoolExecutor

with ProcessPoolExecutor() as executor:
    results = list(executor.map(compute_heavy, data_chunks))
```

### Limit Shared State

Protect shared state with the minimum necessary primitive (`asyncio.Lock`, `threading.Lock`, `queue.Queue`).

---

## Quick Reference

### Code Smells and Fixes

| Smell                                   | Fix                                                |
|-----------------------------------------|----------------------------------------------------|
| Mysterious name                         | Rename to reveal intent                            |
| Long method (> 20 lines)                | Extract smaller named functions                    |
| Comment explaining a block              | Extract block into a named function                |
| Boolean flag argument                   | Split into two functions                           |
| Duplicated logic                        | Extract to shared function or base class           |
| `if/elif` on a type field               | Replace with polymorphism (Strategy / subclass)    |
| Class with many reasons to change       | Apply SRP — split responsibilities                 |
| Hardcoded dependency in `__init__`      | Inject through constructor                         |
| Swallowed exception                     | Log with context; propagate or handle specifically |
| Mutable default argument                | Use `None` sentinel; assign inside the function    |
| Chained attribute access                | Apply Law of Demeter — ask, don't reach            |
| `== None` / `!= None`                   | Use `is None` / `is not None`                      |
| `type(x) == T`                          | Use `isinstance(x, T)`                             |
| String `+` in a loop                    | Use `"".join(parts)`                               |
| Bare `except:`                          | Catch specific exception types                     |
| Implicit `None` return                  | Add `return None` explicitly for consistency       |
| `%` or `.format()` string interpolation | Use f-strings                                      |

### Naming at a Glance

| Style              | Used for                               |
|--------------------|----------------------------------------|
| `snake_case`       | functions, methods, variables, modules |
| `PascalCase`       | classes, exceptions, type aliases      |
| `UPPER_SNAKE_CASE` | module-level constants                 |
| `_single_prefix`   | non-public (internal) members          |
| `__double_prefix`  | name-mangled (use sparingly)           |
| `__dunder__`       | Python-reserved protocol methods       |

---

## Contributing

1. Fork the repository and create a feature branch.
2. Follow all conventions in this document.
3. Ensure `ruff`, `mypy`, and `pytest` all pass locally before opening a PR.
4. All public functions, methods, and classes must have docstrings.
5. New behaviour must be accompanied by tests following the Given / When / Then structure.
6. PRs that fail CI checks or lack tests will not be merged.

---

> *"A foolish consistency is the hobgoblin of little minds."* — Ralph Waldo Emerson  
> *"However, in Python, PEP 8 consistency is the hobgoblin of maintainable code."*
>
> *"Clean code always looks like it was written by someone who cares."* — Robert C. Martin