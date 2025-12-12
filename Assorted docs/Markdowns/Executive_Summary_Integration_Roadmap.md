# 📋 Executive Summary: Integration Roadmap

**DutchBay EPC - Design System × Financial Engine Integration**
**Status:** Ready for Implementation
**Date:** December 7, 2025

---

## The Situation

You have **two production-ready pieces** that need to be connected:

### ✅ What You Have

**Frontend (Design System)**
- Complete 6-screen interactive prototype
- Production-ready CSS with design tokens
- All UI components specified & implemented
- Accessibility standards (WCAG AA) built in
- **Status:** 100% ready to deploy

**Backend (Financial Engine)**
- 261 Python files, 2.0 MB codebase
- Multi-currency DCF model (14 years in development)
- All core calculations: NPV, IRR, DSCR, tax, debt, WACC
- Scenario analysis, sensitivity, Monte Carlo
- Covenant monitoring for lenders
- **Status:** Production-tested, 100% ready

### ❌ What's Missing

**The API Bridge**
- FastAPI endpoints to wire frontend ↔ backend
- Request/response data contracts
- Error handling & validation
- Deployment infrastructure

---

## The Ask

**Build the bridge between UI and engine.**

This is essentially building a **REST API layer** that:
1. Accepts requests from the browser (Dashboard, Scenarios, Reports, etc.)
2. Calls Python functions in your backend (cashflow, debt, equity, etc.)
3. Returns JSON responses that populate the UI

**Effort Estimate:** 2-3 weeks for 1 full-stack engineer (or 1 week for a team of 2)

---

## Implementation Pathways (Choose One)

### Pathway 1: FastAPI + Vanilla JavaScript ⭐ RECOMMENDED
- **Speed:** 2-3 weeks
- **Learning curve:** Low (your backend engineers can build this)
- **Hosting:** Any cloud (AWS, GCP, Azure, DigitalOcean)
- **Best for:** Teams that want quick MVP with Python-native solution

**Example:**
```python
@app.post("/api/v1/projects/{id}/run")
async def run_project(id, request):
    config = loadscenario(request.scenario)
    result = evaluatescenario(config)
    return {"status": "success", "data": result}
```

### Pathway 2: React + TypeScript + GraphQL
- **Speed:** 3-4 weeks (includes frontend framework setup)
- **Learning curve:** Medium (requires React knowledge)
- **Best for:** Teams that prefer modern frontend architecture

### Pathway 3: Serverless (AWS Lambda)
- **Speed:** 3-4 weeks (includes AWS infrastructure)
- **Best for:** Teams that want auto-scaling with no ops

---

## The Three Layers

```
┌─────────────────────────────────────────┐
│  FRONTEND: 6 Screens (You Have This)    │ ← Dashboard, Scenarios, Reports, Settings
│  HTML/CSS from DutchBay_Prototype.html  │
├─────────────────────────────────────────┤
│  API GATEWAY: FastAPI (Build This)      │ ← /api/v1/projects, /api/v1/scenarios
│  ~500 lines of Python code              │
├─────────────────────────────────────────┤
│  BACKEND: Financial Engine (You Have)   │ ← cashflow_v14.py, debt_v14.py, irr.py
│  261 Python files, fully tested         │
└─────────────────────────────────────────┘
```

---

## What Each Screen Needs

| Screen | API Endpoint | Backend Function | Est. Dev Time |
|--------|---|---|---|
| **Dashboard** | `POST /projects/{id}/run` | `evaluatescenario()` | 2 days |
| **Scenarios** | `GET /scenarios`, `POST /scenarios` | `scenario_analytics.py` | 2 days |
| **Metrics Detail** | `GET /projects/{id}/metrics` | `core/metrics.py` | 1 day |
| **Sensitivity** | `POST /scenarios/{id}/sensitivity` | `sensitivity_v14.py` | 2 days |
| **Reports** | `POST /projects/{id}/export` | `export_helpers.py` | 1.5 days |
| **Settings** | `PUT /projects/{id}/settings` | Config validation | 1 day |
| **+ Testing & Deployment** | — | — | 3 days |

**Total: ~13 days of dev work = ~2.5 weeks for 1 engineer**

---

## Quick Start (Next 48 Hours)

### Day 1: Foundation

```bash
# 1. Create project directory
mkdir dutchbay-api
cd dutchbay-api

# 2. Copy backend code
cp -r /path/to/DutchBay_EPC_Model/finance .
cp -r /path/to/DutchBay_EPC_Model/analytics .
cp -r /path/to/DutchBay_EPC_Model/scenarios .

# 3. Install dependencies
python -m venv .venv311
source .venv311/bin/activate
pip install fastapi uvicorn pydantic pyyaml numpyfinancial

# 4. Create API skeleton
cat > main.py << 'EOF'
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="DutchBay API", version="1.0.0")

class ProjectRunRequest(BaseModel):
    scenario_name: str = "basecase"

@app.post("/api/v1/projects/{project_id}/run")
async def run_project(project_id: str, request: ProjectRunRequest):
    from analytics.evaluate_scenario import evaluatescenario
    from analytics.scenario_loader import loadscenario

    config = loadscenario("scenarios/dutchbay_master_config_v14.yaml")
    result = evaluatescenario(config, request.scenario_name)

    return {"status": "success", "data": result}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF

# 5. Test it
python main.py
# Visit: http://localhost:8000/docs
```

### Day 2: Wire Frontend

```javascript
// In DutchBay_Prototype.html, add:
<script>
  async function loadDashboard() {
    const response = await fetch('/api/v1/projects/dutchbay-150mw/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({scenario_name: 'basecase'})
    });

    const result = await response.json();

    // Update UI with data
    document.querySelector('[data-metric="npv"]').textContent =
      `$${(result.data.npv / 1e6).toFixed(1)}M`;
  }

  // Load on page load
  document.addEventListener('DOMContentLoaded', loadDashboard);
</script>
```

---

## Decision Matrix: Which Pathway?

| Factor | Pathway 1 (FastAPI+JS) | Pathway 2 (React) | Pathway 3 (Serverless) |
|--------|---|---|---|
| Speed | ⚡ 2-3 weeks | ⚡⚡ 3-4 weeks | ⚡⚡ 3-4 weeks |
| Hosting | Simple | Simple | AWS managed |
| Team size | 1 engineer | 2 engineers | 2 engineers |
| Ops burden | Low | Low | None (AWS) |
| Cost | $50-200/mo | $50-200/mo | $0-100/mo (pay per use) |
| Recommended for | MVP, proof of concept | Long-term product | Scale without ops |

**Recommendation:** Start with **Pathway 1** (FastAPI). If you need React later, migration is ~1 week.

---

## Key Files & Functions Reference

### Must-Know Backend Functions

```python
# 1. Run full model
from analytics.evaluate_scenario import evaluatescenario
result = evaluatescenario(config, scenario_name='basecase')
# Returns: project_irr, equity_irr, dscr_min, annual rows, etc.

# 2. Load scenario config
from analytics.scenario_loader import loadscenario
config = loadscenario("scenarios/dutchbay_master_config_v14.yaml")

# 3. Run sensitivity analysis
from analytics.sensitivity_v14 import run as run_sensitivity
result = run_sensitivity(request)
# Returns: tornado chart data

# 4. Run Monte Carlo
from analytics.monte_carlo_v14 import run as run_monte_carlo
result = run_monte_carlo(config, samples=1000)
# Returns: probability distributions

# 5. Export to Excel
from analytics.export_helpers import toexcel
toexcel(result, output_path="report.xlsx")
```

### Must-Know Frontend Files

```html
<!-- Main entry point -->
DutchBay_Prototype.html

<!-- Styling -->
DutchBay_Design_System.css  <!-- CSS variables, components -->

<!-- Reference -->
DutchBay_Design_System_v1.md  <!-- Component specs -->
Figma_Component_Specs.md      <!-- Layer structure -->
```

---

## Success Metrics (After Implementation)

✅ **Functional**
- [ ] Dashboard loads project metrics in <500ms
- [ ] User can switch scenarios and see updated results
- [ ] Sensitivity analysis completes in <5 seconds
- [ ] Excel export contains all data

✅ **Quality**
- [ ] All 6 screens fully functional
- [ ] No JavaScript console errors
- [ ] API returns proper error messages
- [ ] Mobile responsive (tested on tablet)

✅ **Operational**
- [ ] Deployed to staging environment
- [ ] CI/CD pipeline configured
- [ ] Team can spin up new instance in <5 minutes
- [ ] Monitoring & alerting active

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|---|---|
| Data contract mismatch | Medium | Use Pydantic models + auto-docs |
| Performance bottleneck | Medium | Cache results, profile early |
| Dependency conflicts | Low | Use `.venv311`, pin versions |
| Integration bugs | High | Start with happy path, add edge cases |

---

## Next Actions (Right Now)

1. **Pick a pathway** (recommend Pathway 1)
2. **Assign a lead engineer** (ideally your Python expert)
3. **Clone this repo** and try running the backend standalone
4. **Read the two integration documents:**
   - `UI_Backend_Integration_Strategy.md` (comprehensive guide)
   - `API_Contract_Specifications.md` (exact endpoints & schemas)

5. **Start Day 1 setup** (the 48-hour plan above)

---

## Contact Points if Stuck

- **Backend functions not working?** → Check `finance/` and `analytics/` READMEs
- **YAML config issues?** → See `scenarios/dutchbay_master_config_v14.yaml`
- **Deployment questions?** → See `docs/` folder in codebase
- **Design system questions?** → See `README.md` (design system)

---

## Timeline Estimate

```
Week 1: API Layer (FastAPI endpoints)
  Mon-Tue: Project setup, core endpoints
  Wed-Thu: Additional endpoints, testing
  Fri: Documentation, debugging

Week 2: Frontend Integration
  Mon-Tue: HTML wiring, data binding
  Wed: Dynamic components, forms
  Thu: Reports & exports
  Fri: Testing, optimization

Week 3: Deployment
  Mon-Tue: Docker, CI/CD
  Wed-Thu: Staging deployment
  Fri: Production launch

→ MVP Live: ~15 business days
```

---

## Deliverables You'll Have

After implementation:

1. ✅ **Working web application**
   - 6 interactive screens
   - Real financial calculations
   - Scenario analysis
   - Report generation

2. ✅ **API documentation**
   - Swagger/OpenAPI spec (auto-generated)
   - Example curl requests
   - Data schema documentation

3. ✅ **Deployment infrastructure**
   - Dockerfile
   - Docker Compose (dev)
   - GitHub Actions CI/CD

4. ✅ **Team knowledge**
   - How to add new features
   - How to deploy updates
   - How the system works end-to-end

---

## Questions to Ask Yourself

1. **Team composition?**
   - 1 full-stack engineer → Pathway 1 (FastAPI)
   - 2 engineers (BE + FE) → Pathway 1 or 2
   - Cloud-first team → Pathway 3

2. **Timeline?**
   - Need MVP in 2 weeks → Pathway 1
   - Can wait 4 weeks → Any pathway

3. **Long-term plans?**
   - Will this grow into multi-user SaaS? → Pathway 2 (React) or 3 (Serverless)
   - Just for internal analysis? → Pathway 1 (FastAPI)

4. **Deployment infrastructure?**
   - Already use AWS? → Pathway 3 (Lambda)
   - Prefer simple VPS? → Pathway 1 (Docker on EC2/Heroku/DO)
   - No preference? → Pathway 1 (simple, flexible)

---

## Final Word

Your backend and frontend are **both production-ready**. The integration is straightforward.

You're not building financial models (done ✅).
You're not designing UI (done ✅).
You're wiring them together with an API (straightforward 🔌).

**Estimated effort: 13-15 developer days for a competent Python engineer.**

---

**You're ready. Let's build! 🚀**
