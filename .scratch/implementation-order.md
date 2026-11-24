# Implementation order

This is the authoritative order for the remaining work across both active
efforts. Ticket numbers remain stable; use this index rather than renumbering
files.

## Current state

- Completed in `bicycle-mechanics-assistant-v1`: tickets 02 through 11.
- Pending in `bicycle-mechanics-assistant-v1`: tickets 01 and 12 through 19.
- Completed in `general-pdf-ingestion`: tickets 01 through 09.
- Pending in `general-pdf-ingestion`: tickets 10 through 12.
- Ticket 13 is partially implemented in the current working tree and should be
  completed and verified before moving to the ingestion refactor.
- Ticket 01 in `bicycle-mechanics-assistant-v1` still requires clean-machine
  acceptance on supported Debian and Ubuntu hosts.

## Ordered backlog

| Order | Ticket | Purpose | Readiness |
| ---: | --- | --- | --- |
| 01 | [bicycle-mechanics-assistant-v1/13](bicycle-mechanics-assistant-v1/issues/13-remote-openai-compatible-provider.md) | Finish the partially implemented remote provider selection and contract tests. | In progress |
| 02 | [general-pdf-ingestion/01](general-pdf-ingestion/issues/01-ingestion-pipeline-and-profile-contract.md) | Define the staged ingestion contract and versioned document profiles. | Ready |
| 03 | [general-pdf-ingestion/02](general-pdf-ingestion/issues/02-cross-layout-regression-corpus.md) | Build the cross-layout CLI regression corpus. | Blocked by order 02 |
| 04 | [general-pdf-ingestion/03](general-pdf-ingestion/issues/03-page-and-block-classification.md) | Classify contents, tables, figures, legal text, and body pages. | Blocked by orders 02-03 |
| 05 | [general-pdf-ingestion/04](general-pdf-ingestion/issues/04-layout-aware-spans-and-fonts.md) | Preserve fonts, spans, columns, languages, and reading order. | Blocked by orders 02-03 |
| 06 | [general-pdf-ingestion/05](general-pdf-ingestion/issues/05-heading-and-section-hierarchy.md) | Reconstruct authoritative headings and section paths. | Blocked by orders 04-05 |
| 07 | [general-pdf-ingestion/06](general-pdf-ingestion/issues/06-procedure-candidate-and-step-extraction.md) | Extract only contiguous, action-bearing procedure steps. | Blocked by orders 04, 06 |
| 08 | [general-pdf-ingestion/08](general-pdf-ingestion/issues/08-source-span-evidence-and-citations.md) | Bind steps and warnings to exact source spans and citations. | Complete |
| 09 | [general-pdf-ingestion/07](general-pdf-ingestion/issues/07-procedure-boundaries-and-completeness.md) | Approve and implement start/end boundary and completeness rules. | Complete |
| 10 | [general-pdf-ingestion/11](general-pdf-ingestion/issues/11-procedure-action-vocabulary.md) | Add reviewed procedure action aliases without weakening identity filters. | Blocked by orders 06-07 |
| 11 | [general-pdf-ingestion/10](general-pdf-ingestion/issues/10-duplicate-and-continuation-handling.md) | Resolve duplicate steps, repeated headings, and continuation pages. | Blocked by orders 07-09 |
| 12 | [general-pdf-ingestion/09](general-pdf-ingestion/issues/09-figure-ocr-and-transcription-policy.md) | Keep figure-only and OCR-only content ineligible until human verification. | Complete |
| 13 | [general-pdf-ingestion/12](general-pdf-ingestion/issues/12-ingestion-diagnostics-and-rebuild-policy.md) | Add diagnostics, parser provenance, and rebuild consequences. | Blocked by orders 02, 04, 07-09 |
| 14 | [bicycle-mechanics-assistant-v1/19](bicycle-mechanics-assistant-v1/issues/19-language-neutral-intent-routing.md) | Replace English keyword routing with validated semantic routing. | Ready |
| 15 | [bicycle-mechanics-assistant-v1/15](bicycle-mechanics-assistant-v1/issues/15-web-chat-adapter.md) | Add the local web adapter over the canonical application service. | Ready |
| 16 | [bicycle-mechanics-assistant-v1/14](bicycle-mechanics-assistant-v1/issues/14-langsmith-result-mirror.md) | Mirror evaluation results without making LangSmith canonical. | Ready |
| 17 | [bicycle-mechanics-assistant-v1/18](bicycle-mechanics-assistant-v1/issues/18-optional-reviewed-korean-output.md) | Add reviewed Korean output behind a disabled-by-default flag. | Blocked by ingestion completion |
| 18 | [bicycle-mechanics-assistant-v1/01](bicycle-mechanics-assistant-v1/issues/01-development-environment-bootstrap.md) | Complete clean Debian and Ubuntu development acceptance. | Human/ops validation |
| 19 | [bicycle-mechanics-assistant-v1/12](bicycle-mechanics-assistant-v1/issues/12-acceptance-gates-and-performance-report.md) | Run and report the full v1 acceptance gates. | Blocked by orders 01, 13 |
| 20 | [bicycle-mechanics-assistant-v1/16](bicycle-mechanics-assistant-v1/issues/16-target-runtime-installer.md) | Install and smoke-test the runtime target, including web chat. | After web adapter |
| 21 | [bicycle-mechanics-assistant-v1/17](bicycle-mechanics-assistant-v1/issues/17-operational-acceptance-and-documentation.md) | Complete final operational handoff and documentation. | Last |

## Rules

1. Do not start a ticket until every `Blocked by` ticket is complete.
2. The first unblocked implementation ticket is
   `bicycle-mechanics-assistant-v1/13`.
3. After ticket 13, proceed with `general-pdf-ingestion/01`.
4. Human-gated tickets may be reviewed in parallel but must not be marked
   complete without the required review.
5. Completing an ingestion ticket requires CLI-seam regression coverage and,
   when parser/profile behavior changes frozen results, a reviewed re-ingest and
   evaluation rerun.
