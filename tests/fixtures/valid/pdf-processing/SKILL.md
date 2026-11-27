---
name: pdf-processing
description: >
  Extract text and tables from PDF files, fill PDF forms, and merge multiple
  PDFs. Use when working with PDF documents, form filling, or document extraction.
license: MIT
compatibility: Requires Python 3.10+ and pypdf
metadata:
  author: example-org
  version: "1.0"
allowed-tools: Read Bash(python:*)
---

# PDF processing

## Workflow

1. Confirm the input files and the requested operation (extract, fill, or merge).
2. Run the extraction script for text and table work:

   ```bash
   python scripts/extract.py "$INPUT_PDF" --out "$OUTPUT_TXT"
   ```

3. For field names and form structure, open [the form reference](references/forms.md).
4. Verify the output exists and is readable before telling the user it succeeded.

## Edge cases

- Encrypted PDFs need a password from the user; do not guess.
- Scanned pages may have no text layer; say so instead of returning an empty string.
