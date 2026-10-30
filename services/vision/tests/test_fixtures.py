"""The labelled test images: present, credited, openly licensed."""

from __future__ import annotations

from pathlib import Path

from vision_service.images import prepare, sniff
from vision_service.model import STATES

FIX = Path(__file__).resolve().parent / "fixtures"
OPEN_LICENCES = {"CC BY 2.0", "CC BY 3.0", "CC BY 4.0", "CC BY-SA 2.0", "CC BY-SA 3.0",
                 "CC BY-SA 4.0", "CC0", "Public domain"}


def test_eight_to_twelve_labelled_images(labels: list[dict]) -> None:
    assert 8 <= len(labels) <= 12
    assert {i["expected"] for i in labels} >= {"waterlogged", "congested", "tree_fall", "clear",
                                               "stalled_vehicle"}
    for item in labels:
        assert item["expected"] in STATES
        data = (FIX / item["file"]).read_bytes()
        assert sniff(data) == "jpeg"
        assert prepare(data).jpeg


def test_every_image_is_credited_and_openly_licensed(labels: list[dict]) -> None:
    notice = (FIX / "NOTICE.md").read_text(encoding="utf-8")
    for item in labels:
        assert item["license"] in OPEN_LICENCES, item["license"]
        assert item["page"].startswith("https://commons.wikimedia.org/wiki/File:")
        assert item["file"] in notice and item["author"] in notice
        assert item["license"] in notice


def test_most_images_are_from_mumbai(labels: list[dict]) -> None:
    local = [i for i in labels if i["caption"].startswith("Mumbai")]
    assert len(local) >= 8
    # and every caption names a road or vehicle scene, never a person as its subject
    for i in labels:
        assert "person" not in i["caption"].lower() and "people" not in i["caption"].lower()
