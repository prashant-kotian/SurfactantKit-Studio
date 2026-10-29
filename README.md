# SurfactantKit Studio

A local-first analysis app for surfactant datasets. Upload your measurements, choose a method, and get
the result with a plot, a plain-language conclusion, an honest statement of how well the method is
validated, the references to cite, the analyses it unlocks next, and a report you can download as
DOCX or PDF.

**Your data never leaves your computer.** The server listens on `127.0.0.1` only, there is no
telemetry, and every calculation runs in [SurfactantKit](https://github.com/prashant-kotian/Surfactant-Toolkit),
a tested Python library.

## What it does (v0.2)

| Category | Technique | Input | Methods |
|---|---|---|---|
| Micellization | CMC from surface tension | surface tension vs concentration | break-point fit, regression intersection, Szyszkowski nonlinear curve, tangent intersection, steepest slope, sigmoid with 95% CI, Szyszkowski deviation, compare all |
| Micellization | CMC and counterion binding | conductivity vs concentration | two-line break point |
| Adsorption | Surface excess and area per molecule | from the CMC analysis | Gibbs equation |
| Adsorption | Langmuir vs Frumkin adsorption | from the CMC analysis | BIC model selection |
| Thermodynamics | Free energy of micellization | from a CMC (and beta) | nonionic or ionic with counterion binding |
| Thermodynamics | Enthalpy, entropy, heat capacity | CMC at 3+ temperatures | multi-point Gibbs-Helmholtz fit |
| Mixtures | Mixed micelles: ideal or interacting? | mixture CMC vs mole fraction | Clint vs Rubingh vs EOMMM by BIC; beta, micellar composition, activity coefficients, excess free energy, synergism criterion |
| Micelle size and shape | Aggregation number | fluorescence quenching series | Turro-Yekta |
| Micelle size and shape | Aggregation number, micelle molar mass, A2 | SLS Rayleigh ratios | Debye plot |
| Micelle size and shape | Packing parameter and shape | from the surface-excess result | Tanford + Israelachvili |
| Formulation | HLB | molecular structure | Griffin, Davies group numbers, Guo-Rong-Ying (CnEm) |
| Formulation | Cc and k (HLD salinity scan) | optimal salinity vs oil EACN | ln S* vs EACN fit |
| Formulation | HLD of a formulation, optimal salinity | Cc, k, salinity, EACN, temperature | ionic (ln S) or nonionic (b S) form; cationic quat presets |
| Wetting and surfaces | Solid surface energy | contact angles of standard probe liquids | Owens-Wendt-Rabel-Kaelble, van Oss-Chaudhury-Good |
| Wetting and surfaces | Work of adhesion, spreading coefficient | surface tension and contact angle | Young-Dupre |
| Electrokinetics | Zeta potential | electrophoretic mobility, ionic strength, radius | Henry (Swan-Furst, Ohshima), Smoluchowski, Hueckel, relaxation-corrected, compare all |
| Solubilization | MSR and micelle-water partition coefficient | solubilized solute vs surfactant concentration | slope above CMC, point-by-point |
| Dynamic surface tension | Adsorption speed (t*, regime, D) | tension vs surface age | Rosen-Hua, diffusion vs kinetic control (BIC), Ward-Tordai fit of D, K, Gamma_max |
| Foam | Foam stability | foam height vs time (Ross-Miles) | Ross-Miles summary; exponential vs logarithmic decay by BIC |
| Foam | Foaminess | steady foam volume and gas flow | Bikerman index |
| Foam | Film elasticity | from the isotherm analysis | Gibbs-Marangoni elasticity (Langmuir or Frumkin) |

Techniques form a tree: primary ones run from raw data, structure and measurement ones from a few typed-in
values, and derived ones become available once their inputs
exist in your session (the right-hand panel shows which are ready).

For an ionic surfactant the free energy uses `Delta G_mic = (1 + beta) RT ln X_cmc`, with beta the degree of
counterion binding (Zana, Langmuir 1996, 12, 1208).

## Workbook mode: a whole binary-mixture study in one Excel file

**Download template** (right-hand panel) gives one workbook: an Info sheet (names, ionic, ionic divalent or nonionic,
temperature, added salt, solvent surface tension, CMC method), a sheet per pure surfactant and per mixture composition (surface tension in
up to three runs per concentration, with mean and SD columns; conductivity optional), and an optional temperature
series. **Upload filled workbook** returns a ZIP with:

- the completed workbook: your data, then **Results** (CMC, gamma_CMC, pC20, Gamma_max, A_min, counterion binding,
  free energies of micellization and adsorption; per composition the Clint ideal CMC, Rubingh X1, beta^M, f1, f2,
  excess free energy; Rosen beta^sigma; Rosen's three synergism tests; temperature thermodynamics);
- **Excel Solver sheets** laid out the way researchers already work (live formulas, Solver model preset, so
  Data > Solver > Solve runs it): Rubingh per composition, Rubingh with one beta for all compositions (the Ogino and
  Abe layout, with beta chosen by the 1/CMC residual), and Rosen per composition;
- a **Comparison** sheet, live, of the Excel Solver values against the toolkit's;
- a **Flags** sheet (step-shaped or too-short isotherms, a CMC with no decline before it, a non-flat plateau,
  large run-to-run SD, unit or calibration problems); a flagged isotherm is kept out of beta^M and beta^sigma;
- every plot as PNG and as an xmgrace (Grace) `.agr` project.

Results are shown to the number of significant figures set on the Info sheet (2 by default); every cell keeps full
precision.

The **CMC method** on Info sets the CMC behind every result, beta and Solver sheet: regression intersection (default;
decline line x plateau line), Szyszkowski nonlinear curve (gamma0 - a ln(1 + bC) fitted below the plateau, x plateau
line) or the older break point. Both the regression-intersection and the Szyszkowski CMC and gamma_CMC are always
listed. **ionic divalent** (a gemini, or a dianion with two counterions) uses Gibbs n = 3 without added salt.

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

## Chat: questions answered from the documentation, no AI model

There is no language model in the Studio and nothing to download for the chat. Two kinds of
message are understood:

- **Your data** ("I have surface tension vs concentration and want the CMC") opens the matching
  analysis.
- **How something is calculated** ("which formula does Rubingh use?", "which non-linear fit is used
  for the CMC?", "what is the principle of the conductivity method?") is answered from the
  knowledge base: section S1 of the SurfactantKit Supporting Information (principle, equations,
  implementation, references for every technique), the Studio's own method descriptions and short
  notes on how the Studio computes things. The answer quotes the text and the formula, with its
  source; formulas are converted from the SI's own LaTeX by the SI build, so they cannot drift
  apart. A question the documentation does not cover gets "not in the documentation", never a
  guess. Evaluation (`tests/kb_eval.py`, 44 researcher questions and 10 off-topic ones): 44/44
  answered with the right formula or topic, 10/10 off-topic questions refused.

## Literature search (optional, off by default)

Tick "Search literature online" and type `search: your keywords` in the chat. Only those keywords
are sent, to [OpenAlex](https://openalex.org) (Crossref if OpenAlex is unavailable); the reply shows
exactly what was sent. Text with more than a few numbers is refused, so pasted data cannot leave
by accident. Results are listed as search hits, not as checked citations. OpenAlex works without a
key on a small shared daily budget; set a free key in `SURFKIT_OPENALEX_KEY` for regular use.

## Install and run

**Windows:** double-click `install_windows.bat` once, then `run_studio.bat` to start (opens http://127.0.0.1:8770).
**macOS / Linux:** `./install.sh` once, then `./run_studio.sh`.

Both need Python 3.10 or newer and create a private environment in `.venv`; nothing is installed
system-wide. SurfactantKit is installed from GitHub; to use a local copy instead, set
`SURFACTANTKIT_SRC=path\to\Surfactant-Toolkit` before running the installer. Options:
`surfkit-studio --port 8771 --no-browser`.

Manual install:

```bash
pip install -e path/to/Surfactant-Toolkit[calc]   # until SurfactantKit is on PyPI
pip install -e .
surfkit-studio                                    # opens http://127.0.0.1:8770
```

Try it with the files in `examples/`: `SDS_surface_tension.csv` is real measured data
(doi:10.5281/zenodo.17232763); the `synthetic_*` files are generated from stated parameters
(see `examples/make_examples.py`) so you can check that the app recovers them.

## Roadmap

1. **Core** (done): techniques, data import with unit checks, plots, conclusions, tiers,
   citations, DOCX/PDF report, keyword chat.
2. **Chat** (done; v0.3 replaced the optional Ollama model): keyword routing to analyses, and
   method/formula questions answered from the documentation (knowledge base), evaluated.
3. **More techniques** (in progress): done: mixed micelles, aggregation number, packing parameter,
   HLB, HLD, wetting and surface energy, zeta potential, solubilization, dynamic surface tension, foam (done).
4. **Optional literature search** (done, off by default): only your search words leave the computer, never your data.
5. **Workbook mode** (done, v0.3): template in, completed workbook with Excel Solver sheets, comparison, flags and
   PNG/.agr plots out. Next: salt-series analysis (Corrin-Harkins) once measured salt series are available.

## Development

```bash
pip install -e .[dev]
pytest
```

MIT licensed.
