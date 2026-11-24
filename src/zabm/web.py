from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, cast

from zabm.agent import answer_question
from zabm.providers import ModelProvider, ProviderError

MAX_REQUEST_BYTES = 16 * 1024
MAX_QUESTION_CHARACTERS = 1000


class ZabmHTTPServer(HTTPServer):
    data_dir: Path
    provider: ModelProvider | None

    def __init__(
        self,
        server_address: tuple[str, int],
        data_dir: Path,
        provider: ModelProvider | None,
    ) -> None:
        super().__init__(server_address, WebRequestHandler)
        self.data_dir = data_dir
        self.provider = provider


class WebRequestHandler(BaseHTTPRequestHandler):
    server_version = "zabm-web/0.1"

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._send(HTTPStatus.OK, "text/html; charset=utf-8", WEB_PAGE.encode())
            return
        self._send_json(
            HTTPStatus.NOT_FOUND,
            {"error": "The requested page does not exist."},
        )

    def do_POST(self) -> None:
        if self.path != "/api/ask":
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "The requested endpoint does not exist."},
            )
            return

        content_length_header = self.headers.get("Content-Length")
        if content_length_header is None:
            self._send_json(
                HTTPStatus.LENGTH_REQUIRED,
                {"error": "A Content-Length header is required."},
            )
            return
        try:
            content_length = int(content_length_header)
        except ValueError:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Content-Length must be an integer."},
            )
            return
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": f"The request body must contain 1-{MAX_REQUEST_BYTES} bytes."},
            )
            return

        body = self.rfile.read(content_length)
        try:
            decoded: object = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "The request body must be valid UTF-8 JSON."},
            )
            return
        if not isinstance(decoded, dict):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "The request body must be a JSON object."},
            )
            return

        payload = cast(dict[str, Any], decoded)
        question = payload.get("question")
        if not isinstance(question, str) or not question.strip():
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "question must be a non-empty string."},
            )
            return
        if len(question) > MAX_QUESTION_CHARACTERS:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": (f"question must be at most {MAX_QUESTION_CHARACTERS} characters.")},
            )
            return

        try:
            response = answer_question(
                question.strip(),
                self._zabm_server().data_dir,
                self._zabm_server().provider,
            )
        except (OSError, ProviderError, ValueError) as exc:
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {"error": f"The assistant could not answer the request: {exc}"},
            )
            return

        self._send_json(
            HTTPStatus.OK,
            response.model_dump(mode="json"),
        )

    def _zabm_server(self) -> ZabmHTTPServer:
        return cast(ZabmHTTPServer, self.server)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self._send(status, "application/json; charset=utf-8", body)

    def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if content_type.startswith("text/html"):
            self.send_header(
                "Content-Security-Policy",
                (
                    "default-src 'self'; "
                    "style-src 'unsafe-inline'; "
                    "script-src 'unsafe-inline'; "
                    "connect-src 'self'; "
                    "img-src 'self' data:"
                ),
            )
        self.end_headers()
        self.wfile.write(body)


WEB_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bicycle Mechanics Assistant</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #17201b;
      --muted: #5f6963;
      --line: #d8ded9;
      --paper: #f7f5ef;
      --panel: #ffffff;
      --accent: #156b4a;
      --accent-soft: #e5f2eb;
      --warning: #8b4d08;
      --warning-soft: #fff2df;
      --danger: #8e302a;
      --danger-soft: #fbe9e7;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, #e6eee8 0, transparent 34rem),
        var(--paper);
      color: var(--ink);
      min-height: 100vh;
    }

    main {
      width: min(960px, calc(100% - 2rem));
      margin: 0 auto;
      padding: 3rem 0 5rem;
    }

    header { max-width: 760px; }

    .eyebrow {
      margin: 0 0 .65rem;
      color: var(--accent);
      font-size: .78rem;
      font-weight: 750;
      letter-spacing: .12em;
      text-transform: uppercase;
    }

    h1 {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(2.4rem, 8vw, 4.8rem);
      font-weight: 500;
      letter-spacing: -.045em;
      line-height: .95;
    }

    .intro {
      color: var(--muted);
      font-size: 1.04rem;
      line-height: 1.65;
      margin: 1.15rem 0 2rem;
      max-width: 670px;
    }

    .question-panel,
    .response-panel {
      background: color-mix(in srgb, var(--panel) 94%, transparent);
      border: 1px solid var(--line);
      border-radius: 1.25rem;
      box-shadow: 0 1.4rem 4rem rgba(31, 52, 39, .08);
      padding: clamp(1.1rem, 4vw, 2rem);
    }

    label {
      display: block;
      font-size: .88rem;
      font-weight: 700;
      margin-bottom: .55rem;
    }

    textarea {
      width: 100%;
      min-height: 7.2rem;
      resize: vertical;
      border: 1px solid #bfc8c1;
      border-radius: .8rem;
      background: #fcfcfa;
      color: var(--ink);
      font: inherit;
      line-height: 1.5;
      padding: .9rem 1rem;
    }

    textarea:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(21, 107, 74, .12);
      outline: none;
    }

    .actions {
      align-items: center;
      display: flex;
      gap: 1rem;
      justify-content: space-between;
      margin-top: .85rem;
    }

    .hint {
      color: var(--muted);
      font-size: .8rem;
      line-height: 1.45;
      margin: 0;
    }

    button {
      background: var(--ink);
      border: 0;
      border-radius: 999px;
      color: white;
      cursor: pointer;
      font: inherit;
      font-weight: 700;
      min-width: 8.5rem;
      padding: .72rem 1.2rem;
    }

    button:hover { background: var(--accent); }
    button:disabled { cursor: wait; opacity: .55; }

    #response {
      margin-top: 1.2rem;
    }

    .status-row {
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: .65rem;
      justify-content: space-between;
    }

    .status {
      border-radius: 999px;
      display: inline-block;
      font-size: .78rem;
      font-weight: 800;
      letter-spacing: .06em;
      padding: .3rem .62rem;
      text-transform: uppercase;
    }

    .status-supported {
      background: var(--accent-soft);
      color: var(--accent);
    }

    .status-refused {
      background: var(--danger-soft);
      color: var(--danger);
    }

    .status-clarification {
      background: var(--warning-soft);
      color: var(--warning);
    }

    .status-pending {
      background: #ecefed;
      color: var(--muted);
    }

    .response-id {
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: .72rem;
    }

    h2 {
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(1.55rem, 4vw, 2.25rem);
      font-weight: 500;
      letter-spacing: -.025em;
      line-height: 1.15;
      margin: 1.15rem 0 .45rem;
    }

    h3 {
      font-size: .82rem;
      letter-spacing: .1em;
      margin: 1.8rem 0 .7rem;
      text-transform: uppercase;
    }

    p { line-height: 1.6; }

    .value {
      color: var(--accent);
      font-size: 1.2rem;
      font-weight: 750;
      margin: .35rem 0;
    }

    .message {
      border-left: 3px solid currentColor;
      color: var(--danger);
      font-weight: 650;
      padding: .2rem 0 .2rem 1rem;
    }

    .clarification { color: var(--warning); }

    .conditions,
    .claims,
    .sources,
    .conflicts {
      display: grid;
      gap: .65rem;
    }

    .card {
      background: #fbfcfa;
      border: 1px solid var(--line);
      border-radius: .8rem;
      padding: .8rem .9rem;
    }

    .card strong { display: block; margin-bottom: .3rem; }

    .muted {
      color: var(--muted);
      font-size: .84rem;
      line-height: 1.5;
    }

    .citation-details {
      display: grid;
      gap: .18rem 1.2rem;
      grid-template-columns: max-content 1fr;
      font-size: .86rem;
      line-height: 1.45;
      margin: .55rem 0 0;
    }

    .citation-details dt {
      color: var(--muted);
      font-weight: 650;
    }

    .citation-details dd { margin: 0; }

    ol.steps {
      display: grid;
      gap: .85rem;
      list-style: none;
      margin: 1.15rem 0 0;
      padding: 0;
    }

    ol.steps > li {
      border-top: 1px solid var(--line);
      padding-top: .85rem;
    }

    .step-heading {
      display: flex;
      gap: .7rem;
      line-height: 1.55;
    }

    .step-number {
      align-items: center;
      background: var(--ink);
      border-radius: 999px;
      color: white;
      display: inline-flex;
      flex: 0 0 1.65rem;
      font-size: .75rem;
      font-weight: 750;
      height: 1.65rem;
      justify-content: center;
      margin-top: .1rem;
    }

    .warning {
      background: var(--warning-soft);
      border-radius: .5rem;
      color: var(--warning);
      font-size: .84rem;
      margin: .65rem 0 0 2.35rem;
      padding: .55rem .65rem;
    }

    .conflict-candidate[data-selected="true"] {
      border-color: #88bda5;
    }

    .conflict-state {
      color: var(--muted);
      font-size: .72rem;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
    }

    .precedence {
      background: var(--accent-soft);
      border-color: #aad0bd;
    }

    details {
      border-top: 1px solid var(--line);
      margin-top: 1.8rem;
      padding-top: 1rem;
    }

    summary {
      color: var(--muted);
      cursor: pointer;
      font-size: .86rem;
      font-weight: 700;
    }

    pre {
      background: #17201b;
      border-radius: .8rem;
      color: #e8eee9;
      font-size: .73rem;
      line-height: 1.5;
      margin: 1rem 0 0;
      max-height: 34rem;
      overflow: auto;
      padding: 1rem;
      white-space: pre-wrap;
      word-break: break-word;
    }

    @media (max-width: 620px) {
      main { padding-top: 1.8rem; }
      .actions { align-items: stretch; flex-direction: column; }
      button { width: 100%; }
      .citation-details { grid-template-columns: 1fr; }
      .citation-details dt { margin-top: .35rem; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <p class="eyebrow">Evidence-gated maintenance assistant</p>
      <h1>Ask the manual.</h1>
      <p class="intro">
        Ask a bicycle maintenance question. Answers come from a frozen manufacturer
        source pack, with claims, citations, conflicts, and refusals kept identical
        to the command-line application.
      </p>
    </header>

    <form id="question-form" class="question-panel">
      <label for="question">Maintenance question</label>
      <textarea
        id="question"
        name="question"
        maxlength="1000"
        required
        placeholder="What torque should I use for the RockShox Reverb Standard Remote clamp bolt?"
      ></textarea>
      <div class="actions">
        <p class="hint">Runs locally. The answer cannot bypass evidence or refusal rules.</p>
        <button id="submit" type="submit">Ask assistant</button>
      </div>
    </form>

    <section id="response" class="response-panel" aria-live="polite" hidden>
      <div class="status-row">
        <span id="status" class="status status-pending">Checking</span>
        <span id="request-id" class="response-id"></span>
      </div>
      <div id="answer"></div>
      <details id="raw-details">
        <summary>Inspect canonical response envelope</summary>
        <pre id="raw-response"></pre>
      </details>
    </section>
  </main>

  <script>
    "use strict";

    const form = document.querySelector("#question-form");
    const submitButton = document.querySelector("#submit");
    const responsePanel = document.querySelector("#response");
    const status = document.querySelector("#status");
    const requestId = document.querySelector("#request-id");
    const answer = document.querySelector("#answer");
    const rawDetails = document.querySelector("#raw-details");
    const rawResponse = document.querySelector("#raw-response");

    function element(tag, className, text) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined) node.textContent = text;
      return node;
    }

    function appendParagraphs(container, values) {
      for (const value of values || []) {
        container.append(element("p", "muted", value));
      }
    }

    function citationDetails(citation) {
      const details = element("dl", "citation-details");
      const fields = [
        ["Document", citation.title + " (" + citation.document_id + ")"],
        ["Printed page", citation.printed_page],
        ["Physical page", citation.physical_page],
        ["Section", citation.section],
        ["Retrieved", citation.retrieval_date],
        ["Manufacturer", citation.manufacturer],
      ];
      for (const [label, value] of fields) {
        details.append(element("dt", "", label));
        details.append(element("dd", "", String(value)));
      }
      return details;
    }

    function citationCard(citation, label) {
      const card = element("article", "card");
      card.append(element("strong", "", label || citation.title));
      card.append(citationDetails(citation));
      return card;
    }

    function addSources(container, citations) {
      if (!citations || citations.length === 0) return;
      container.append(element("h3", "", "Sources"));
      const sources = element("div", "sources");
      citations.forEach((citation) => sources.append(citationCard(citation)));
      container.append(sources);
    }

    function addClaims(container, claims) {
      if (!claims || claims.length === 0) return;
      container.append(element("h3", "", "Supported claims"));
      const claimList = element("div", "claims");
      claims.forEach((claim) => {
        const card = element("article", "card");
        card.append(element("p", "", claim.text));
        card.append(
          element("span", "muted", "Evidence: " + claim.evidence_ids.join(", "))
        );
        claimList.append(card);
      });
      container.append(claimList);
    }

    function addListSection(container, title, values) {
      if (!values || values.length === 0) return;
      container.append(element("h3", "", title));
      const conditionList = element("div", "conditions");
      appendParagraphs(conditionList, values);
      container.append(conditionList);
    }

    function addConditions(container, conditions) {
      addListSection(container, "Conditions", conditions);
    }

    function addConflicts(container, conflicts) {
      if (!conflicts) return;
      container.append(
        element(
          "h3",
          "",
          conflicts.precedence_established
            ? "Applicable evidence and cited precedence"
            : "Applicable evidence"
        )
      );
      const conflictList = element("div", "conflicts");
      conflicts.candidates.forEach((candidate) => {
        const card = element("article", "card conflict-candidate");
        card.dataset.selected = String(Boolean(candidate.selected));
        card.append(
          element("div", "conflict-state", candidate.selected ? "Selected" : "Rejected")
        );
        card.append(element("strong", "", candidate.claim));
        appendParagraphs(card, candidate.excerpts);
        const sources = element("div", "sources");
        candidate.citations.forEach((citation) =>
          sources.append(citationCard(citation))
        );
        card.append(sources);
        conflictList.append(card);
      });
      if (conflicts.precedence) {
        const precedence = conflicts.precedence;
        const card = element("article", "card precedence");
        card.append(element("div", "conflict-state", "Precedence · " + precedence.kind));
        card.append(element("strong", "", precedence.reason));
        card.append(element("p", "muted", "Excerpt: " + precedence.excerpt));
        card.append(citationCard(precedence.citation));
        conflictList.append(card);
      }
      container.append(conflictList);
    }

    function renderSupportedResponse(response, container) {
      if (response.response_type === "compatibility") {
        const result = response.compatibility;
        const componentA = result.component_a ? result.component_a.name : "Component A";
        const componentB = result.component_b ? result.component_b.name : "Component B";
        container.append(element("h2", "", componentA + " with " + componentB));
        container.append(element("p", "value", result.outcome));
        addConditions(container, result.conditions);
      } else if (response.response_type === "procedure") {
        const procedure = response.procedure;
        container.append(element("h2", "", procedure.title));
        if (procedure.heading_path.length > 0) {
          appendParagraphs(container, [procedure.heading_path.join(" / ")]);
        }
        const steps = element("ol", "steps");
        procedure.steps.forEach((step) => {
          const item = document.createElement("li");
          const heading = element("div", "step-heading");
          heading.append(element("span", "step-number", String(step.number)));
          heading.append(element("span", "", step.text));
          item.append(heading);
          step.warnings.forEach((warning) => {
            item.append(
              element(
                "p",
                "warning",
                warning.severity.toUpperCase() + ": " + warning.text
              )
            );
          });
          item.append(citationCard(step.citation, "Step source"));
          steps.append(item);
        });
        container.append(steps);
      } else {
        const result = response.specification;
        container.append(
          element(
            "h2",
            "",
            [
              result.manufacturer,
              result.model,
              result.component,
              result.attribute,
            ].join(" ")
          )
        );
        container.append(element("p", "value", result.value.display));
        addConditions(container, result.conditions);
      }

      addClaims(container, response.claims);
      addSources(container, response.citations);
      addConflicts(container, response.conflicts);
    }

    function render(response) {
      answer.replaceChildren();
      requestId.textContent = response.request_id
        ? "Request " + response.request_id
        : "";
      rawResponse.textContent = JSON.stringify(response, null, 2);
      rawDetails.open = false;

      if (response.status === "supported") {
        status.textContent = "Supported answer";
        status.className = "status status-supported";
        renderSupportedResponse(response, answer);
      } else if (response.status === "conflicting_evidence") {
        status.textContent = "Conflicting evidence";
        status.className = "status status-refused";
        answer.append(element("h2", "", "No answer selected"));
        answer.append(element("p", "message", response.failure.message));
        addConflicts(answer, response.conflicts);
      } else if (response.status === "clarification_required") {
        status.textContent = "Clarification required";
        status.className = "status status-clarification";
        answer.append(element("h2", "", "More detail needed"));
        answer.append(element("p", "message clarification", response.clarification.message));
        addListSection(
          answer,
          "Missing information",
          response.clarification.missing_information
        );
      } else {
        status.textContent = response.status === "out_of_scope" ? "Out of scope" : "Not found";
        status.className = "status status-refused";
        answer.append(element("h2", "", "No supported answer"));
        answer.append(element("p", "message", response.failure.message));
      }
      responsePanel.hidden = false;
    }

    function renderRequestError(message) {
      answer.replaceChildren();
      requestId.textContent = "";
      rawResponse.textContent = JSON.stringify({ error: message }, null, 2);
      rawDetails.open = false;
      status.textContent = "Request failed";
      status.className = "status status-refused";
      answer.append(element("h2", "", "The assistant did not answer"));
      answer.append(element("p", "message", message));
      responsePanel.hidden = false;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const question = form.elements.question.value.trim();
      if (!question) return;

      submitButton.disabled = true;
      submitButton.textContent = "Checking evidence…";
      status.textContent = "Checking evidence";
      status.className = "status status-pending";
      requestId.textContent = "";
      responsePanel.hidden = false;

      try {
        const httpResponse = await fetch("/api/ask", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({question}),
        });
        const payload = await httpResponse.json();
        if (!httpResponse.ok) {
          throw new Error(payload.error || "The local web adapter rejected the request.");
        }
        render(payload);
      } catch (error) {
        renderRequestError(error instanceof Error ? error.message : String(error));
      } finally {
        submitButton.disabled = false;
        submitButton.textContent = "Ask assistant";
      }
    });
  </script>
</body>
</html>
"""
