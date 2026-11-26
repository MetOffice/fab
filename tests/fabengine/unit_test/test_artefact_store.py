from contextlib import nullcontext
from os import stat_result, utime
from pathlib import Path

from fabengine.actions import TwoPartPath
from fabengine.artefact_store import Artefact, ArtefactPath, ArtefactStore
from pytest import mark, raises


class TestArtefactStore:
    def test_constructor(self, tmp_path: Path):
        store_path = tmp_path / "cheese" / "beef"
        assert not store_path.exists()
        test_unit = ArtefactStore(store_path)
        assert store_path.is_dir()
        assert len(test_unit) == 0
        assert test_unit.intermediate_dir == store_path

    def test_map(self, tmp_path: Path):
        test_unit = ArtefactStore(tmp_path / "store")
        assert test_unit.exists(ArtefactPath("greek/alpha")) is False

        test_file = tmp_path / "first.txt"
        test_file.write_text("Teapot")
        test_unit.map_file(test_file, ArtefactPath("greek/alpha.txt"))
        assert len(test_unit) == 1
        assert test_unit.exists(ArtefactPath("greek/alpha.txt")) is True
        assert (
            test_unit.get_artefact(ArtefactPath("greek/alpha.txt")).real_filename
            == test_file
        )

        test_2_file = tmp_path / "second.txt"
        test_2_file.write_text("Cheese")
        with raises(RuntimeError):
            # confirms that map_file will fail if the target is already used by the ArtefactStore
            test_unit.map_file(test_2_file, ArtefactPath("greek/alpha.txt"))

        test_3_file = tmp_path / "third.txt"
        test_3_file.write_text("A herring")
        test_unit.map_file(test_file, ArtefactPath("greek/gamma.txt"), label="abc")
        assert test_unit.exists(ArtefactPath("greek/gamma.txt")) is True
        assert (
            test_unit.get_artefact(ArtefactPath("greek/gamma.txt")).real_filename
            == test_file
        )
        assert (
            test_unit.get_artefact(ArtefactPath("greek/gamma.txt")).get_meta("label")
            == "abc"
        )

    def test_notice_file(self, tmp_path: Path) -> None:
        test_unit = ArtefactStore(tmp_path)

        test_path = ArtefactPath("wibble/wobble.txt")
        assert test_unit.exists(test_path) is False

        (tmp_path / test_path).parent.mkdir()
        (tmp_path / test_path).write_text("Sneaky, sneaky")
        assert test_unit.exists(test_path) is False

        test_unit.notice_file(test_path)
        assert test_unit.exists(test_path) is True

    def test_ensure_directory(self, tmp_path: Path):
        intermediate_dir = tmp_path / "intermediate"
        test_unit = ArtefactStore(intermediate_dir)
        assert intermediate_dir.is_dir()
        assert test_unit.ensure_directory(ArtefactPath("")) == intermediate_dir
        assert (
            test_unit.ensure_directory(ArtefactPath("wibble"))
            == intermediate_dir / "wibble"
        )
        assert (intermediate_dir / "wibble").is_dir()

    def test_get_artefact_intermediate(self, tmp_path: Path):
        intermediate_dir = tmp_path / "intermediates"
        test_unit = ArtefactStore(intermediate_dir)
        assert test_unit.exists(ArtefactPath("greek/alpha.txt")) is False

        artefact = test_unit.get_artefact(ArtefactPath("greek/alpha.txt"))
        assert test_unit.exists(ArtefactPath("greek/alpha.txt")) is False
        expected_filename = tmp_path / "intermediates" / "greek" / "alpha.txt"
        assert artefact.real_filename == expected_filename
        expected_dir = intermediate_dir / "greek"
        assert expected_dir.is_dir()

        artefact.real_filename.write_text("Modified")
        artefact_again = test_unit.get_artefact(ArtefactPath("greek/alpha.txt"))
        expected_filename = tmp_path / "intermediates" / "greek" / "alpha.txt"
        assert artefact.real_filename == expected_filename
        assert artefact_again.real_filename.read_text() == "Modified"

    def test_promote_artefact(self, tmp_path: Path):
        intermediate_dir = tmp_path / "intermediates"
        test_unit = ArtefactStore(intermediate_dir)

        # Artefact isn't in store...
        #
        with raises(KeyError):
            test_unit.promote_artefact(ArtefactPath("test.txt"))

        # Map an artefact
        #
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello")
        test_unit.map_file(test_file, ArtefactPath("foo/test.txt"))
        assert list(intermediate_dir.iterdir()) == []
        assert test_unit.exists(ArtefactPath("foo/test.txt")) is True
        assert (
            test_unit.get_artefact(ArtefactPath("foo/test.txt")).real_filename
            == test_file
        )

        # Promote the artefact
        #
        test_unit.promote_artefact(ArtefactPath("foo/test.txt"))
        assert (intermediate_dir / "foo").is_dir()
        assert (intermediate_dir / "foo" / "test.txt").is_symlink()
        assert (intermediate_dir / "foo" / "test.txt").readlink() == test_file
        assert (
            test_unit.get_artefact(ArtefactPath("foo/test.txt")).real_filename
            == intermediate_dir / "foo" / "test.txt"
        )

    def test_iterator(self, tmp_path: Path):
        test_unit = ArtefactStore(tmp_path / "items")
        targets = ("alpha", "beta", "gamma")

        for name in targets:
            test_file = tmp_path / f"{name}.txt"
            test_file.write_text(name)
            test_unit.map_file(test_file, ArtefactPath(f"foo/{name}.txt"))

        for i, artefact in enumerate(test_unit):
            name = targets[i]
            assert isinstance(artefact, Artefact)
            assert str(artefact.virtual_filename) == f"foo/{name}.txt"
            assert str(artefact.real_filename) == str(tmp_path / f"{name}.txt")

    # todo: parametrize?
    def test_status(self, tmp_path: Path):
        test_unit = ArtefactStore(tmp_path / "items")
        test_file = tmp_path / "test"

        assert test_unit.status(ArtefactPath("nosuch")) is None

        test_unit.map_file(test_file, ArtefactPath("dir/test"))
        assert test_unit.status(ArtefactPath("dir/test")) is None
        test_file.touch()
        assert isinstance(test_unit.status(ArtefactPath("dir/test")), stat_result)

        plain_file = tmp_path / "plain"
        assert test_unit.status(plain_file) is None
        plain_file.touch()
        assert isinstance(test_unit.status(plain_file), stat_result)

        two_file = TwoPartPath(tmp_path, Path("two"))
        assert test_unit.status(two_file) is None
        two_file.full.touch()
        assert isinstance(test_unit.status(two_file), stat_result)

    def test_digest(self, tmp_path: Path):
        test_unit = ArtefactStore(tmp_path / "items")
        test_file = tmp_path / "test"

        assert test_unit.digest(ArtefactPath("nosuch")) is None

        test_file.touch()
        result = test_unit.digest(test_file)
        assert result is not None and result.startswith("e3b0c44") is True

        test_file.write_text("abc123")
        result = test_unit.digest(test_file)
        assert result is not None and result.startswith("6ca13d5") is True

    @mark.parametrize(
        "first, second, fresh, expected, handler",
        [
            ([None], [None], True, False, nullcontext()),
            ([None], [None], False, False, nullcontext()),
            ([None], ["abc"], False, False, nullcontext()),
            (["abc"], [None], False, False, nullcontext()),
            (["abc", None], ["abc", "def"], False, False, nullcontext()),
            (["abc", "def"], ["abc", None], False, False, nullcontext()),
            (["abc"], ["abc"], False, True, nullcontext()),
            (["abc", "def"], ["abc", "def"], False, True, nullcontext()),
            (["abc", "def"], ["abc", "def"], True, False, nullcontext()),
            (["abc"], ["abc", "def"], False, False, raises(IndexError)),
            (["abc"], ["abc", "def"], True, False, nullcontext()),
        ],
        ids=[
            "fresh build + None",
            "both None",
            "first None",
            "second None",
            "mixed first",
            "mixed second",
            "single item lists",
            "multi item lists",
            "fresh build + match",
            "mismatched lengths",
            "fresh build + mismatch",
        ],
    )
    def test_reusable_digests(
        self, first, second, fresh, expected, handler, tmp_path: Path
    ):
        test_unit = ArtefactStore(tmp_path / "items", fresh)

        with handler:
            assert test_unit.reusable_digests(first, second) is expected

    @mark.parametrize(
        "inputs, outputs, expected",
        [
            ([("a", 1), ("b", 2), ("c", 3)], [("d", 4), ("e", 5)], True),
            ([("a", 1), ("b", 2), ("c", 3)], [("d", 3), ("e", 4)], False),
            ([("a", 1), ("b", 2), ("c", 3)], [("d", 2), ("e", 4)], False),
            ([("a", 1), ("b", 2), ("c", 3)], [("d", 2), ("e", 3)], False),
            ([("a", 1), ("b", 2), ("c", 3)], [("d", 0), ("e", 0)], False),
            ([("a", 1), ("b", 2), ("c", 3)], [("d", None), ("e", 0)], False),
            ([(Path("a"), 1), ("b", 2), ("c", 3)], [(Path("d"), 4), ("e", 5)], True),
        ],
        ids=[
            "all older",
            "one equal",
            "one lower",
            "equal or lower",
            "all lower",
            "missing output",
            "with paths",
        ],
    )
    def test_reusable(self, inputs, outputs, expected, tmp_path: Path):
        test_unit = ArtefactStore(tmp_path / "items")
        ipaths, opaths = [], []

        for name, stamp in inputs:
            target = tmp_path / name
            artefact = ArtefactPath(f"test/{name}")
            if stamp is not None:
                target.touch()
                utime(target, (stamp, stamp))
            test_unit.map_file(target, artefact)
            ipaths.append(artefact)

        for name, stamp in outputs:
            target = tmp_path / name
            artefact = ArtefactPath(f"test/{name}")
            if stamp is not None:
                target.touch()
                utime(target, (stamp, stamp))
            test_unit.map_file(target, artefact)
            opaths.append(artefact)

        assert test_unit.reusable(ipaths, opaths) is expected

    @mark.parametrize(
        "previous, current, fresh, expected",
        [
            (1, 1, True, False),
            (None, 1, False, False),
            (1, 1, False, True),
            (1, 2, False, True),
            (2, 1, False, False),
        ],
        ids=[
            "fresh build",
            "no previous",
            "same timestamps",
            "current is newer",
            "current is older",
        ],
    )
    def test_valid(
        self,
        previous: int | None,
        current: int,
        fresh: bool,
        expected: bool,
        tmp_path: Path,
        monkeypatch,
    ):
        test_unit = ArtefactStore(tmp_path / "items", fresh)
        test_artefact = test_unit.get_artefact(ArtefactPath("abc"))

        monkeypatch.setattr(Artefact, "get_meta", lambda x, y, z: previous)
        monkeypatch.setattr(
            test_unit, "status", lambda x: stat_result([0] * 8 + [current] + [0])
        )

        assert test_unit.valid(test_artefact) is expected

    def test_as_list(self, tmp_path):
        test_unit = ArtefactStore(tmp_path / "items")
        targets = ("alpha", "beta", "gamma")

        for name in targets:
            test_unit.map_file(Path(name), Path(f"{name[0]}.txt"))

        test_list = test_unit.as_list()
        assert isinstance(test_list, list) is True
        assert len(test_list) == 3

        for i, item in enumerate(test_list):
            assert isinstance(item, dict) is True
            assert item.get("real_filename", "") == targets[i]
            assert item.get("virtual_filename", "") == f"{targets[i][0]}.txt"

    def test_load_list(self, tmp_path):
        test_list = [
            {
                "virtual_filename": "a.txt",
                "real_filename": "alpha.txt",
                "meta": {"extra": "special"},
            },
            {
                "virtual_filename": "b.txt",
                "real_filename": "beta.txt",
                "meta": {"extra": "special", "__private": False},
            },
        ]

        test_unit = ArtefactStore(tmp_path / "work")
        test_unit.load_list(test_list)
        assert len(test_unit) == 2

        for i, artefact in enumerate(test_unit._map.values()):
            assert str(artefact.virtual_filename) == test_list[i]["virtual_filename"]
            assert str(artefact.real_filename) == test_list[i]["real_filename"]
            for key, value in test_list[i]["meta"].items():
                assert artefact.get_meta(key) == None if key.startswith("__") else value


class TestArtefact:
    def test_constructor(self):
        test_unit = Artefact(ArtefactPath("feed/fish"), Path("/var/tmp/cheese"))
        assert test_unit.virtual_filename == ArtefactPath("feed/fish")
        assert test_unit.real_filename == Path("/var/tmp/cheese")

    def test_meta(self, tmp_path: Path):
        test_unit = Artefact(
            ArtefactPath("work/test.f90"),
            tmp_path / "fred.f90",
            extra="special",
        )
        test_unit.set_meta("thing", "one")
        assert test_unit.get_meta("thing") == "one"
        assert test_unit.get_meta("extra") == "special"
        assert test_unit.get_meta("nosuch") is None
        assert test_unit.get_meta("nosuch", "default") == "default"

    def test_read_text(self, tmp_path: Path):
        test_file = tmp_path / "nonsense.text"
        test_file.write_text("This is your brain on text.")
        test_unit = Artefact(ArtefactPath("text.txt"), test_file)
        assert test_unit.read_text() == "This is your brain on text."


class TestArtefactPath:
    @mark.parametrize(
        "path_in",
        [
            "wibble.txt",
            "wibble/wobble.txt",
            Path("wibble.txt"),
            Path("wibble/wobble.txt"),
        ],
    )
    def test_constructor(self, path_in):
        test_unit = ArtefactPath(path_in)
        assert test_unit == Path(path_in)

    @mark.parametrize(
        "path_in",
        [
            "/",
            "/wibble.txt",
            "/wibble/wobble.txt",
            Path("/"),
            Path("/wibble.txt"),
            Path("/wibble/wobble.txt"),
        ],
    )
    def test_constructor_absolute(self, path_in):
        with raises(ValueError):
            _ = ArtefactPath(path_in)

    @mark.parametrize("filename", ["thing", Path("thang")])
    def test_hashing(self, filename: str | Path):
        """
        Ensures different objects representing the same path return the same
        Hash.

        This test was added as it seemed like it might not, but it turns out
        everything was as it should be.
        """
        first_unit = ArtefactPath(filename)
        second_unit = ArtefactPath(filename)
        assert hash(first_unit) == hash(second_unit)
