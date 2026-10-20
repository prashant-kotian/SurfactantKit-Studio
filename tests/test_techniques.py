"""Golden-data and round-trip tests for every technique."""
import csv
import math
import re
from pathlib import Path

import pytest

from surfkit_studio.catalog import TECHNIQUES, tiers, tree
from surfkit_studio.catalog.base import RunInput

EX = Path(__file__).resolve().parents[1] / "examples"
TOOLKIT_TEST = Path(r"H:\CodeProjects\Surfactant-Toolkit\tests\test_curve_analysis.py")


def load(name):
    with open(EX / name) as f:
        rows = list(csv.reader(f))[1:]
    return [[float(v) for v in r] for r in rows]


def sds():
    rows = load("SDS_surface_tension.csv")
    return {"conc": [r[0] for r in rows], "gamma": [r[1] for r in rows]}


IONIC = {"temperature_K": 298.15, "system_type": "ionic_no_added_salt"}


@pytest.mark.skipif(not TOOLKIT_TEST.exists(), reason="toolkit source not on this machine")
def test_sds_example_is_the_real_dataset_verbatim():
    src = TOOLKIT_TEST.read_text()
    c = eval(re.search(r"_SDS_CONCS = (\[.*?\])", src, re.S).group(1))
    g = eval(re.search(r"_SDS_TENSIONS = (\[.*?\])", src, re.S).group(1))
    assert sds() == {"conc": c, "gamma": g}


def test_cmc_break_point_matches_toolkit_validated_sds_value():
    r = TECHNIQUES["cmc_tensiometry"].run(RunInput(sds(), IONIC, "rss", {}))
    assert r.provides["cmc_mM"] == pytest.approx(9.18, abs=0.01)
    assert not any("plateau" in w for w in r.warnings)        # SDS plateau is genuinely flat
    # but its decline has only 2 points between baseline and CMC: must be disclosed, not shown as R^2 = 1
    assert any("only 2 points" in w for w in r.warnings)


def test_conductivity_slopes_match_the_plotted_split():
    rows = load("synthetic_conductivity.csv")
    from surfactantkit.curve_analysis import cmc_from_conductivity_curve
    c, k = [x[0] for x in rows], [x[1] for x in rows]
    r = cmc_from_conductivity_curve(c, k)
    nb = r.n_points_below_cmc
    xs, ys = c[:nb], k[:nb]
    mx, my = sum(xs) / nb, sum(ys) / nb
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    assert b == pytest.approx(r.slope_below_cmc, rel=1e-6)     # the drawn line is the toolkit's fit


def test_every_cmc_method_runs_and_compare_reports_the_spread():
    for m in ("rss", "tangential", "derivative", "sigmoid_bootstrap", "szyszkowski"):
        r = TECHNIQUES["cmc_tensiometry"].run(RunInput(sds(), IONIC, m, {}))
        assert r.provides["cmc_mM"] > 0 and r.figures
    r = TECHNIQUES["cmc_tensiometry"].run(RunInput(sds(), IONIC, "compare", {}))
    spread = next(v for v in r.values if v.label.startswith("Spread"))
    assert spread.value > 1.0 and any("disagree" in w for w in r.warnings)


def test_derived_chain_surface_excess_isotherm_gibbs():
    s = dict(TECHNIQUES["cmc_tensiometry"].run(RunInput(sds(), IONIC, "rss", {})).provides)
    s.update(TECHNIQUES["surface_excess"].run(RunInput(None, IONIC, "gibbs", s)).provides)
    assert s["a_min_nm2"] * 100 == pytest.approx(48.8, abs=0.5)      # plausible SDS area per molecule
    iso = TECHNIQUES["isotherm_selection"].run(RunInput(None, IONIC, "bic", s))
    assert iso.provides["isotherm_model"] in ("langmuir", "frumkin")
    g = TECHNIQUES["gibbs_energy_micellization"].run(
        RunInput(None, {"temperature_K": 298.15, "beta": 0.728}, "pseudo_phase_ionic", s))
    x = s["cmc_mM"] / 1000 / 55.5
    expected = (1 + 0.728) * 8.314462618 * 298.15 * math.log(x / (1 + x)) / 1000  # (1 + beta) convention
    assert g.provides["delta_g_mic_kJ"] == pytest.approx(expected, rel=2e-3)


def test_ionic_free_energy_refuses_without_beta():
    with pytest.raises(ValueError):
        TECHNIQUES["gibbs_energy_micellization"].run(
            RunInput(None, {"temperature_K": 298.15, "beta": None}, "pseudo_phase_ionic", {"cmc_mM": 8.2}))


def test_conductivity_recovers_synthetic_parameters():
    rows = load("synthetic_conductivity.csv")
    r = TECHNIQUES["cmc_conductivity"].run(
        RunInput({"conc": [x[0] for x in rows], "kappa": [x[1] for x in rows]}, {}, "rss", {}))
    assert r.provides["cmc_mM"] == pytest.approx(8.2, rel=0.08)
    assert r.provides["beta"] == pytest.approx(0.70, abs=0.03)


def test_vant_hoff_recovers_synthetic_parameters():
    rows = load("synthetic_cmc_vs_T.csv")
    r = TECHNIQUES["vant_hoff"].run(RunInput({"T": [x[0] + 273.15 for x in rows], "cmc": [x[1] for x in rows]},
                                             {"beta": 0.70}, "gibbs_helmholtz", {}))
    vals = {v.label: v.value for v in r.values}
    ref_T = vals["Reference temperature"]
    # generated with dH(298.15) = -1.0 kJ/mol and dCp = -500 J/(mol K)
    assert vals["Heat capacity change, Delta Cp"] == pytest.approx(-500, rel=0.05)
    assert vals["Enthalpy of micellization, Delta H"] == pytest.approx(-1.0 - 0.5 * (ref_T - 298.15) / 1, abs=0.3)


def test_mixed_micelles_recover_synthetic_rubingh_beta():
    rows = load("synthetic_mixed_cmc.csv")
    r = TECHNIQUES["mixed_micelles"].run(RunInput(
        {"alpha1": [x[0] for x in rows], "cmc_mix": [x[1] for x in rows]},
        {"cmc1_mM": 14.8, "cmc2_mM": 8.0, "temperature_K": 298.15}, "bic", {}))
    assert r.provides["rubingh_beta"] == pytest.approx(-3.0, abs=0.15)      # generated with beta = -3.0
    assert r.provides["mixture_model"] != "clint_ideal"
    assert any("Synergism in mixed micelle formation is expected" in c for c in r.conclusion)  # |-3| > ln(14.8/8)


def test_mixed_micelles_rejects_pure_components_in_series():
    with pytest.raises(ValueError):
        TECHNIQUES["mixed_micelles"].run(RunInput({"alpha1": [0.0, 0.5, 1.0], "cmc_mix": [8, 7, 14.8]},
                                                  {"cmc1_mM": 14.8, "cmc2_mM": 8.0, "temperature_K": 298.15}, "bic", {}))


def test_quenching_recovers_synthetic_aggregation_number():
    rows = load("synthetic_quenching.csv")
    r = TECHNIQUES["aggregation_quenching"].run(RunInput(
        {"q": [x[0] for x in rows], "I": [x[1] for x in rows]},
        {"I0": 1000, "total_surfactant_mM": 20, "cmc_mM": 8}, "turro_yekta", {}))
    assert r.provides["aggregation_number"] == pytest.approx(60, rel=0.03)


def test_sls_recovers_synthetic_aggregation_number():
    rows = load("synthetic_sls.csv")
    r = TECHNIQUES["aggregation_sls"].run(RunInput(
        {"c": [x[0] for x in rows], "R": [x[1] for x in rows]},
        {"dn_dc": 0.12, "wavelength_nm": 632.8, "monomer_mw": 288.38, "n_solvent": 1.333}, "debye", {}))
    assert r.provides["aggregation_number"] == pytest.approx(60, rel=0.05)


def test_packing_parameter_from_sds_area():
    r = TECHNIQUES["packing_parameter"].run(RunInput(None, {"n_carbons": 12}, "israelachvili", {"a_min_nm2": 0.488}))
    assert r.provides["cpp"] == pytest.approx(350.2 / (48.8 * 16.7), rel=0.02)   # Tanford v and lc for C12
    assert any("guide, not a measurement" in c for c in r.conclusion)


def test_hlb_three_methods_and_honest_refusal():
    t = TECHNIQUES["hlb"]
    # Griffin, C12E8 (dodecyl octaethylene glycol ether): EO8 = 8 x 44.05 = 352.4 g/mol of 538.8 total
    g = t.run(RunInput(None, {"mw_hydrophilic": 352.4, "mw_total": 538.8}, "griffin", {}))
    assert g.provides["hlb"] == pytest.approx(20 * 352.4 / 538.8, rel=1e-6)
    assert any("oil-in-water emulsifier" in c for c in g.conclusion)
    d = t.run(RunInput(None, {"groups": "SO4Na: 1, CH2: 11, CH3: 1"}, "davies", {}))    # SDS
    assert d.provides["hlb"] == pytest.approx(40.0, abs=0.5)                           # Davies' classic SDS value
    with pytest.raises(ValueError, match="No verified Davies group number"):
        t.run(RunInput(None, {"groups": "AmidoAmine: 1, CH2: 11"}, "davies", {}))
    e = t.run(RunInput(None, {"n_carbons": 12, "n_eo": 8}, "guo", {}))      # C12E8, HLB ~13 in practice
    assert 11.5 < e.provides["hlb"] < 14.5


def test_tree_is_rooted_in_primary_techniques_and_every_unlock_exists():
    for cat in tree():
        for t in cat["techniques"]:
            for u in t["unlocks"]:
                assert u["id"] in TECHNIQUES
    for t in TECHNIQUES.values():
        assert all(u in TECHNIQUES for u in t.unlocks)
        assert t.level in ("primary", "derived", "structure")
        assert (t.dataset is not None) == (t.level == "primary")
        if t.level == "structure":
            assert not t.requires


def test_every_technique_reports_tiers_and_only_verified_citations():
    from surfkit_studio import citations
    for t in TECHNIQUES.values():
        assert tiers(t)
        for k in t.citations:
            assert k in citations.REFERENCES and citations.REFERENCES[k]["verified"], k
