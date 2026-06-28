"""ID value objects: equality, hashing, repr, str."""

from __future__ import annotations

from uuid import UUID

from uuid_extensions import uuid7

from lens_domain.ids import (
    CategoryId,
    ChangeId,
    DomainId,
    ProfileId,
    SnapshotId,
    UrlId,
)


def _uuid() -> UUID:
    return uuid7()


class TestDomainId:
    def test_value_property(self) -> None:
        v = _uuid()
        did = DomainId(v)
        assert did.value == v

    def test_eq_same_value_true(self) -> None:
        v = _uuid()
        a = DomainId(v)
        b = DomainId(v)
        assert a == b

    def test_eq_different_false(self) -> None:
        a = DomainId(_uuid())
        b = DomainId(_uuid())
        assert a != b

    def test_eq_other_type_false(self) -> None:
        a = DomainId(_uuid())
        assert a != _uuid()
        assert a != "not-an-id"

    def test_hash_consistent(self) -> None:
        v = _uuid()
        a = DomainId(v)
        b = DomainId(v)
        assert hash(a) == hash(b)

    def test_repr(self) -> None:
        v = _uuid()
        did = DomainId(v)
        assert repr(did) == f"DomainId({v!s})"

    def test_str(self) -> None:
        v = _uuid()
        did = DomainId(v)
        assert str(did) == str(v)


class TestCategoryId:
    def test_value_property(self) -> None:
        v = _uuid()
        cid = CategoryId(v)
        assert cid.value == v

    def test_eq_same_value_true(self) -> None:
        v = _uuid()
        a = CategoryId(v)
        b = CategoryId(v)
        assert a == b

    def test_eq_different_false(self) -> None:
        a = CategoryId(_uuid())
        b = CategoryId(_uuid())
        assert a != b

    def test_repr(self) -> None:
        v = _uuid()
        cid = CategoryId(v)
        assert repr(cid) == f"CategoryId({v!s})"

    def test_str(self) -> None:
        v = _uuid()
        cid = CategoryId(v)
        assert str(cid) == str(v)


class TestUrlId:
    def test_value_property(self) -> None:
        v = _uuid()
        uid = UrlId(v)
        assert uid.value == v

    def test_eq_same_value_true(self) -> None:
        v = _uuid()
        a = UrlId(v)
        b = UrlId(v)
        assert a == b

    def test_eq_different_false(self) -> None:
        a = UrlId(_uuid())
        b = UrlId(_uuid())
        assert a != b

    def test_repr(self) -> None:
        v = _uuid()
        uid = UrlId(v)
        assert repr(uid) == f"UrlId({v!s})"

    def test_str(self) -> None:
        v = _uuid()
        uid = UrlId(v)
        assert str(uid) == str(v)


class TestSnapshotId:
    def test_value_property(self) -> None:
        v = _uuid()
        sid = SnapshotId(v)
        assert sid.value == v

    def test_eq_same_value_true(self) -> None:
        v = _uuid()
        a = SnapshotId(v)
        b = SnapshotId(v)
        assert a == b

    def test_repr(self) -> None:
        v = _uuid()
        sid = SnapshotId(v)
        assert repr(sid) == f"SnapshotId({v!s})"

    def test_str(self) -> None:
        v = _uuid()
        sid = SnapshotId(v)
        assert str(sid) == str(v)


class TestProfileId:
    def test_value_property(self) -> None:
        v = _uuid()
        pid = ProfileId(v)
        assert pid.value == v

    def test_eq_same_value_true(self) -> None:
        v = _uuid()
        a = ProfileId(v)
        b = ProfileId(v)
        assert a == b

    def test_repr(self) -> None:
        v = _uuid()
        pid = ProfileId(v)
        assert repr(pid) == f"ProfileId({v!s})"

    def test_str(self) -> None:
        v = _uuid()
        pid = ProfileId(v)
        assert str(pid) == str(v)


class TestChangeId:
    def test_value_property(self) -> None:
        v = _uuid()
        cid = ChangeId(v)
        assert cid.value == v

    def test_eq_same_value_true(self) -> None:
        v = _uuid()
        a = ChangeId(v)
        b = ChangeId(v)
        assert a == b

    def test_repr(self) -> None:
        v = _uuid()
        cid = ChangeId(v)
        assert repr(cid) == f"ChangeId({v!s})"

    def test_str(self) -> None:
        v = _uuid()
        cid = ChangeId(v)
        assert str(cid) == str(v)
