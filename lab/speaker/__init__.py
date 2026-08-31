"""Who is speaking -- a separate question from what was said.

Recognising a voice is not something the STT does, and not something it can be
trained to do: Whisper turns audio into words and throws the speaker away. Voice
identity comes from a different model that maps a few seconds of speech to a
vector (an "embedding"), close for the same person and far apart for different
people. Two voices are compared by the cosine of the angle between their vectors.

That means no training in the usual sense. Enrolling somebody is recording a
handful of phrases and averaging their vectors; recognising them is one
comparison. Adding your mother later costs one recording, not a retrain.
"""

from lab.speaker.identify import SpeakerBook

__all__ = ["SpeakerBook"]
