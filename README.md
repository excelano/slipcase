# Slipcase

A container file format that attaches metadata to a file.

A `.slpc` file is a ZIP archive holding a payload file of any type together with a TOML metadata file describing it. The two become one file, so copying, moving, or sending the payload carries its metadata along.

Most files have nowhere to put metadata. Some formats have an embedded slot, but writing to it means modifying the payload, and a great many types have no slot at all. Filenames carry very little. Sidecar files sit beside the payload until someone copies one and not the other. Databases hold metadata well until the file leaves the system, and then the two are separated with nothing to reconnect them.

A container needs no special tooling to make or to read:

```bash
cat > slipcase.metadata.toml <<'TOML'
slipcase_version = "1.0"

[payload]
file = "report.pdf"
TOML

zip report.pdf.slpc slipcase.metadata.toml report.pdf
```

That is a conformant container. `unzip` gets it back.

## This repository

`SPEC.md` is the specification. `DESIGN.md` records the design and the reasoning behind each rule.

<https://slipcaseformat.org> presents both as web pages, alongside the implementations that exist. The site is generated from this repository and this repository stays the authority: where the two differ, these files are right and the site is stale.

To the extent possible under law, Excelano LLC has waived all copyright and related or neighboring rights to Slipcase, dedicating it to the public domain under [CC0 1.0](LICENSE). Anyone can implement it — or quote, fork, or embed the text — without obligation to this project.
