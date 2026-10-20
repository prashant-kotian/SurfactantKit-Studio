# SurfactantKit Studio

A local-first analysis app for surfactant datasets. Upload your measurements, choose a method, and get
the result with a plot, a plain-language conclusion, an honest statement of how well the method is
validated, the references to cite, the analyses it unlocks next, and a report you can download as
DOCX or PDF.

**Your data never leaves your computer.** The server listens on `127.0.0.1` only, there is no
telemetry, and every calculation runs in [SurfactantKit](https://github.com/prashant-kotian/Surfactant-Toolkit),
a tested Python library.

## What it does (v0.1)

| Category | Technique | Input | Methods |
|---|---|---|---|
| Micellization | CMC from surface tension | surface tension vs concentration | break-point fit, tangent intersection, steepest slope, sigmoid with 95% CI, Szyszkowski deviation, compare all |
| Micellization | CMC and counterion binding | conductivity vs concentration | two-line break point |
| Adsorption | Surface excess and area per molecule | from the CMC analysis | Gibbs equation |
| Adsorption | Langmuir vs Frumkin adsorption | from the CMC analysis | BIC model selection |
| Thermodynamics | Free energy of micellization | from a CMC (and beta) | nonionic or ionic with counterion binding |
| Thermodynamics | Enthalpy, entropy, heat capacity | CMC at 3+ temperatures | multi-point Gibbs-Helmholtz fit |

Techniques form a tree: primary ones run from raw data, derived ones become available once their inputs
exist in your session (the right-hand panel shows which are ready).

For an ionic surfactant the free energy uses `Delta G_mic = (1 + beta) RT ln X_cmc`, with beta the degree of
counterion binding (Zana, Langmuir 1996, 12, 1208).

## Honesty built in

- **Validation tiers.** Every function used is shown with its SurfactantKit validation tier (T1: reproduces
  published numbers; T2: equation checked, no published worked number; T3: estimate) and the evidence.
- **Method spread.** "Compare all methods" runs every CMC estimator on the same curve, because the CMC
  depends on how it is defined.
- **Data warnings.** Too few points before or after the CMC, a non-flat plateau, or a two-point slope are
  flagged instead of hidden behind an R^2 of 1.
- **Citations** are only shown after being checked against a bibliographic record.
- **No guessing.** An ionic surfactant's free energy is not computed without beta; Gamma_max is not
  computed without the electrolyte condition.

## Install and run

```bash
pip install -e path/to/Surfactant-Toolkit[calc]   # until SurfactantKit is on PyPI
pip install -e .
surfkit-studio                                    # opens http://127.0.0.1:8770
```

Try it with the files in `examples/`: `SDS_surface_tension.csv` is real measured data
(doi:10.5281/zenodo.17232763); the `synthetic_*` files are generated from stated parameters
(see `examples/make_examples.py`) so you can check that the app recovers them.

## Roadmap

1. **Core** (this release): techniques, data import with unit checks, plots, conclusions, tiers,
   citations, DOCX/PDF report, keyword chat.
2. **Local chat model** via [Ollama](https://ollama.com) (small models such as Qwen3 4B): understands free-text
   requests, opens the right panel, explains the principle, asks which method, suggests follow-ups.
   Numbers in chat always come from tool results, never from the model.
3. **More techniques**: mixed micelles (Clint, Rubingh, model selection), aggregation number, packing
   parameter, HLB/HLD, electrostatics, wetting, solubilization, dynamic surface tension, foam.
4. **Optional web search** (off by default): only your search words leave the computer, never your data.

## Development

```bash
pip install -e .[dev]
pytest
```

MIT licensed.
