# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | ✅        |
| 0.1.x   | ❌        |

## Reporting a vulnerability

Please report security issues privately via GitHub
[Security Advisories](https://github.com/tobtok/tgnav-lite/security/advisories/new)
rather than a public issue. You can expect a response within 7 days.

## Scope notes

tgnav-lite produces **static HTML files**. There is no server-side runtime,
no database and no user input handling at generation time beyond the JSON
files you provide. Realistic concerns are therefore limited to:

- HTML/JS injection through data files (mitigated: Jinja autoescape is on
  for all HTML templates, JSON-LD goes through `tojson`, sitemap XML is
  escaped).
- Generated content that links to third-party resources — you are
  responsible for the links you publish (see the README disclaimer).
