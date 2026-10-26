# Verificări

## Fișiere de intrare (SHA-256)

- registru_2025.xlsx: e036f04e49b118e2da870112f5bde9e197f8cb3867d52f205cda617840318dc3
- registru_2024.xlsx: 7d522ac3864f4fb42412645c933f185cd0a77f58dcfb8a67f85c44c6ce618af4
- situatii_financiare_2025_extras.pdf: da54da1ca135a6a53b294ee913570f4cdf752c139989810f7cda91bdea06e619
- proces_verbal_AGA_2025-04-24.txt: 0adba254d8aa89297b99e203f01185335a65102582ecb0156dcb2e2397212f3c
- nota_functia_actuariala_2026-02-02.docx: 6a64488d1d5af60869574e3d2feaef6538506c68952ff37403975b18ffb39ee0
- proces_verbal_CA_2025-02-18_scanat.pdf: 6c15f38a3e3df670c8c3a95b5400a114d0167f137344a581ca1d134d2d986ba7

## Foi ascunse (nu au fost citite)

- registru_2025.xlsx: Capital_vechi (hidden)

## Verificări între cifre

- scr: coloana „an anterior” = registrul anului trecut: ok
- solvency_ratio: identică cu 2024: CONFLICT
- positive: scr: ok
- positive: mcr: nu s-a putut verifica
- sum: own_funds_total, own_funds_t1, own_funds_t2, own_funds_t3: ok
- sum: scr_basic, scr_underwriting, scr_market, scr_counterparty, scr_diversification: ok
- sum: scr_in_modules, scr_basic, scr_operational: ok
- equal: scr, scr_in_modules: ok
- ratio: own_funds_total, scr, solvency_ratio: CONFLICT
- less: mcr, scr: nu s-a putut verifica
- equal: dividends_paid, dividends_approved: ok

## Goluri în draft (de completat înainte de publicare)

- E, E1_legal_basis: afirmația „fondurile proprii sunt clasificate conform Regulamentului delegat (UE) 2015/35 și Legii nr. 237/2015, aplicabile Societății începând cu 1 ianuarie 2016” nu a fost confirmată de un om (config/facts.toml)
- E, E2_ratio: pentru „Rata de solvabilitate” sursele sau verificările nu se potrivesc (187,4 % în registru_2025.xlsx, foaia Capital, celula C12; 197,4 % în calcul: „Fonduri proprii eligibile SCR, total” / „SCR”); este nevoie de o decizie în config/decisions.toml
- E, E2_mcr: valoarea pentru „MCR” lipsește în registru_2025.xlsx, foaia Capital; nota din rând: „în lucru, actuariat”; calculul MCR nu este finalizat, conform notei funcției actuariale din 2 februarie 2026 (nota_functia_actuariala_2026-02-02.docx)

## Conflicte (așteaptă o decizie în config/decisions.toml)

- solvency_ratio („Rata de solvabilitate”): `1.874` din registru_2025.xlsx, foaia Capital, celula C12; `1.974273879561612011572754552` din calcul: „Fonduri proprii eligibile SCR, total” / „SCR”

## Decizii

- niciuna

## Fapte din documente

- scr_cause_market (nota_functia_actuariala_2026-02-02.docx, pagina 1; confirmat de: Teodor-Vasile Constantin 2026-10-26): folosit
- market_risk_down (nota_functia_actuariala_2026-02-02.docx, pagina 1; confirmat de: Teodor-Vasile Constantin 2026-10-26): folosit
- dividends_paid_fs (situatii_financiare_2025_extras.pdf, pagina 1; confirmat de: Teodor-Vasile Constantin 2026-10-26): folosit
- dividends_approved_aga (proces_verbal_AGA_2025-04-24.txt, pagina 1; confirmat de: Teodor-Vasile Constantin 2026-10-26): folosit
- dividend_policy (proces_verbal_AGA_2025-04-24.txt, pagina 1; confirmat de: Teodor-Vasile Constantin 2026-10-26): folosit
- mcr_in_progress (nota_functia_actuariala_2026-02-02.docx, pagina 1; confirmat de: Teodor-Vasile Constantin 2026-10-26): folosit
- standard_formula (nota_functia_actuariala_2026-02-02.docx, pagina 1; confirmat de: Teodor-Vasile Constantin 2026-10-26): folosit
- legal_basis (fără document; confirmat de: - ): afirmația „fondurile proprii sunt clasificate conform Regulamentului delegat (UE) 2015/35 și Legii nr. 237/2015, aplicabile Societății începând cu 1 ianuarie 2016” nu a fost confirmată de un om (config/facts.toml)
- mcr_covered (fără document; confirmat de: - ): afirmația „MCR a fost acoperită integral la 31 decembrie 2025” nu a fost confirmată de un om (config/facts.toml)

## Aprobarea textului

- E: aprobat de Teodor-Vasile Constantin la 2026-10-26 (sha256 1e25920db2418116d82ef8a3f99219be58debca32a19d521ba46f39d2dbb5533)
