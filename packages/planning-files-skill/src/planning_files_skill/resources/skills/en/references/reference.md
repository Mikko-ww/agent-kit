# Reference

Planning Files is a compact adaptation of the file-based planning pattern from `planning-with-files`.

Core ideas:

- Context is volatile; files are persistent.
- Plans should be re-read before important decisions.
- Findings and errors should be written down so the agent does not repeat mistakes.
- External or untrusted content belongs in `findings.md`, not in the auto-read plan.

