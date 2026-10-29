Decompose monolithic ``finance/debt_v14.py`` into ``finance/debt/*`` with a stable façade.

Public imports (``plan_debt``, ``apply_debt_layer``, ``size_debt_with_dual_dscr``, and related symbols) remain on ``finance.debt_v14``. No intentional algorithm or KPI change; structure only (Dolphin MOVE + façade).
