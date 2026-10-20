import pandas as pd
import pytest

from surfkit_studio import data_io
from surfkit_studio.catalog import TECHNIQUES


def _spec(tid):
    return TECHNIQUES[tid].dataset


def test_detects_columns_and_units_from_headers():
    df = pd.DataFrame({"Conc (M)": [1e-3, 2e-3, 4e-3, 8e-3, 1.6e-2, 3.2e-2],
                       "Surface tension (dyn/cm)": [60, 55, 50, 45, 40, 40]})
    m = data_io.suggest_mapping(df, _spec("cmc_tensiometry"))["mapping"]
    assert m["conc"] == {"header": "Conc (M)", "unit": "M"}
    assert m["gamma"]["unit"] == "dyn/cm"
    data, notes = data_io.extract(df, _spec("cmc_tensiometry"), m)
    assert data["conc"][0] == pytest.approx(1.0)               # M -> mM
    assert any("converted" in n for n in notes)


def test_semicolon_and_decimal_comma_csv():
    raw = "c (mM);gamma (mN/m)\n0,5;70,1\n1,0;68,0\n2,0;63,2\n4,0;55,0\n8,0;43,1\n16,0;37,0\n".encode()
    df = data_io.read_table("x.csv", raw)
    assert df.iloc[0, 0] == pytest.approx(0.5) and df.iloc[0, 1] == pytest.approx(70.1)


def test_celsius_to_kelvin_and_sorting_and_bad_rows():
    df = pd.DataFrame({"T (C)": [35, 25, "x", 45], "CMC (mM)": [8.4, 8.2, 8.3, 8.9]})
    m = data_io.suggest_mapping(df, _spec("vant_hoff"))["mapping"]
    m["T"]["unit"] = "C"
    data, notes = data_io.extract(df, _spec("vant_hoff"), m)
    assert data["T"] == [298.15, 308.15, 318.15]
    assert any("skipped" in n for n in notes)


def test_rejects_too_few_rows_and_nonpositive_concentration():
    df = pd.DataFrame({"conc": [0, 1, 2, 3, 4, 5], "gamma": [70, 69, 60, 50, 40, 40]})
    m = data_io.suggest_mapping(df, _spec("cmc_tensiometry"))["mapping"]
    with pytest.raises(ValueError):
        data_io.extract(df, _spec("cmc_tensiometry"), m)
    with pytest.raises(ValueError):
        data_io.extract(df.head(3), _spec("cmc_tensiometry"), m)
