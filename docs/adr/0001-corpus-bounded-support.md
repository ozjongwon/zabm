# Support is bounded by a frozen source pack

The assistant supports bicycle-maintenance questions from any manufacturer only when the evidence appears in a bounded source pack. Candidate documents may be rejected through retrieval-only usability checks, but the source pack, evaluation questions, and expected answers are frozen before any answer-accuracy baseline runs. We chose this because unrestricted manufacturer coverage would be untestable, while selecting documents based on answer scores would make the reported gains circular.
