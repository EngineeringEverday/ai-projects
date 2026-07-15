# GraphLens (MappingMoney)

[![Frontend](https://img.shields.io/badge/Svelte-Frontend-ff3e00?logo=svelte&logoColor=white)](https://svelte.dev/)
[![Backend](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Pages](https://img.shields.io/badge/GitHub%20Pages-Deployed-222222?logo=githubpages&logoColor=white)](https://aaryesh-ad.github.io/graphlens/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

GraphLens is a project focused on exploring financial relationships in the CMS Open Payments ecosystem using graph analytics and interactive visualizations.

## At A Glance

- Interactive analytics for CMS Open Payments data
- Temporal graph exploration across years and products
- Centrality, community, anomaly, and concentration analysis
- 3D network exploration and dashboard storytelling


## Project Overview

GraphLens studies payment flows between manufacturers and physicians across years, products, and network structures using publicly available CMS Open Payments data.

The project combines:

- Temporal graph construction
- Community and centrality analysis
- Anomaly detection
- Dashboard-driven visual storytelling
- 3D network exploration

## Tech Stack

- Frontend: Svelte, Vite, D3, Deck.gl, Plotly, Three.js
- Backend API: Python, FastAPI, Pydantic, Polars, Uvicorn
- Graph/Analytics: igraph, NetworkX, NumPy, SciPy, scikit-learn, UMAP, PyArrow
- Infra: Docker, GitHub Actions

## Data Source

- CMS Open Payments Data: [https://openpaymentsdata.cms.gov/](https://openpaymentsdata.cms.gov/)
- CMS Open Payments Program: [https://www.cms.gov/openpayments](https://www.cms.gov/openpayments)

## Quick Start

1. Install Python dependencies from `pyproject.toml`.
2. Run the API (for example with Uvicorn against `api.main:app`).
3. In `frontend/`, install Node dependencies and run `npm run dev`.

## Local Deployment (Short)

1. Backend API:

    Install Python deps, then run: `uvicorn api.main:app --reload --port 8000`

2. Frontend:

- `cd frontend`
- `npm install`
- `npm run dev`

## GitHub Pages (Short)

Website is hosted on GitHub Pages at [https://aaryesh-ad.github.io/graphlens/](https://aaryesh-ad.github.io/graphlens/).

The deployment process is automated with GitHub Actions, which builds the frontend and publishes it to Pages on pushes to `main`/`master` when relevant files change.

- Frontend deploy is automated with GitHub Actions via [.github/workflows/deploy-frontend-pages.yml](.github/workflows/deploy-frontend-pages.yml).
- The workflow runs on pushes to `main`/`master` when files in `frontend/**` (or the workflow file) change.

Build uses:

- `VITE_BASE_PATH=/<repo-name>/` for Pages routing
- `VITE_API_BASE_URL` from repository secrets

Output from `frontend/dist` is published to GitHub Pages.

The backend is hosted on Render and is not part of the Pages deployment (separate infrastructure). The frontend calls this API for data.

## License

This project is released under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgements

- CMS Open Payments Program for providing the data and ecosystem to explore financial relationships in healthcare.
- Open-source libraries and tools that made the development of GraphLens possible, including Svelte, D3, FastAPI, igraph, and many others.

---
