"""Short notes on how the Studio itself computes things (Workbook mode, definitions, tiers).
Formulas here are the ones the code uses; tests/test_knowledge.py checks the key ones against it."""

NOTES = [
    {"title": "Rubingh beta^M at each composition (Excel Solver sheet)",
     "text": "For each mixture composition alpha1 with measured mixed CMC, Solver changes x1 until the Rubingh mass "
             "balance F1 - F2 = 0 holds; beta^M then follows from x1. The toolkit solves the same equation "
             "numerically (mixed_micelle.solve_rubingh_x) and the Comparison sheet shows the difference.",
     "equations": ["F1 = x1^2 ln((alpha1 CMC12)/(x1 CMC1)); F2 = (1-x1)^2 ln(((1-alpha1) CMC12)/((1-x1) CMC2))",
                   "beta^M = (ln [alpha1 CMC12/(x1 CMC1)])/((1-x1)^2)"],
     "refs": ["Rubingh 1979"], "technique": "mixed_micelles"},
    {"title": "One beta for all compositions (Ogino and Abe layout, Excel Solver)",
     "text": "For a trial beta, Solver changes x1 at each composition so the predicted bulk composition equals "
             "alpha1; the predicted mixed CMC is C1 + C2. Beta is chosen by the smallest sum of (1/CMC exptl - "
             "1/CMC correl)^2. The composition residual alone is zero for any beta, so it cannot choose beta.",
     "equations": ["f1 = exp(beta(1-x1)^2); f2 = exp(beta x1^2)",
                   "C1 = x1 f1 CMC1; C2 = (1-x1) f2 CMC2; alpha1 predicted = C1/(C1 + C2)",
                   "objective = sum of (1/CMC exptl - 1/(C1 + C2))^2 over compositions"],
     "refs": ["Rubingh 1979", "Holland 1983"], "technique": "mixed_micelles"},
    {"title": "Rosen beta^sigma for the mixed monolayer",
     "text": "beta^sigma uses the same equation as Rubingh's beta^M, but with the concentrations at which the pure "
             "surfactants (C1, C2) and the mixture (C12) reach one chosen surface tension, not the CMCs. The Studio "
             "reads them where each fitted pre-CMC line reaches gamma_solvent - pi_ref (20 mN/m by default).",
     "equations": ["X1^2 ln((alpha1 C12)/(X1 C1)) = (1-X1)^2 ln(((1-alpha1) C12)/((1-X1) C2))",
                   "beta^sigma = (ln [alpha1 C12/(X1 C1)])/((1-X1)^2)"],
     "refs": ["Rosen 2012"], "technique": "mixed_micelles"},
    {"title": "Synergism criteria (Rosen)",
     "text": "Synergism in mixed micelle formation needs beta^M < 0 and |beta^M| > |ln(CMC1/CMC2)|. Synergism in "
             "surface tension reduction efficiency needs beta^sigma < 0 and |beta^sigma| > |ln(C1/C2)| at the "
             "reference tension. Synergism in effectiveness needs beta^sigma - beta^M < 0 and "
             "|beta^sigma - beta^M| > |ln(C1 CMC2/(C2 CMC1))|.",
     "equations": [], "refs": ["Rosen 2012"], "technique": "mixed_micelles"},
    {"title": "Triplicate surface tension: mean and standard deviation",
     "text": "Up to three runs per concentration are averaged; the sample standard deviation is shown when two or "
             "more runs exist and is drawn as error bars. The analysis uses the mean.",
     "equations": ["mean = (gamma1 + gamma2 + gamma3)/n; SD = sqrt(sum of (gamma_i - mean)^2/(n - 1))"],
     "refs": [], "technique": None},
    {"title": "Significant figures in the results",
     "text": "Results are shown to the number of significant figures chosen on the Info sheet (2 by default). Each "
             "cell keeps the full-precision value; only the display is rounded, and inputs are never rounded.",
     "equations": [], "refs": [], "technique": None},
    {"title": "Gibbs prefactor n for the surface excess",
     "text": "n = 1 for a nonionic surfactant and for an ionic surfactant in excess inert electrolyte; n = 2 for a "
             "1:1 ionic surfactant without added salt. The Studio does not guess it: the condition must be stated.",
     "equations": ["Gamma_max = -1/(nRT) (d gamma)/(d ln C)"], "refs": ["Rosen 2012"], "technique": "surface_excess"},
    {"title": "C20, pC20 and CMC/C20",
     "text": "C20 is the concentration that lowers the surface tension by 20 mN/m from the solvent value; pC20 is "
             "its negative logarithm in mol/L and measures efficiency. CMC/C20 compares micellization with "
             "adsorption.",
     "equations": ["pC20 = -log10(C20 / (mol/L))"], "refs": ["Rosen 2012"], "technique": "cmc_tensiometry"},
    {"title": "CMC, degree of ionization and counterion binding from conductivity",
     "text": "Conductivity rises linearly with concentration below and above the CMC with two slopes, b1 (S1) below "
             "and b2 (S2) above; the CMC is where the two fitted lines cross. The slope ratio gives the degree of "
             "ionization; one minus it is the counterion binding.",
     "equations": ["kappa = a1 + b1 C (C<CMC); kappa = a2 + b2 C (C>CMC); CMC = (a2-a1)/(b1-b2)",
                   "alpha = S2/S1 = b2/b1; beta = 1-S2/S1 = 1-b2/b1"], "refs": ["Zana 1996"],
     "technique": "cmc_conductivity"},
    {"title": "Free energy of adsorption",
     "text": "The standard free energy of adsorption follows from the free energy of micellization, the surface "
             "pressure at the CMC and the maximum surface excess.",
     "equations": ["Delta G_ads = Delta G_mic - pi_CMC/Gamma_max; pi_CMC = gamma_solvent - gamma_CMC"],
     "refs": ["Rosen 2012"], "technique": None},
    {"title": "Validation tiers T1, T2 and T3",
     "text": "Every toolkit function carries a tier. T1: it reproduces a published worked number. T2: the equation "
             "is checked but no published worked number exists. T3: an estimate or correlation. The tier is shown "
             "with each result.",
     "equations": [], "refs": [], "technique": None},
    {"title": "Gamma_max from a curved isotherm",
     "text": "The Gibbs slope is taken from a straight line through the pre-CMC decline. When the decline is "
             "curved (Szyszkowski behaviour), that line gives the average slope, so Gamma_max is a lower estimate "
             "and A_min an upper one.",
     "equations": [], "refs": [], "technique": "surface_excess"},
]
