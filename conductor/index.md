# CogGuard Project Context

This directory is the concise, maintained entry point for project context. It
does not replace the repository's normative governance or architecture records.

## Read order

1. [product.md](product.md) for the product purpose and scope.
2. [product-guidelines.md](product-guidelines.md) for product-facing language.
3. [tech-stack.md](tech-stack.md) for runtime and dependency facts.
4. [workflow.md](workflow.md) before changing code.
5. [tracks.md](tracks.md) for active structural work.
6. [code_styleguides/python.md](code_styleguides/python.md) or
   [code_styleguides/typescript.md](code_styleguides/typescript.md) for local conventions.

## Normative sources

- [`../AGENTS.md`](../AGENTS.md): contributor operating rules.
- [`../CONTEXT.md`](../CONTEXT.md): product and system context.
- [`../UBIQUITOUS_LANGUAGE.md`](../UBIQUITOUS_LANGUAGE.md): domain terms.
- [`../doc/engineering/system-governance.md`](../doc/engineering/system-governance.md): package and ownership rules.
- [`../docs/adr/index.md`](../docs/adr/index.md): durable architecture decisions.

When this directory conflicts with a normative source, the normative source
wins and this directory must be corrected in the same change.
