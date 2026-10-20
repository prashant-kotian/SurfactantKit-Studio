"""Routing accuracy of the local model vs the keyword router on realistic requests.

Not a unit test (needs a running Ollama). Run:  python tests/eval_router.py [model]
The gate for shipping a model as default: accuracy >= the keyword router's and no
reply ever containing a number (enforced by sanitize, counted here anyway).
"""
import sys
import time

from surfkit_studio import llm, router

CASES = [   # (message, expected technique id or None)
    ("I have surface tension vs concentration data and want the CMC", "cmc_tensiometry"),
    ("what's the critical micelle concentration from my tensiometer readings", "cmc_tensiometry"),
    ("I measured SFT at different concentrations of my gemini surfactant", "cmc_tensiometry"),
    ("how efficient is my surfactant, pC20?", "cmc_tensiometry"),
    ("my du Nouy ring data, where does the plateau start", "cmc_tensiometry"),
    ("which CMC method should I trust, the values differ", "cmc_tensiometry"),
    ("I have conductivity vs concentration for an ionic surfactant", "cmc_conductivity"),
    ("how many counterions are bound to my micelles", "cmc_conductivity"),
    ("conductometric titration of CTAB, find the break", "cmc_conductivity"),
    ("degree of ionization of micelles from specific conductance", "cmc_conductivity"),
    ("area per molecule at the air water interface", "surface_excess"),
    ("maximum surface excess concentration Gamma max", "surface_excess"),
    ("how tightly packed is my surfactant at the interface", "surface_excess"),
    ("is the adsorption Langmuir or Frumkin", "isotherm_selection"),
    ("do adsorbed molecules interact laterally", "isotherm_selection"),
    ("fit an adsorption isotherm to the pre-CMC data", "isotherm_selection"),
    ("free energy of micellization", "gibbs_energy_micellization"),
    ("is micelle formation spontaneous, delta G", "gibbs_energy_micellization"),
    ("Gibbs energy of micelle formation for my ionic surfactant", "gibbs_energy_micellization"),
    ("I have CMC at five temperatures, get enthalpy and entropy", "vant_hoff"),
    ("van't Hoff analysis of micellization", "vant_hoff"),
    ("is micellization entropy driven or enthalpy driven", "vant_hoff"),
    ("heat capacity change of micellization", "vant_hoff"),
    ("CMC measured from 15 to 50 C, thermodynamics", "vant_hoff"),
    ("I measured the CMC of SDS/DTAB mixtures at different mole fractions", "mixed_micelles"),
    ("is there synergism between my two surfactants", "mixed_micelles"),
    ("calculate the Rubingh interaction parameter for my blend", "mixed_micelles"),
    ("pyrene fluorescence quenching data, how many molecules per micelle", "aggregation_quenching"),
    ("I want the aggregation number from my quencher series", "aggregation_quenching"),
    ("static light scattering Debye plot of my micelles", "aggregation_sls"),
    ("micelle molar mass from Rayleigh ratios", "aggregation_sls"),
    ("will my surfactant form spheres, rods or vesicles", "packing_parameter"),
    ("critical packing parameter of a C12 surfactant", "packing_parameter"),
    ("hello", None),
    ("what can this app do", None),
    ("how do I make a cake", None),
    ("translate this to French", None),
]


class _Fixed:
    """Replays one model answer through the real router (no second model call)."""
    def __init__(self, res):
        self.res = res

    def route(self, *a, **k):
        return self.res


def main(model: str = llm.DEFAULT_MODEL):
    m = llm.LocalLLM(model)
    if not m.available():
        sys.exit(f"Ollama model {model} not available")
    stats = {"local-ai": 0, "keyword": 0, "combined": 0}
    digits, t0 = 0, time.time()
    for msg, want in CASES:
        kw = router.keyword_route(msg, {})
        kw_got = kw["action"]["open"] if kw["action"] else None
        res = m.route(msg, {})
        got = res["technique"] if res else "ERROR"
        stats["keyword"] += kw_got == want
        stats["local-ai"] += got == want
        comb = router.route(msg, {}, _Fixed(res))           # what the app actually does with this model answer
        stats["combined"] += (comb["action"]["open"] if comb["action"] else None) == want
        digits += bool(res and any(ch.isdigit() for ch in res["reply"]))
        flag = "" if got == want else "   <-- model"
        flag += "" if kw_got == want else "   <-- keyword"
        print(f"{want or '-':<28} model={got or '-':<28} kw={kw_got or '-':<28}{flag}")
    n = len(CASES)
    print(f"\nmodel {model}: {stats['local-ai']}/{n}   keyword: {stats['keyword']}/{n}   "
          f"COMBINED (as shipped): {stats['combined']}/{n}   "
          f"replies with digits: {digits}   {time.time() - t0:.0f}s total")


if __name__ == "__main__":
    main(*sys.argv[1:])
