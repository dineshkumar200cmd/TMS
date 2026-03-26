"""
Four independent traffic clips — one per approach (North / South / East / West).

Put your own MP4 files in either:
  • project/videos/<side>_road.mp4   (recommended), or
  • project root: north_road.mp4, south_road.mp4, east_road.mp4, west_road.mp4

If a file is missing, the old demo clip for that direction is used instead.

Example layout:
  videos/north_road.mp4
  videos/south_road.mp4
  videos/east_road.mp4
  videos/west_road.mp4
"""
import os
import cv2

ORDER = ["North", "South", "East", "West"]

# Legacy demo files (project root) — used only when your road clip is absent
FALLBACK = {
    "North": "videos/north_road.mp4",
    "South": "videos/south_road.mp4",
    "East": "videos/east_road.mp4",
    "West": "videos/north_road.mp4", # Mirrored in CV processor
}


def _candidate_paths(project_root: str, road: str) -> list:
    side = road.lower()
    name = f"{side}_road.mp4"
    return [
        os.path.join(project_root, "videos", name),
        os.path.join(project_root, name),
        os.path.join(project_root, FALLBACK[road]),
    ]


def open_all_captures(project_root: str):
    """
    Returns (caps dict road -> VideoCapture, sources dict road -> absolute path used).
    """
    caps = {}
    sources = {}
    for road in ORDER:
        cap = None
        chosen = None
        for path in _candidate_paths(project_root, road):
            if not os.path.isfile(path):
                continue
            c = cv2.VideoCapture(path)
            if c.isOpened():
                cap, chosen = c, os.path.abspath(path)
                break
        if cap is None:
            last = os.path.join(project_root, FALLBACK[road])
            cap = cv2.VideoCapture(last)
            chosen = os.path.abspath(last) if cap.isOpened() else None
        caps[road] = cap
        sources[road] = chosen

    # If West and South ended up on the same file, offset West so it is not a duplicate stream
    if (
        caps.get("West")
        and caps["West"].isOpened()
        and sources.get("West")
        and sources.get("South")
        and sources["West"] == sources["South"]
    ):
        caps["West"].set(cv2.CAP_PROP_POS_FRAMES, 500)

    return caps, sources
