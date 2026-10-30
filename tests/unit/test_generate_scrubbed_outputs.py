
from pathlib import Path

import pytest

import generate_scrubbed_outputs as generator


def create_fake_data_directory(tmp_path):
    """Create four empty synthetic files with the expected filenames."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    for filename in generator.EXPECTED_FILES:
        (data_dir / filename).write_text(
            "Synthetic test content only.",
            encoding="utf-8",
        )

    return data_dir


class FakeProcessingService:
    """Return safe synthetic results without reading any documents."""

    def __init__(self, data_dir):
        self.data_dir = data_dir

    def process_directory(
        self,
        file_paths,
        max_file_size_bytes=None,
    ):
        processed_files = []

        for path in file_paths:
            processed_files.append(
                {
                    "file_name": path.name,
                    "status": "success",
                    "safe_to_send": True,
                    "scrubbed_output": (
                        f"Safe synthetic output for {path.name}."
                    ),
                    "warnings": [],
                }
            )

        combined_output = "\n\n".join(
            f"=== {item['file_name']} ===\n"
            f"{item['scrubbed_output']}"
            for item in processed_files
        )

        return {
            "status": "success",
            "safe_to_send": True,
            "success_count": len(processed_files),
            "failed_count": 0,
            "processed_files": processed_files,
            "combined_output": combined_output,
        }


@pytest.fixture
def safe_test_environment(tmp_path, monkeypatch):
    data_dir = create_fake_data_directory(tmp_path)
    output_dir = tmp_path / "submission" / "scrubbed_outputs"

    monkeypatch.setattr(generator, "BASE_DIR", tmp_path)
    monkeypatch.setattr(generator, "DATA_DIR", data_dir)
    monkeypatch.setattr(generator, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(
        generator,
        "DocumentProcessingService",
        FakeProcessingService,
    )

    return data_dir, output_dir


def test_safe_synthetic_batch_writes_one_combined_output(
    safe_test_environment,
):
    _, output_dir = safe_test_environment

    generator.main()

    outputs = list(output_dir.glob("*.txt"))

    assert len(outputs) == 1
    assert outputs[0].name == "combined_scrubbed_output.txt"

    combined = outputs[0].read_text(encoding="utf-8")

    for filename in generator.EXPECTED_FILES:
        assert f"---- File: {filename} ----" in combined
def test_unexpected_file_is_rejected_without_writing(
    safe_test_environment,
):
    data_dir, output_dir = safe_test_environment

    (data_dir / "unexpected.txt").write_text(
        "Synthetic extra file.",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="exactly four files"):
        generator.main()

    assert not output_dir.exists()


def test_existing_output_is_never_overwritten(
    safe_test_environment,
):
    _, output_dir = safe_test_environment

    output_dir.mkdir(parents=True)
    existing_file = output_dir / "existing.txt"
    existing_file.write_text("Keep this content.", encoding="utf-8")

    with pytest.raises(SystemExit, match="not empty"):
        generator.main()

    assert existing_file.read_text(encoding="utf-8") == (
        "Keep this content."
    )


def test_pii_in_generated_output_prevents_writing(
    safe_test_environment,
    monkeypatch,
):
    _, output_dir = safe_test_environment

    class PIIProcessingService(FakeProcessingService):
        def process_directory(
            self,
            file_paths,
            max_file_size_bytes=None,
        ):
            result = super().process_directory(
                file_paths,
                max_file_size_bytes,
            )

            result["processed_files"][0]["scrubbed_output"] = (
                "Contact test@example.com"
            )

            result["combined_output"] = "\n\n".join(
                f"=== {item['file_name']} ===\n"
                f"{item['scrubbed_output']}"
                for item in result["processed_files"]
            )

            return result

    monkeypatch.setattr(
        generator,
        "DocumentProcessingService",
        PIIProcessingService,
    )

    with pytest.raises(SystemExit, match="Sensitive information"):
        generator.main()

    assert not output_dir.exists()


def test_failed_batch_prevents_writing(
    safe_test_environment,
    monkeypatch,
):
    _, output_dir = safe_test_environment

    class FailedProcessingService(FakeProcessingService):
        def process_directory(
            self,
            file_paths,
            max_file_size_bytes=None,
        ):
            return {
                "status": "failed",
                "safe_to_send": False,
                "success_count": 0,
                "failed_count": len(file_paths),
                "processed_files": [],
                "combined_output": "",
            }

    monkeypatch.setattr(
        generator,
        "DocumentProcessingService",
        FailedProcessingService,
    )

    with pytest.raises(SystemExit, match="batch"):
        generator.main()

    assert not output_dir.exists()


def test_generator_does_not_call_database_persistence(
    safe_test_environment,
):
    _, output_dir = safe_test_environment

    # The fake service has no persistence method.
    generator.main()

    outputs = list(output_dir.glob("*.txt"))

    assert len(outputs) == 1
    assert outputs[0].name == "combined_scrubbed_output.txt"
def test_symlink_input_is_rejected_when_supported(
    safe_test_environment,
):
    data_dir, output_dir = safe_test_environment

    original = data_dir / generator.EXPECTED_FILES[0]
    link = data_dir / "linked_file.txt"

    try:
        link.symlink_to(original)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not permitted on this system.")

    with pytest.raises(SystemExit, match="exactly four files"):
        generator.main()

    assert not output_dir.exists()
