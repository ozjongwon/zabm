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

|| Order | Ticket | Purpose | Readiness ||
|| ---: | --- | --- | --- | --- ||
|| 01 | [coding-environment-improvements/01](coding-environment-improvements/issues/01-pre-commit-hooks-setup.md) | Set up pre-commit hooks to automatically run linting and type checking before commits. | ready-for-agent ||
|| 02 | [coding-environment-improvements/02](coding-environment-improvements/issues/02-agents-md-navigation-enhancement.md) | Enhance AGENTS.md with clear navigation pointers to key documentation files and development workflows. | ready-for-agent ||
|| 03 | [coding-environment-improvements/03](coding-environment-improvements/issues/03-test-infrastructure-investigation.md) | Investigate and resolve test timeout issues to ensure reliable test execution. | ready-for-agent ||
|| 04 | [bicycle-mechanics-assistant-v1/13](bicycle-mechanics-assistant-v1/issues/13-remote-openai-compatible-provider.md) | Finish the partially implemented remote provider selection and contract tests. | Complete ||
|| 05 | [general-pdf-ingestion/01](general-pdf-ingestion/issues/01-ingestion-pipeline-and-profile-contract.md) | Define the staged ingestion contract and versioned document profiles. | Complete ||
|| 06 | [general-pdf-ingestion/02](general-pdf-ingestion/issues/02-cross-layout-regression-corpus.md) | Build the cross-layout CLI regression corpus. | Complete ||
|| 07 | [general-pdf-ingestion/03](general-pdf-ingestion/issues/03-page-and-block-classification.md) | Classify contents, tables, figures, legal text, and body pages. | Complete ||
|| 08 | [general-pdf-ingestion/04](general-pdf-ingestion/issues/04-layout-aware-spans-and-fonts.md) | Preserve fonts, spans, columns, languages, and reading order. | Complete ||
|| 09 | [general-pdf-ingestion/05](general-pdf-ingestion/issues/05-heading-and-section-hierarchy.md) | Reconstruct authoritative headings and section paths. | Complete ||
|| 10 | [general-pdf-ingestion/06](general-pdf-ingestion/issues/06-procedure-candidate-and-step-extraction.md) | Extract only contiguous, action-bearing procedure steps. | Complete ||
|| 11 | [general-pdf-ingestion/08](general-pdf-ingestion/issues/08-source-span-evidence-and-citations.md) | Bind steps and warnings to exact source spans and citations. | Complete ||
|| 12 | [general-pdf-ingestion/07](general-pdf-ingestion/issues/07-procedure-boundaries-and-completeness.md) | Approve and implement start/end boundary and completeness rules. | Complete ||
|| 13 | [general-pdf-ingestion/11](general-pdf-ingestion/issues/11-procedure-action-vocabulary.md) | Add reviewed procedure action aliases without weakening identity filters. | Complete ||
|| 14 | [general-pdf-ingestion/10](general-pdf-ingestion/issues/10-duplicate-and-continuation-handling.md) | Resolve duplicate steps, repeated headings, and continuation pages. | Complete ||
|| 15 | [general-pdf-ingestion/09](general-pdf-ingestion/issues/09-figure-ocr-and-transcription-policy.md) | Keep figure-only and OCR-only content ineligible until human verification. | Complete ||
|| 16 | [general-pdf-ingestion/12](general-pdf-ingestion/issues/12-ingestion-diagnostics-and-rebuild-policy.md) | Add diagnostics, parser provenance, and rebuild consequences. | Complete ||
|| 17 | [bicycle-mechanics-assistant-v1/19](bicycle-mechanics-assistant-v1/issues/19-language-neutral-intent-routing.md) | Replace English keyword routing with validated semantic routing. | Complete ||
|| 18 | [bicycle-mechanics-assistant-v1/15](bicycle-mechanics-assistant-v1/issues/15-web-chat-adapter.md) | Add the local web adapter over the canonical application service. | Complete ||
|| 19 | [bicycle-mechanics-assistant-v1/14](bicycle-mechanics-assistant-v1/issues/14-langsmith-result-mirror.md) | Mirror evaluation results without making LangSmith canonical. | Complete ||
|| 20 | [bicycle-mechanics-assistant-v1/18](bicycle-mechanics-assistant-v1/issues/18-optional-reviewed-korean-output.md) | Add reviewed Korean output behind a disabled-by-default flag. | Complete ||
|| 21 | [bicycle-mechanics-assistant-v1/01](bicycle-mechanics-assistant-v1/issues/01-development-environment-bootstrap.md) | Complete clean Debian and Ubuntu development acceptance. | Complete ||
|| 22 | [bicycle-mechanics-assistant-v1/12](bicycle-mechanics-assistant-v1/issues/12-acceptance-gates-and-performance-report.md) | Run and report the full v1 acceptance gates. | Complete ||
|| 23 | [bicycle-mechanics-assistant-v1/16](bicycle-mechanics-assistant-v1/issues/16-target-runtime-installer.md) | Install and smoke-test the runtime target, including web chat. | Complete ||
|| 24 | [bicycle-mechanics-assistant-v1/23](bicycle-mechanics-assistant-v1/issues/23-remote-llm-acceptance-evidence.md) | Produce canonical remote-LLM acceptance and performance evidence. | Complete ||
|| 25 | [bicycle-mechanics-assistant-v1/17](bicycle-mechanics-assistant-v1/issues/17-operational-acceptance-and-documentation.md) | Complete final operational handoff and documentation. | Complete ||
|| 26 | [multilingual-reviewed-output/01](multilingual-reviewed-output/issues/01-language-profile-contract-and-korean-migration.md) | Introduce the language-profile contract and migrate Korean artifacts. | Next agent ticket ||
|| 27 | [multilingual-reviewed-output/02](multilingual-reviewed-output/issues/02-dynamic-question-language-routing.md) | Detect and select arbitrary target languages through semantic routing. | Blocked by order 26 ||
|| 28 | [multilingual-reviewed-output/03](multilingual-reviewed-output/issues/03-language-neutral-translation-validation.md) | Generalize translation and structural validation for approved profiles. | Blocked by orders 26-27 ||
|| 29 | [multilingual-reviewed-output/04](multilingual-reviewed-output/issues/04-per-language-review-and-activation.md) | Review and activate language profiles independently. | Blocked by orders 26, 28 ||
|| 30 | [multilingual-reviewed-output/05](multilingual-reviewed-output/issues/05-language-neutral-cli-and-web-rendering.md) | Render arbitrary reviewed languages in CLI and web adapters. | Blocked by orders 26, 28-29 ||
|| 31 | [multilingual-reviewed-output/06](multilingual-reviewed-output/issues/06-cross-language-acceptance-and-review-guide.md) | Prove the complete multilingual review and adapter workflow. | Blocked by orders 26-29 ||
|| 32 | [coding-environment-improvements/04](coding-environment-improvements/issues/04-test-file-organization-analysis.md) | Analyze test file organization and structure to identify improvement opportunities. | Blocked by order 03 ||
|| 33 | [coding-environment-improvements/05](coding-environment-improvements/issues/05-integration-test-scenarios-definition.md) | Define specific integration test scenarios based on core project workflows. | Blocked by orders 03, 32 ||
|| 34 | [coding-environment-improvements/06](coding-environment-improvements/issues/06-ci-pipeline-setup.md) | Set up continuous integration pipeline for automated quality gates. | Blocked by orders 01, 03 ||
|| 35 | [coding-environment-improvements/07](coding-environment-improvements/issues/07-enhanced-acceptance-testing.md) | Enhance and automate acceptance testing for comprehensive coverage. | Blocked by order 33 ||

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
