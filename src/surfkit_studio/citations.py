"""Method references shown to researchers.

Every entry here was checked against an independent bibliographic record
(publisher page or a citing paper's reference list) before being added; the
date and source of that check are kept with the entry. Never add a reference
from memory: an unchecked entry must carry verified=False, and the app does
not show unverified entries.
"""
from __future__ import annotations

REFERENCES: dict[str, dict] = {
    "rosen_kunjappu_2012": {
        "text": "Rosen, M. J.; Kunjappu, J. T. Surfactants and Interfacial Phenomena, 4th ed.; "
                "John Wiley & Sons: Hoboken, NJ, 2012.",
        "doi": "10.1002/9781118228920",
        "verified": True, "checked": "2026-10-20, Wiley Online Books record (ISBN 9780470541944)",
    },
    "zana_1996": {
        "text": "Zana, R. Critical Micellization Concentration of Surfactants in Aqueous Solution and "
                "Free Energy of Micellization. Langmuir 1996, 12, 1208-1211.",
        "doi": "10.1021/la950691q",
        "verified": True, "checked": "2026-10-20, ACS Publications record",
    },
    "szyszkowski_1908": {
        "text": "von Szyszkowski, B. Experimentelle Studien ueber kapillare Eigenschaften der waesserigen "
                "Loesungen von Fettsaeuren. Z. Phys. Chem. 1908, 64, 385-414.",
        "doi": "10.1515/zpch-1908-6425",
        "verified": True, "checked": "2026-10-20, reference lists of Kleinheins et al. 2023 (PMC10132450) and Salma et al. 2006",
    },
    "frumkin_1925": {
        "text": "Frumkin, A. Die Kapillarkurve der hoeheren Fettsaeuren und die Zustandsgleichung der "
                "Oberflaechenschicht. Z. Phys. Chem. 1925, 116, 466.",
        "doi": "10.1515/zpch-1925-11629",
        "verified": True, "checked": "2026-10-20, reference lists of Hansen et al. 2025 (JPCC) and Volkova-Gugeshashvili 2006",
    },
    "clint_1975": {
        "text": "Clint, J. H. Micellization of Mixed Nonionic Surface Active Agents. J. Chem. Soc., Faraday Trans. 1 "
                "1975, 71, 1327-1334.",
        "doi": "10.1039/F19757101327",
        "verified": True, "checked": "2026-10-20, RSC Publishing record",
    },
    "rubingh_1979": {
        "text": "Rubingh, D. N. Mixed Micelle Solutions. In Solution Chemistry of Surfactants; Mittal, K. L., Ed.; "
                "Plenum Press: New York, 1979; Vol. 1, pp 337-354.",
        "doi": "10.1007/978-1-4615-7880-2",
        "verified": True, "checked": "2026-10-20, Springer book record (chapter pages 337-354); DOI is the book's",
    },
    "turro_yekta_1978": {
        "text": "Turro, N. J.; Yekta, A. Luminescent Probes for Detergent Solutions. A Simple Procedure for "
                "Determination of the Mean Aggregation Number of Micelles. J. Am. Chem. Soc. 1978, 100, 5951-5952.",
        "doi": "10.1021/ja00486a062",
        "verified": True, "checked": "2026-10-20, ACS Publications record",
    },
    "israelachvili_1976": {
        "text": "Israelachvili, J. N.; Mitchell, D. J.; Ninham, B. W. Theory of Self-Assembly of Hydrocarbon "
                "Amphiphiles into Micelles and Bilayers. J. Chem. Soc., Faraday Trans. 2 1976, 72, 1525-1568.",
        "doi": "10.1039/F29767201525",
        "verified": True, "checked": "2026-10-20, RSC Publishing record",
    },
    "tanford_1972": {
        "text": "Tanford, C. Micelle Shape and Size. J. Phys. Chem. 1972, 76, 3020-3024.",
        "doi": "10.1021/j100665a018",
        "verified": True, "checked": "2026-10-20, ACS Publications record",
    },
    "griffin_1949": {
        "text": "Griffin, W. C. Classification of Surface-Active Agents by \"HLB\". J. Soc. Cosmet. Chem. 1949, 1, "
                "311-326.",
        "doi": "",
        "verified": True, "checked": "2026-10-20, SCC online library record and citing references",
    },
    "davies_1957": {
        "text": "Davies, J. T. A Quantitative Kinetic Theory of Emulsion Type. I. Physical Chemistry of the "
                "Emulsifying Agent. In Proceedings of the 2nd International Congress of Surface Activity; 1957.",
        "doi": "",
        "verified": True, "checked": "2026-10-20, chapter PDF title and citing references (pages not confirmed, omitted)",
    },
    "guo_2006": {
        "text": "Guo, X.; Rong, Z.; Ying, X. Calculation of Hydrophile-Lipophile Balance for Polyethoxylated "
                "Surfactants by Group Contribution Method. J. Colloid Interface Sci. 2006, 298, 441-450.",
        "doi": "10.1016/j.jcis.2005.12.009",
        "verified": True, "checked": "2026-10-20, PubMed 16414065 and ScienceDirect record",
    },
    "surfactantkit": {
        "text": "Kotian, P. D. SurfactantKit: surfactant and interfacial-science theory as a tested Python "
                "library. Software, 2026.",
        "doi": "",
        "verified": True, "checked": "self",
    },
}


def for_keys(keys: list[str]) -> list[dict]:
    out = []
    for k in keys:
        ref = REFERENCES.get(k)
        if ref and ref["verified"]:
            out.append({"key": k, **ref})
    return out
