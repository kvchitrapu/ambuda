Text validation flow
====================

This document describes Ambuda's text validation flow.


Overview
--------

Ambuda measures a text's quality by running various checks against the text and compiling those
checks into a report. The purpose of this report is twofold. For readers, the report gives some
assurance that the text is well-formed. For proofers, the report surfaces various quality defects
that need attention.

Since some checks are potentially slow or resource-intensive, the report runs asynchronously. For
example, one check might analyze the tokens in a text. But if the text is very large, we may
potentially fetch hundreds of thousands of tokens, which degrades performance when run on each
request.


Key files
---------

Backend:
- `ambuda/models/texts.py` -- the TextReport model
- `ambuda/utils/text_validation.py` -- core reporting logic
- `ambuda/tasks/reports.py` -- Celery task for reports

Templates:
- texts/reader.html -- displays report information as a summary item in the About subpanel.
- texts/text-validate.html -- displays a comprehensive report for some text.


Data model
----------

Report results are stored in the database as a TextReport (models/texts.py) with this structure:

- id: integer primary key
- text_id: foreign key to Text.id
- created_at: datetime
- updated_at: datetime
- payload: JSON

`payload` should be parseable as a ValidationReport (utils/text_validation.py), which is a Pydantic
base class. We use `payload` for flexibility so that we can quickly add more validation types.


Data flow
---------

The report runs as a Celery task defined in `ambuda/tasks/reports.py`. The key endpoint is the
`run_report` task.

We start `run_report` asynchronously in these conditions:
- when a text is created as part of the publish flow (proofing/publish.py, `def create`)
- when a text is updated as part of the publish flow (as above).
- when parsing `payload` fails. We use Redis to acquire a lock in the reporting code so that
  multiple attempts to parse `payload` don't trigger multiple reruns.
- when an admin user manually re-runs the report.

The report runs with the code in utils/text_validation.py and saves its data to the database. We
save report data through an upsert. That is, we update an existing TextReport record if present
and create a new record if absent.


Future work
-----------

- Define other conditions in which the report flow should be triggered, such as when updating an
  upstream project

- Provide an option to trigger re-runs across all texts at once, such as when making a major change.
