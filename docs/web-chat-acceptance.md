# Web chat acceptance

This procedure manually exercises the web adapter against the same canonical
application service used by the CLI. The CLI remains the repository's automated
test seam; this acceptance run must not add a second web-specific answer path or
independent evidence checks.

## Prepare

Build the evidence directory through the normal CLI workflow:

```bash
./.venv/bin/python -m zabm download
./.venv/bin/python -m zabm ingest --data-dir .zabm
```

Start the web chat in a second terminal:

```bash
./.venv/bin/python -m zabm web --data-dir .zabm
```

Open <http://127.0.0.1:8765>. Keep the CLI and web configured with the same
evidence directory and provider options. For a remote provider acceptance run,
pass the same `--provider`, `--provider-url`, `--model`, `--embedding-model`, and
`--provider-configuration` values to both commands.

## Compare canonical outcomes

For each question, first ask it through the CLI:

```bash
./.venv/bin/python -m zabm ask '<question>' --data-dir .zabm --json
```

Then submit the same question in the web chat and expand **Inspect canonical
response envelope**. Compare:

- `response_type` and `status`
- `claims` and `citations`
- `specification`, `compatibility`, or `procedure`
- `failure`, `clarification`, and `conflicts`
- `source_pack_id`

`request_id` and `timestamp` are intentionally request-specific and do not need
to match.

Use this representative set:

| Outcome | Question |
| --- | --- |
| Supported specification | What torque should I use for the RockShox Reverb Standard Remote clamp bolt? |
| Supported compatibility | Is a Reverb Stealth hose barb with barb sleeve compatible with a Reverb Stealth A2 seatpost? |
| Clarification required | What torque should I use for the bolt? |
| Not found | What torque should I use for a Reverb unicorn clamp bolt? |
| Out of scope | What bicycle should I buy for commuting? |

For the supported outcomes, confirm the web page displays the answer, every
claim, and each source's document, printed page, physical page, section, and
retrieval date. Confirm compatibility displays its outcome. For procedures,
confirm every numbered step, warning, and step citation appears.

For clarification, not-found, and out-of-scope outcomes, confirm the page shows
only the canonical message or missing information. It must not render claims,
citations, specification values, compatibility outcomes, or procedure steps.

## Check conflicts

Use a data directory that contains two applicable claims for one question, as
in the repository's conflict fixtures. Ask the question through both adapters.
Confirm both report `conflicting_evidence`, show every candidate claim, excerpt,
and source, and render the same cited precedence reason and citation when a
precedence decision exists. No specification or compatibility answer component
may be shown for an unresolved conflict.

## Check the HTTP boundary

The browser-facing endpoint accepts a JSON object with a non-empty `question`
string and returns the canonical envelope:

```bash
curl -sS http://127.0.0.1:8765/api/ask \
  -H 'Content-Type: application/json' \
  --data '{"question":"What torque should I use for the RockShox Reverb Standard Remote clamp bolt?"}'
```

Malformed JSON, a missing or empty question, an oversized request, and unknown
routes fail at the adapter boundary without invoking the answer service. A
provider or evidence-loading failure returns an HTTP error and must not be
presented as a supported answer.
