# Figure-derived content requires a verified transcription evidence plane

Ordinary PDF extraction and human transcription have different provenance and
must not be mixed. Figure-only, callout-only, and text-free pages are retained
as `pdf-text` evidence for inspection, but they remain `transcription-required`
and cannot support procedure answers. OCR or vision output is also ineligible
until a named human reviewer verifies it.

An accepted transcription records the document, physical and printed pages,
section, heading path, page box, contiguous numbered steps with source boxes,
attached warnings, an explicit end boundary, and the reviewer and verification
date. It creates synthetic source spans on a distinct
`verified-transcription` evidence plane. Procedure evidence resolution selects
the plane recorded by the procedure, and verification rejects spans, text,
locators, or boxes from the wrong plane.

This deliberately withholds figure-derived answers until the source can be
checked by a human. Invalid entries marked `human_verified` fail ingestion
closed. Unverified entries remain visible as `unverified_transcriptions` on
their page but never become answerable.
