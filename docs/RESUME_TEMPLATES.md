# Resume templates

Tailoring produces structured content; templates own presentation. A template must deterministically define fonts, sizes, margins, spacing, headings, bullets, page behavior, and accessible text order. It must not accept arbitrary document markup from model output.

The built-in `classic-ats` template uses a single column and ordinary Word paragraphs. New templates register `(version, DOCX renderer, PDF renderer)` in `materials.TEMPLATES`, implement the same `(path, profile, proposal)` contract, and pass extraction, page-count, required-section, contact, minimum-font, and unsupported-claim validation. Add visual regression output and inspect every rendered page.
