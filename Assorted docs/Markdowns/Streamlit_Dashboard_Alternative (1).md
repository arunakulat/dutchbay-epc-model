# 🎯 STREAMLIT DASHBOARD: Alternative UI Layer

**DutchBay EPC - Streamlit Interactive Explorer**

---

## What is Streamlit?

[Streamlit](https://streamlit.io) is a Python framework that turns Python scripts into **interactive web apps with zero JavaScript**.

**Key advantage:** Your backend engineer can build the entire UI without touching HTML/CSS/JavaScript.

```
Traditional Stack:          Streamlit Stack:
┌──────────────────┐       ┌──────────────────┐
│  HTML/CSS/JS     │       │  Python Script   │
│  (Frontend)      │  vs   │  (Streamlit)     │
├──────────────────┤       ├──────────────────┤
│  FastAPI/REST    │       │  (No API needed) │
│  (API Gateway)   │       │                  │
├──────────────────┤       ├──────────────────┤
│  Python Backend  │       │  Python Backend  │
│  (Finance Engine)│       │  (Finance Engine)│
└──────────────────┘       └──────────────────┘
```

---

## Your Existing Streamlit App

You already have `dashboard/streamlit_app.py`:

```python
streamlit run dashboard/streamlit_app.py
```

This gives you:
- ✅ Interactive tornado/spider charts
- ✅ Scenario selector
- ✅ Parameter sensitivity explorer
- ✅ Real-time visualization
- ✅ Zero JavaScript required

**This is a FAST path to MVP!**

---

## Three UI Implementation Pathways (Revised)

### **Pathway 1: FastAPI + Vanilla JS** (What I Recommended)
- **Speed:** 2-3 weeks
- **Complexity:** Medium (HTML, CSS, JS, API)
- **Best for:** Production web apps, multi-user
- **Learning curve:** High for frontend
- **Deployment:** Docker + cloud server
- **Pros:** Professional, scalable, responsive mobile
- **Cons:** Most code to write

### **Pathway 2: FastAPI + React** (Modern, Type-Safe)
- **Speed:** 3-4 weeks
- **Complexity:** High (TypeScript, React, API)
- **Best for:** Long-term products, large teams
- **Learning curve:** Very high
- **Deployment:** Docker + cloud server
- **Pros:** Type-safe, component reuse, huge ecosystem
- **Cons:** Most overhead for MVP

### **Pathway 3: Streamlit** ⭐ **FASTEST TO MVP**
- **Speed:** 2-3 DAYS (not weeks!)
- **Complexity:** Low (Python only)
- **Best for:** MVP, demos, internal tools, data exploration
- **Learning curve:** Minimal (you already know Python)
- **Deployment:** Simple cloud deployment
- **Pros:** Fastest, pure Python, already have code
- **Cons:** Less customizable UI, single-user by default

---

## Why Streamlit is Perfect For You

### ✅ You Already Have 80% of the Code

Your existing `dashboard/streamlit_app.py` shows:
```python
st.title("Sensitivity Dashboard")
st.text_input()  # Scenario selector
st.dataframe()   # Results table
st.image()       # Tornado chart
st.success()     # Success message
```

**This is literally 90 lines to explore sensitivity analysis!**

### ✅ Direct Backend Integration (No API Needed)

```python
# No HTTP requests, no JSON serialization
from analytics.sensitivity_v14 import run as run_sensitivity
from finance.cashflow_v14 import buildannualrows

# Direct Python function calls
result = run_sensitivity(config)
df = buildannualrows(config)

# Display directly in Streamlit
st.dataframe(df)
st.line_chart(df)
```

### ✅ Perfect for Your Use Case

Streamlit excels at:
- 📊 Financial dashboards (exactly your use case)
- 📈 Data visualization (tornado, spider charts already built)
- 🔄 Interactive scenarios (your sensitivity analysis)
- 💼 Internal tools (used by JPMorgan, McKinsey, etc.)
- 🚀 Rapid prototyping (MVP in days)

### ✅ Your Team Can Build It

No JavaScript expertise needed. Just Python.

---

## Streamlit MVP: 2-3 Days

### Day 1: Expand Dashboard

```python
import streamlit as st
import pandas as pd
from analytics.scenario_loader import loadscenario
from analytics.evaluate_scenario import evaluatescenario
from analytics.sensitivity_v14 import run as run_sensitivity

st.set_page_config(page_title="DutchBay EPC", layout="wide")

# ============================================================================
# SIDEBAR: Scenario & Parameter Selector
# ============================================================================

st.sidebar.title("⚙️ Project Configuration")

scenario_name = st.sidebar.selectbox(
    "Scenario",
    ["basecase", "optimisticwind", "conservativewind", "pe_case"],
    index=0
)

# Parameter overrides
with st.sidebar.expander("Parameter Overrides"):
    capex = st.number_input("CAPEX (USD)", value=250e6, step=1e6)
    cf = st.slider("Capacity Factor", 0.0, 1.0, 0.40, step=0.01)
    debt_ratio = st.slider("Debt Ratio", 0.0, 1.0, 0.70, step=0.01)
    tariff = st.number_input("Tariff (LKR/kWh)", value=20.3, step=0.1)

# ============================================================================
# MAIN: Project Metrics
# ============================================================================

st.title("🏗️ DutchBay 150MW Wind Project")
st.markdown(f"**Scenario:** {scenario_name}")

# Load and run scenario
config = loadscenario(f"scenarios/dutchbay_master_config_v14.yaml")

# Apply overrides
config['capex']['usd_total'] = capex
config['project']['capacity_factor'] = cf
config['financing']['debt_ratio'] = debt_ratio
config['revenue']['tariff']['lkr_per_kwh'] = tariff

# Run model
with st.spinner("Calculating..."):
    result = evaluatescenario(config, scenario_name)

# ============================================================================
# METRIC CARDS (Mimics your design system)
# ============================================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "NPV (USD)",
        f"${result['project_npv']/1e6:.1f}M",
        delta=None
    )

with col2:
    st.metric(
        "Project IRR",
        f"{result['project_irr']*100:.1f}%",
        delta=None
    )

with col3:
    st.metric(
        "Min DSCR",
        f"{result['dscr_min']:.2f}x",
        delta=None
    )

with col4:
    st.metric(
        "Equity IRR",
        f"{result['equity_irr']*100:.1f}%",
        delta=None
    )

# ============================================================================
# TIMESERIES CHART
# ============================================================================

st.subheader("📈 Annual Cashflow")

# Create DataFrame for charting
chart_df = pd.DataFrame({
    'Year': result['years'],
    'Revenue (USD)': [x/1e6 for x in result['revenue']],
    'OPEX (USD)': [x/1e6 for x in result['opex']],
    'DSCR': result['dscr']
})

# Two-column layout for charts
col1, col2 = st.columns(2)

with col1:
    st.line_chart(
        chart_df.set_index('Year')[['Revenue (USD)', 'OPEX (USD)']]
    )

with col2:
    st.bar_chart(
        chart_df.set_index('Year')[['DSCR']]
    )

# ============================================================================
# SENSITIVITY ANALYSIS
# ============================================================================

st.subheader("🎯 Sensitivity Analysis")

if st.button("Run Tornado Analysis"):
    with st.spinner("Running sensitivity analysis..."):
        params = [
            {'name': 'capacity_factor', 'base': cf, 'range': 0.05},
            {'name': 'tariff_lkr', 'base': tariff, 'range': 0.10},
            {'name': 'opex_usd', 'base': 3e6, 'range': 0.15},
        ]

        sensitivity_result = run_sensitivity(config, params)

        # Display tornado data
        tornado_df = pd.DataFrame(sensitivity_result['tornado'])
        st.dataframe(tornado_df)

        # Tornado chart (if you have plot function)
        st.info("📊 Tornado chart would display here")

# ============================================================================
# COVENANT MONITORING
# ============================================================================

st.subheader("✅ Covenant Compliance")

covenant_cols = st.columns(3)

with covenant_cols[0]:
    if result['dscr_min'] >= 1.20:
        st.success(f"Min DSCR: {result['dscr_min']:.2f}x ✓")
    else:
        st.error(f"Min DSCR: {result['dscr_min']:.2f}x ✗")

with covenant_cols[1]:
    llcr = result.get('llcr', 0)
    if llcr >= 1.50:
        st.success(f"LLCR: {llcr:.2f}x ✓")
    else:
        st.warning(f"LLCR: {llcr:.2f}x ⚠")

with covenant_cols[2]:
    if debt_ratio <= 0.75:
        st.success(f"Leverage: {debt_ratio:.0%} ✓")
    else:
        st.warning(f"Leverage: {debt_ratio:.0%} ⚠")

# ============================================================================
# EXPORT & DOWNLOADS
# ============================================================================

st.subheader("📥 Reports")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Download Excel"):
        from analytics.export_helpers import toexcel
        file_path = toexcel(result)
        with open(file_path, 'rb') as f:
            st.download_button(
                label="📊 Download Excel Report",
                data=f,
                file_name="dutchbay_analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

with col2:
    if st.button("Download CSV"):
        csv_str = chart_df.to_csv(index=False)
        st.download_button(
            label="📋 Download CSV",
            data=csv_str,
            file_name="dutchbay_timeseries.csv"
        )

with col3:
    st.info("JSON export would be here")

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.markdown(
    """
    <small>
    DutchBay EPC Financial Model v1.0 |
    Last updated: 2025-12-07 |
    [Learn More](https://github.com/dutchbay)
    </small>
    """,
    unsafe_allow_html=True
)
```

### Day 2: Add Monte Carlo & Scenario Comparison

```python
# Add to sidebar
if st.sidebar.checkbox("Advanced Analysis"):

    st.subheader("🎲 Monte Carlo Simulation")
    samples = st.slider("Samples", 100, 10000, 1000, step=100)

    if st.button("Run Monte Carlo"):
        with st.spinner("Running 1000 simulations..."):
            from analytics.monte_carlo_v14 import run as run_mc
            mc_result = run_mc(config, samples=samples)

            st.metric("Mean Equity IRR", f"{mc_result['equity_irr']['mean']*100:.1f}%")
            st.metric("Std Dev", f"{mc_result['equity_irr']['std_dev']*100:.1f}%")
            st.metric("5th Percentile", f"{mc_result['equity_irr']['percentile_5']*100:.1f}%")
            st.metric("95th Percentile", f"{mc_result['equity_irr']['percentile_95']*100:.1f}%")

            # Distribution plot
            st.bar_chart(
                pd.Series(mc_result['equity_irr']['distribution']),
                use_container_width=True
            )

    # Scenario comparison
    st.subheader("📊 Scenario Comparison")
    scenarios_to_compare = st.multiselect(
        "Select scenarios",
        ["basecase", "optimisticwind", "conservativewind", "pe_case"],
        default=["basecase", "optimisticwind"]
    )

    if st.button("Compare"):
        comparison_data = {}
        for scen in scenarios_to_compare:
            config_scen = loadscenario(f"scenarios/dutchbay_{scen}.yaml")
            result_scen = evaluatescenario(config_scen, scen)
            comparison_data[scen] = {
                'NPV': result_scen['project_npv'] / 1e6,
                'IRR': result_scen['project_irr'] * 100,
                'DSCR': result_scen['dscr_min']
            }

        comparison_df = pd.DataFrame(comparison_data).T
        st.dataframe(comparison_df)
        st.bar_chart(comparison_df)
```

### Day 3: Polish & Deploy

- Add caching with `@st.cache_data` for performance
- Add multi-page support with `st.navigation()`
- Configure deployment settings
- Test on Streamlit Cloud

---

## Deployment Options (Streamlit)

### Option A: Streamlit Cloud (Free, 1-minute setup)

```bash
# Push code to GitHub
git push origin main

# Visit: https://streamlit.io/cloud
# Connect GitHub repo
# App is live in 60 seconds!
```

### Option B: Docker (Self-hosted)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0"]
```

```bash
docker build -t dutchbay-streamlit .
docker run -p 8501:8501 dutchbay-streamlit
```

### Option C: AWS/GCP/Azure

Streamlit has native deployment support for all major clouds.

---

## Streamlit vs FastAPI: Decision Matrix

| Factor | Streamlit | FastAPI + JS |
|--------|-----------|---|
| **Speed to MVP** | **2-3 days** ⚡⚡⚡ | 2-3 weeks ⚡ |
| **Code to write** | ~300 lines Python | 1000+ lines (Python + JS) |
| **JavaScript needed?** | **No** | Yes |
| **Production-ready** | Yes, for internal tools | Yes, for web apps |
| **Multi-user support** | Limited (auth optional) | Full (JWT, roles, etc.) |
| **Mobile responsive** | **Automatic** | Manual CSS work |
| **Customizable UI** | Limited (Streamlit widgets) | Unlimited (HTML/CSS) |
| **Team composition** | 1 Python dev | 1 backend + 1 frontend |
| **Deployment** | **1-minute (Cloud)** | 30 minutes (Docker) |
| **Cost** | Free → $150/month | ~$100-500/month |
| **Scalability** | Medium (single-user or small teams) | High (multi-user, enterprise) |

---

## Recommendation for Your Project

### **For MVP/Demo (Right Now)**
**→ Use Streamlit**
- Have working dashboard in 2-3 days
- Perfect for showing stakeholders
- Your backend engineer can build entire UI
- Deploy to Streamlit Cloud for free
- **Zero JavaScript required**

### **For Production (Later)**
**→ Migrate to FastAPI + React**
- Professional web app
- Multi-user support
- Mobile optimized
- Enterprise-grade
- Takes 2-3 weeks after Streamlit works

---

## Your Action Plan (Revised)

### **Week 1: Streamlit MVP**
- **Day 1-2:** Expand existing `dashboard/streamlit_app.py`
- **Day 3:** Add Monte Carlo, comparison, exports
- **Day 4:** Deploy to Streamlit Cloud
- **Day 5:** Show stakeholders, get feedback

### **Week 2-4: Transition (Optional)**
- **If MVP is sufficient:** Stop here, use Streamlit
- **If production needed:** Start FastAPI layer in parallel
- **Gradually migrate:** Streamlit → FastAPI

---

## Code Comparison

### Streamlit (2 days)
```python
st.title("Dashboard")
st.metric("NPV", "$45M")
result = evaluatescenario(config)
st.dataframe(chart_df)
st.download_button("Excel", excel_file)
```

### FastAPI + JS (14 days)
```python
# main.py (FastAPI)
@app.post("/api/v1/projects/{id}/run")
async def run_project(id, request):
    result = evaluatescenario(config)
    return {"data": result}

# dashboard.js (JavaScript)
const response = await fetch('/api/v1/projects/...')
const data = await response.json()
document.querySelector('[data-metric]').textContent = data.npv

<!-- index.html -->
<div data-metric="npv">$45M</div>
<script src="dashboard.js"></script>
```

---

## Next Steps (Revised)

### **Option A: Fast Track (Recommend)**
1. ✅ Expand existing `dashboard/streamlit_app.py`
2. ✅ Deploy to Streamlit Cloud
3. ✅ Show stakeholders in **3 days**
4. ⏸️  Decide if FastAPI needed

### **Option B: Parallel Path**
1. ✅ Start Streamlit MVP (2-3 days)
2. ⏳ Simultaneously start FastAPI (2-3 weeks)
3. 🔄 Build FastAPI while getting Streamlit feedback
4. ✅ Launch FastAPI when ready

### **Option C: Full FastAPI (Original Plan)**
1. Skip Streamlit
2. Build FastAPI + JavaScript (2-3 weeks)
3. No Streamlit dashboard

---

## Files You Need to Modify

```
dashboard/
├── streamlit_app.py          ← EXPAND THIS (currently 50 lines)
│   ├── Add metric cards
│   ├── Add charts
│   ├── Add sensitivity
│   ├── Add exports
│   └── Sidebar controls
├── requirements.txt
└── config.toml               ← Streamlit settings
```

---

## Summary

| Path | Timeline | Code | JavaScript | Best For |
|------|----------|------|---|---|
| **Streamlit** | 2-3 days | ~300 lines Python | ❌ No | MVP, demo, internal tools |
| **FastAPI** | 2-3 weeks | ~1500 lines (Py + JS) | ✅ Yes | Production web app |
| **Both** | 3-4 weeks | ~1800 lines | ✅ Yes | MVP + production |

**My revised recommendation:**
1. **Start with Streamlit** (2-3 days) → Show stakeholders
2. **Then decide** if FastAPI needed (based on feedback)
3. **Migrate if production required** (2-3 weeks)

---

**You already have the Streamlit code. Expand it. Deploy it. Get feedback. Then decide on FastAPI.**

That's the fastest path to a working dashboard. 🚀
