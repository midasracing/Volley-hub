"""Proof the actual rendered Rive panel travels like a serve into the O.

This intentionally measures the lime panel rather than assuming keyed values prove
what the exported .riv visibly does. Requires Pillow, supplied by Rive CI.
"""
from pathlib import Path
from PIL import Image

FRAMES = [1, 12, 24, 40, 47, 63, 84]
ROOT = Path(".rive-captures/contact")


def lime_centroid(frame: int) -> tuple[float, float]:
    image = Image.open(ROOT / f"frame-{frame}.png").convert("RGB")
    pixels = [
        (x, y)
        for y in range(min(39, image.height))
        for x in range(image.width)
        if (
            (pixel := image.getpixel((x, y)))[0] > 155
            and pixel[1] > 203
            and pixel[2] < 170
            and pixel[1] > pixel[0] * 1.08
        )
    ]
    assert len(pixels) > 35, f"Missing recognizable volleyball panel in frame {frame}"
    return (
        sum(x for x, _ in pixels) / len(pixels),
        sum(y for _, y in pixels) / len(pixels),
    )


positions = {frame: lime_centroid(frame) for frame in FRAMES}
print("Actual Rive lime panel positions:", positions)

# Horizontal service: visible from right edge, flying left towards the O.
xs = [positions[f][0] for f in [1, 12, 24, 40, 47]]
assert all(a > b + 10 for a, b in zip(xs, xs[1:])), "Serve isn't travelling right-to-left"

# Higher arc followed by descent.
assert positions[24][1] < positions[12][1] - 8, "Missing serve apex"
assert positions[40][1] > positions[24][1] + 7, "Missing descending trajectory"

# Volleyball lands at the exact static O position and completely settles.
assert abs(positions[63][0] - positions[84][0]) < 1, "Ball still moves after settling"
assert abs(positions[63][1] - positions[84][1]) < 1, "Ball still bounces after settling"
assert 32 < positions[84][0] < 43, "Ball did not finish in the letter O"
print("Service path, apex, arrival and hold: VERIFIED")
