"""The boundary that keeps pose and media data out of every agent input.

Every specialist's input contract carries the same second line of defence:
whatever a caller assembled, nothing shaped like raw webcam frames, a keypoint
sequence or an encoded blob may cross into an agent. This module is that rule,
written once, so the four contracts cannot disagree about it.

WHY IT IS STRUCTURAL, NOT A SUBSTRING SEARCH
============================================
The rule used to be "if the serialised payload contains the word 'keypoint',
refuse it". That refused a legitimate payload: `assessments/schema.py`
deliberately stores `quality.meanKeypointScore` — a single number summarising
how confident the pose detector was — and the browser sends it with every
session. So a real assessment made the Physio Agent and the Progress Agent
refuse their own input, and no movement plan and no progress review could ever
be produced from a real recording. A rule that refuses the product's own
normal data is not protecting anything.

The distinction `assessments/schema.py` already documents is the one applied
here:

* A **scalar** under a pose-related name is a summary, and summaries are
  wanted. `meanKeypointScore: 0.71` is a measurement of recording quality, not
  pose data.
* A **container** (list or object) under a pose-related name is a sequence,
  and a sequence is exactly what must never cross this boundary.
* A name with no legitimate scalar counterpart at all — video, image, base64,
  dataurl, blob, pixel, snapshot, a raw frame — is refused whatever its value
  is shaped like.
* A data URI, or a long base64-looking string, is refused wherever it appears,
  because that is an encoded payload however it was labelled.

The exemption for projection geometry (`camera_image_plane_projection`,
`downward_vertical_image_plane`) is preserved: those are names for protocol
definitions, not for pictures.

Standard library only, and no I/O: a caller can run this check as a pure
function.
"""

# Names with no legitimate scalar counterpart. A value under one of these is a
# media or encoded payload however it is shaped, so the name alone decides.
MEDIA_KEY_SUBSTRINGS = (
    "video",
    "image",
    "pixel",
    "dataurl",
    "base64",
    "blob",
    "thumbnail",
    "snapshot",
    "rawframe",
    "framedata",
)

# Names that refer to pose data. Allowed to hold a scalar summary; never
# allowed to hold a list or an object.
POSE_KEY_SUBSTRINGS = (
    "keypoint",
    "landmark",
    "skeleton",
    "pose",
    "frame",
)

# Protocol-geometry names that merely contain a media word. These describe
# projection definitions (which plane the camera's image plane maps to), not
# pictures, and refusing them would break the assessment protocol's own
# metadata.
GEOMETRY_KEY_EXCEPTIONS = ("image_plane", "camera_image")

# A string longer than this is not a summary of anything. Generous compared
# with any legitimate field in these payloads (the longest is a reason
# sentence) and far too short to hold an encoded frame.
MAX_SCALAR_STRING_LENGTH = 4096

# A string at least this long drawn only from the base64 alphabet, with the
# usual padding, is an encoded payload rather than prose.
_ENCODED_MIN_LENGTH = 256


def _is_encoded_blob(value: str) -> bool:
    if value.startswith("data:"):
        return True

    if len(value) < _ENCODED_MIN_LENGTH:
        return False

    return all(
        character.isalnum() or character in "+/=\r\n" for character in value
    )


def find_pose_or_media_violation(payload, *, path: str = "") -> str:
    """Return a description of the first pose/media violation in `payload`, or
    an empty string when there is none.

    Returning the reason rather than raising keeps this usable from four
    different contracts that each raise their own error type, and makes it
    directly testable.
    """

    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            lowered = key_text.lower()
            location = f"{path}.{key_text}" if path else key_text

            if not any(exception in lowered for exception in GEOMETRY_KEY_EXCEPTIONS):
                for term in MEDIA_KEY_SUBSTRINGS:
                    if term in lowered:
                        return (
                            f"{location} names media data ({term!r}); a field "
                            "with no scalar meaning is refused outright"
                        )

                if isinstance(value, (list, tuple, dict)):
                    for term in POSE_KEY_SUBSTRINGS:
                        if term in lowered:
                            return (
                                f"{location} is named for pose data ({term!r}) "
                                "and holds a list or object, which is the shape "
                                "a keypoint sequence would have"
                            )

            nested = find_pose_or_media_violation(value, path=location)

            if nested:
                return nested

        return ""

    if isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            nested = find_pose_or_media_violation(value, path=f"{path}[{index}]")

            if nested:
                return nested

        return ""

    if isinstance(payload, str):
        if _is_encoded_blob(payload):
            return (
                f"{path or 'a string value'} looks like an encoded or data-URI "
                "payload"
            )

        if len(payload) > MAX_SCALAR_STRING_LENGTH:
            return (
                f"{path or 'a string value'} is longer than "
                f"{MAX_SCALAR_STRING_LENGTH} characters, which is not a summary "
                "of anything"
            )

    return ""
