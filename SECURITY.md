# Security policy

Please report suspected vulnerabilities privately, not in a public issue.

## How to report

Use GitHub's private vulnerability reporting: on the repository page, open **Security →
Report a vulnerability**. Include the DataScout version, a minimal example, and what you expected
to happen. Never include API keys.

You can expect an acknowledgement within 5 business days and an assessment within 15 business
days. Fixes are released as a patch version with a CHANGELOG entry and a GitHub security advisory.
Reporters are credited unless they prefer otherwise.

## What counts as a vulnerability

DataScout sends web content to LLMs and acts on what they return, so the main risks are:

- a schema, LLM reply or web page that makes DataScout execute code (extraction schemas are parsed
  with `parse_extraction_schema` and must never be executed);
- API keys leaking into logs, reprs, exceptions, outputs or requests to the wrong service;
- DataScout reading or writing local files beyond its bundled data.

## Known limitations (not vulnerabilities)

- Fetched pages are untrusted. Their text goes into LLM prompts, so a page can try to steer the
  extraction (prompt injection) and produce wrong data points. Grounding checks and quality control
  make such data easier to spot but do not prevent it. Review the collected data.
- Pages are loaded in a headless browser by crawl4ai; browser security is crawl4ai's and
  Playwright's.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | yes |
