# Bicycle Mechanics Assistant

A system that answers bicycle maintenance questions from a bounded set of loaded manufacturer documents and refuses claims that those documents do not support.

## Answer Contract

**Claim**:
An atomic statement, number, compatibility result, warning, or procedure step that must be supported by evidence.
_Avoid_: assertion, answer fact

**Specification**:
An exact value for one component or fastener attribute, including its unit and any applicability conditions.
_Avoid_: spec, torque value without conditions

**Verified specification**:
A specification that a human has checked against its original manufacturer document and which contains every source-defined applicability condition.

**Service procedure**:
An ordered sequence of actions and attached warnings that completes one maintenance task as defined by a complete source section.
_Avoid_: steps, instructions

**Evidence**:
Source content that directly supports a claim and includes a document citation and a verifiable locator.
_Avoid_: context, result, chunk

**Evidence plane**:
The provenance class that determines which source spans may support a claim. PDF text and human-verified transcriptions are separate planes.
_Avoid_: evidence type, confidence tier

**Citation**:
A stable reference to the document and location containing the evidence.
_Avoid_: source, link

**Verified transcription**:
Human-reviewed text for figure-only or scanned source content, bound to an exact page and source box with a named reviewer and verification date.
_Avoid_: OCR output, inferred caption

**Source pack**:
The bounded, frozen set of manufacturer documents from which the assistant may answer.
_Avoid_: knowledge base, corpus

**Accepted source**:
A first-party technical publication from a bicycle or component manufacturer.
_Avoid_: source page, reference

**Supported answer**:
A successful response whose substantive claims are all supported by evidence.

## Compatibility

**Compatibility rule**:
An explicit manufacturer table or statement that establishes whether two identified components may be used together.

**Compatible**:
The source pack contains an explicit manufacturer rule that supports using the two identified components together.

**Not compatible**:
The source pack contains an explicit manufacturer rule that says the two identified components must not be used together.

**Unknown**:
Relevant evidence exists, but it explicitly leaves the compatibility of the identified components unresolved.
_Avoid_: not found

## Refusal

**Clarification required**:
The request cannot be answered safely because an essential model, component, side, revision, or task remains missing or ambiguous.
_Avoid_: not found

**Not found**:
The source pack contains no adequate or complete evidence for the request, so no substantive answer is given.
_Avoid_: unknown, no result

**Conflicting evidence**:
Two or more applicable pieces of evidence disagree, so no answer is given unless their applicability clearly resolves the disagreement.

**Precedence**:
An explicit, cited source statement about model scope, supersession, revision date, or manufacturer applicability that resolves otherwise conflicting evidence.
_Avoid_: confidence, recency without a citation, matching dimensions

**Out of scope**:
The request is outside bicycle maintenance, so it is declined without attempting an evidence search.
_Avoid_: not found, unsupported
