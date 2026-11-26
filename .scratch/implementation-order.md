# Implementation order

This is the authoritative order for the remaining work across all active
efforts. Ticket numbers remain stable; use this index rather than renumbering
files.

## Current state

- Completed in `bicycle-mechanics-assistant-v1`: tickets 01 through 21 and 23.
- Won't fix in `bicycle-mechanics-assistant-v1`: ticket 22.
- Pending in `bicycle-mechanics-assistant-v1`: none.
- Completed in `general-pdf-ingestion`: tickets 01 through 12.
- Pending in `general-pdf-ingestion`: none.
- Pending in `multilingual-reviewed-output`: tickets 01 through 06.

## Ordered backlog

| Order | Ticket | Purpose | Readiness |
| ---: | --- | --- | --- |
| 01 | [bicycle-mechanics-assistant-v1/13](bicycle-mechanics-assistant-v1/issues/13-remote-openai-compatible-provider.md) | Finish the partially implemented remote provider selection and contract tests. | Complete |
| 02 | [general-pdf-ingestion/01](general-pdf-ingestion/issues/01-ingestion-pipeline-and-profile-contract.md) | Define the staged ingestion contract and versioned document profiles. | Complete |
| 03 | [general-pdf-ingestion/02](general-pdf-ingestion/issues/02-cross-layout-regression-corpus.md) | Build the cross-layout CLI regression corpus. | Complete |
| 04 | [general-pdf-ingestion/03](general-pdf-ingestion/issues/03-page-and-block-classification.md) | Classify contents, tables, figures, legal text, and body pages. | Complete |
| 05 | [general-pdf-ingestion/04](general-pdf-ingestion/issues/04-layout-aware-spans-and-fonts.md) | Preserve fonts, spans, columns, languages, and reading order. | Complete |
| 06 | [general-pdf-ingestion/05](general-pdf-ingestion/issues/05-heading-and-section-hierarchy.md) | Reconstruct authoritative headings and section paths. | Complete |
| 07 | [general-pdf-ingestion/06](general-pdf-ingestion/issues/06-procedure-candidate-and-step-extraction.md) | Extract only contiguous, action-bearing procedure steps. | Complete |
| 08 | [general-pdf-ingestion/08](general-pdf-ingestion/issues/08-source-span-evidence-and-citations.md) | Bind steps and warnings to exact source spans and citations. | Complete |
| 09 | [general-pdf-ingestion/07](general-pdf-ingestion/issues/07-procedure-boundaries-and-completeness.md) | Approve and implement start/end boundary and completeness rules. | Complete |
| 10 | [general-pdf-ingestion/11](general-pdf-ingestion/issues/11-procedure-action-vocabulary.md) | Add reviewed procedure action aliases without weakening identity filters. | Complete |
| 11 | [general-pdf-ingestion/10](general-pdf-ingestion/issues/10-duplicate-and-continuation-handling.md) | Resolve duplicate steps, repeated headings, and continuation pages. | Complete |
| 12 | [general-pdf-ingestion/09](general-pdf-ingestion/issues/09-figure-ocr-and-transcription-policy.md) | Keep figure-only and OCR-only content ineligible until human verification. | Complete |
| 13 | [general-pdf-ingestion/12](general-pdf-ingestion/issues/12-ingestion-diagnostics-and-rebuild-policy.md) | Add diagnostics, parser provenance, and rebuild consequences. | Complete |
| 14 | [bicycle-mechanics-assistant-v1/19](bicycle-mechanics-assistant-v1/issues/19-language-neutral-intent-routing.md) | Replace English keyword routing with validated semantic routing. | Complete |
| 15 | [bicycle-mechanics-assistant-v1/15](bicycle-mechanics-assistant-v1/issues/15-web-chat-adapter.md) | Add the local web adapter over the canonical application service. | Complete |
| 16 | [bicycle-mechanics-assistant-v1/14](bicycle-mechanics-assistant-v1/issues/14-langsmith-result-mirror.md) | Mirror evaluation results without making LangSmith canonical. | Complete |
| 17 | [bicycle-mechanics-assistant-v1/18](bicycle-mechanics-assistant-v1/issues/18-optional-reviewed-korean-output.md) | Add reviewed Korean output behind a disabled-by-default flag. | Complete |
| 18 | [bicycle-mechanics-assistant-v1/01](bicycle-mechanics-assistant-v1/issues/01-development-environment-bootstrap.md) | Complete clean Debian and Ubuntu development acceptance. | Complete |
| 19 | [bicycle-mechanics-assistant-v1/12](bicycle-mechanics-assistant-v1/issues/12-acceptance-gates-and-performance-report.md) | Run and report the full v1 acceptance gates. | Complete |
| 20 | [bicycle-mechanics-assistant-v1/16](bicycle-mechanics-assistant-v1/issues/16-target-runtime-installer.md) | Install and smoke-test the runtime target, including web chat. | Complete |
| 21 | [bicycle-mechanics-assistant-v1/23](bicycle-mechanics-assistant-v1/issues/23-remote-llm-acceptance-evidence.md) | Produce canonical remote-LLM acceptance and performance evidence. | Complete |
| 22 | [bicycle-mechanics-assistant-v1/17](bicycle-mechanics-assistant-v1/issues/17-operational-acceptance-and-documentation.md) | Complete final operational handoff and documentation. | Complete |
| 23 | [multilingual-reviewed-output/01](multilingual-reviewed-output/issues/01-language-profile-contract-and-korean-migration.md) | Introduce the language-profile contract and migrate Korean artifacts. | Next agent ticket |
| 24 | [multilingual-reviewed-output/02](multilingual-reviewed-output/issues/02-dynamic-question-language-routing.md) | Detect and select arbitrary target languages through semantic routing. | Blocked by order 23 |
| 25 | [multilingual-reviewed-output/03](multilingual-reviewed-output/issues/03-language-neutral-translation-validation.md) | Generalize translation and structural validation for approved profiles. | Blocked by orders 23-24 |
| 26 | [multilingual-reviewed-output/04](multilingual-reviewed-output/issues/04-per-language-review-and-activation.md) | Review and activate language profiles independently. | Blocked by orders 23, 25 |
| 27 | [multilingual-reviewed-output/05](multilingual-reviewed-output/issues/05-language-neutral-cli-and-web-rendering.md) | Render arbitrary reviewed languages in CLI and web adapters. | Blocked by orders 23, 25-26 |
| 28 | [multilingual-reviewed-output/06](multilingual-reviewed-output/issues/06-cross-language-acceptance-and-review-guide.md) | Prove the complete multilingual review and adapter workflow. | Blocked by orders 23-27 |

## Rules

1. Do not start a ticket until every `Blocked by` ticket is complete.
2. The first unblocked multilingual implementation ticket after the operational
   handoff is
   `multilingual-reviewed-output/01`.
3. Provider work (ticket 13) and general PDF ingestion are complete.
4. Human-gated tickets may be reviewed in parallel but must not be marked
   complete without the required review.
5. Completing an ingestion ticket requires CLI-seam regression coverage and,
   when parser/profile behavior changes frozen results, a reviewed re-ingest and
   evaluation rerun.
