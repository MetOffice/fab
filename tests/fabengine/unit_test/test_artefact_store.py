from pathlib import Path

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
