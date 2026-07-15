<script>
  const teamMembers = [
    "Aaryesh Deshpande",
    "Birendra Kumar Saye",
    "Gabriel Appiah",
    "Prabhjot Singh Ahluwalia",
    "Sanjana Suresh"
  ];

  const techSections = [
    {
      label: "Frontend",
      items: [
        {
          name: "Svelte",
          logo: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/svelte/svelte-original.svg",
          url: "https://svelte.dev/"
        },
        {
          name: "Vite",
          logo: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/vitejs/vitejs-original.svg",
          url: "https://vite.dev/"
        },
        {
          name: "Tailwind CSS",
          logo: "https://cdn.simpleicons.org/tailwindcss/06B6D4",
          url: "https://tailwindcss.com/"
        },
        {
          name: "Deck.gl",
          logo: "https://deck.gl/images/icon-layers.svg",
          url: "https://deck.gl/"
        },
        {
          name: "D3.js",
          logo: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/d3js/d3js-original.svg",
          url: "https://d3js.org/"
        },
        {
          name: "Three.js",
          logo: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/threejs/threejs-original.svg",
          url: "https://threejs.org/"
        },
        {
          name: "Plotly.js",
          logo: "https://cdn.simpleicons.org/plotly/3F4F75",
          url: "https://plotly.com/javascript/"
        }
      ]
    },
    {
      label: "Backend API",
      items: [
        {
          name: "Python",
          logo: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg",
          url: "https://www.python.org/"
        },
        {
          name: "FastAPI",
          logo: "https://cdn.simpleicons.org/fastapi/009688",
          url: "https://fastapi.tiangolo.com/"
        },
        {
          name: "Pydantic",
          logo: "https://cdn.simpleicons.org/pydantic/E92063",
          url: "https://docs.pydantic.dev/"
        },
        {
          name: "Polars",
          logo: "https://cdn.simpleicons.org/polars/CD792C",
          url: "https://pola.rs/"
        },
        {
          name: "Uvicorn",
          logo: "https://uvicorn.dev/uvicorn.png",
          url: "https://www.uvicorn.org/"
        }
      ]
    },
    {
      label: "GraphLens Core",
      items: [
        {
          name: "Polars",
          logo: "https://cdn.simpleicons.org/polars/CD792C",
          url: "https://pola.rs/"
        },
        {
          name: "igraph",
          logo: "https://igraph.org/img/igraph_logo_black.svg",
          url: "https://igraph.org/"
        },
        {
          name: "NetworkX",
          logo: "https://networkx.org/_static/networkx_logo.svg",
          url: "https://networkx.org/"
        },
        {
          name: "PyArrow",
          logo: "https://arrow.apache.org/img/arrow-logo_chevrons_black-txt_white-bg.svg",
          url: "https://arrow.apache.org/"
        }
      ]
    },
    {
      label: "Analytics Module",
      items: [
        {
          name: "NumPy",
          logo: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/numpy/numpy-original.svg",
          url: "https://numpy.org/"
        },
        {
          name: "SciPy",
          logo: "https://cdn.simpleicons.org/scipy/8CAAE6",
          url: "https://scipy.org/"
        },
        {
          name: "scikit-learn",
          logo: "https://cdn.simpleicons.org/scikitlearn/F7931E",
          url: "https://scikit-learn.org/"
        },
        {
          name: "UMAP",
          logo: "https://cdn.simpleicons.org/python/3776AB",
          url: "https://umap-learn.readthedocs.io/"
        }
      ]
    },
    {
      label: "Infra & DevOps",
      items: [
        {
          name: "Docker",
          logo: "https://cdn.simpleicons.org/docker/2496ED",
          url: "https://www.docker.com/"
        },
        {
          name: "GitHub",
          logo: "https://cdn.simpleicons.org/github/FFFFFF",
          url: "https://github.com/"
        },
        {
          name: "GitHub Actions",
          logo: "https://cdn.simpleicons.org/githubactions/2088FF",
          url: "https://github.com/features/actions"
        },
        {
          name: "CMS Open Payments",
          logo: "https://www.cms.gov/files/image/open-payments-logo-tm.png",
          url: "https://openpaymentsdata.cms.gov/"
        }
      ]
    }
  ];
</script>

<div class="about-page">
  <!-- Hero -->
  <div class="about-hero">
    <div class="hero-glow"></div>
    <div class="hero-content">
      <div class="hero-badge">CS6242- Data and Visual Analytics | Sping 2026 | Georgia Tech</div>
      <p class="hero-product">MappingMoney</p>
      <h1 class="hero-title">
        <span class="title-graph">Graph</span><span class="title-sep">
          :
        </span><span class="title-lens">Lens</span>
      </h1>
      <p class="hero-sub">Pharma Payment Intelligence · CMS Open Payments</p>
    </div>
  </div>

  <div class="team-pane" aria-label="Team members">
    <h3 class="team-pane-title">Team Members</h3>
    <div class="team-strip">
      {#each teamMembers as member}
        <button type="button" class="team-pill">{member}</button>
      {/each}
    </div>
  </div>

  <!-- Placeholder grid -->
  <div class="about-grid">
    <div class="about-card">
      <h3 class="card-title">Project Overview</h3>
      <p class="card-body">
        MappingMoney: Graph Lens is a course project focused on exploring financial
        relationships in the CMS Open Payments ecosystem through graph analytics
        and interactive visualizations.
      </p>
    </div>

    <div class="about-card">
      <h3 class="card-title">Dataset</h3>
      <p class="card-body">
        We use publicly available CMS Open Payments data to study payment flows
        between manufacturers and physicians across years, products, and network
        structures.
      </p>
      <div class="dataset-links">
        <a href="https://openpaymentsdata.cms.gov/" target="_blank" rel="noreferrer"
          >CMS Open Payments Data</a
        >
        <a href="https://www.cms.gov/openpayments" target="_blank" rel="noreferrer"
          >CMS Open Payments Program</a
        >
      </div>
    </div>

    <div class="about-card">
      <h3 class="card-title">Methodology</h3>
      <p class="card-body">
        The project combines temporal graph construction, community and centrality
        analysis, anomaly detection, and dashboard-based storytelling for quick
        insight discovery.
      </p>
      <p class="card-meta">Course: CS6242- Data and Visual Analytics | Sping 2026 | Georgia Tech</p>
    </div>
  </div>

  <section class="tech-pane" aria-label="Technology stack">
    <h3 class="tech-pane-title">Tech Stack</h3>
    <div class="tech-sections">
      {#each techSections as section}
        <div class="tech-section">
          <h4 class="tech-section-title">{section.label}</h4>
          <div class="tech-grid">
            {#each section.items as tech}
              <a
                class="tech-item"
                href={tech.url}
                target="_blank"
                rel="noreferrer"
                aria-label={tech.name}
              >
                <img src={tech.logo} alt={tech.name} class="tech-logo" loading="lazy" />
                <span>{tech.name}</span>
              </a>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  </section>
</div>

<style>
  .about-page {
    min-height: 100%;
    padding: 40px 32px 80px;
    max-width: 1100px;
    margin: 0 auto;
  }

  /* ── Hero ─────────────────────────────────────────────────────── */
  .about-hero {
    position: relative;
    text-align: center;
    padding: 64px 24px 56px;
    margin-bottom: 48px;
    border-radius: 16px;
    background: var(--color-card);
    border: 1px solid var(--color-border);
    overflow: hidden;
  }

  .hero-glow {
    position: absolute;
    inset: 0;
    background: radial-gradient(
      ellipse 70% 60% at 50% 0%,
      rgba(139, 92, 246, 0.035) 0%,
      transparent 70%
    );
    pointer-events: none;
  }

  .hero-content {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
  }

  .hero-badge {
    display: inline-flex;
    padding: 5px 14px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.6px;
    color: var(--color-accent);
    background: var(--color-accent-dim);
    border: 1px solid rgba(139, 92, 246, 0.25);
    text-align: center;
  }

  .hero-product {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 3.5px;
    text-transform: uppercase;
    color: rgba(196, 181, 253, 0.5);
    margin: 0;
  }

  .hero-title {
    font-size: clamp(44px, 7vw, 72px);
    font-weight: 800;
    letter-spacing: -3px;
    line-height: 1;
    margin: 0;
    font-family: var(--font-display);
  }

  .title-graph {
    background: linear-gradient(160deg, #ffffff 0%, #ede9ff 60%, #c4b5fd 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .title-sep {
    background: linear-gradient(
      160deg,
      rgba(196, 181, 253, 0.35) 0%,
      rgba(139, 92, 246, 0.3) 100%
    );
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 300;
    font-size: 0.7em;
    vertical-align: middle;
  }

  .title-lens {
    background: linear-gradient(160deg, #8b5cf6 0%, #a78bfa 50%, #c4b5fd 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .hero-sub {
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--color-muted);
    margin: 0;
  }

  .team-pane {
    margin: 0 auto 28px;
    background: var(--color-card);
    border: 1px solid rgba(196, 181, 253, 0.22);
    border-radius: 14px;
    padding: 18px 20px;
  }

  .team-pane-title {
    margin: 0 0 12px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.7px;
    text-transform: uppercase;
    color: rgba(221, 214, 254, 0.95);
    text-align: center;
  }

  .team-strip {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 10px;
  }

  .team-pill {
    border: 1px solid rgba(196, 181, 253, 0.28);
    background: rgba(139, 92, 246, 0.08);
    color: rgba(245, 243, 255, 0.96);
    border-radius: 999px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.2px;
    line-height: 1;
    box-shadow: none;
    cursor: default;
  }

  /* ── Cards grid ────────────────────────────────────────────────── */
  .about-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 20px;
  }

  .about-card {
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: 12px;
    padding: 28px 24px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    position: relative;
    overflow: hidden;
    transition:
      border-color 0.2s,
      box-shadow 0.2s;
  }
  .about-card::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(
      135deg,
      rgba(139, 92, 246, 0.04) 0%,
      transparent 60%
    );
    pointer-events: none;
  }
  .about-card:hover {
    border-color: rgba(139, 92, 246, 0.3);
    box-shadow: 0 4px 24px rgba(139, 92, 246, 0.08);
  }

  .card-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--color-heading);
    margin: 0;
    font-family: var(--font-display);
  }

  .card-body {
    font-size: 13px;
    color: var(--color-muted);
    line-height: 1.6;
    margin: 0;
  }

  .card-meta {
    font-size: 11px;
    letter-spacing: 0.4px;
    color: rgba(196, 181, 253, 0.75);
    margin: 0;
    text-transform: none;
  }

  .dataset-links {
    display: grid;
    gap: 6px;
  }

  .dataset-links a {
    color: rgba(196, 181, 253, 0.95);
    text-decoration: none;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.2px;
    width: fit-content;
    border-bottom: 1px solid rgba(196, 181, 253, 0.35);
    transition:
      color 0.2s,
      border-color 0.2s;
  }

  .dataset-links a:hover {
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.7);
  }

  .tech-pane {
    margin-top: 26px;
    background: var(--color-card);
    border: 1px solid rgba(196, 181, 253, 0.18);
    border-radius: 14px;
    padding: 18px 20px;
  }

  .tech-pane-title {
    margin: 0 0 12px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.7px;
    text-transform: uppercase;
    color: rgba(221, 214, 254, 0.95);
  }

  .tech-sections {
    display: grid;
    gap: 14px;
  }

  .tech-section {
    border: 1px solid rgba(196, 181, 253, 0.14);
    border-radius: 12px;
    padding: 12px;
    background: rgba(139, 92, 246, 0.03);
  }

  .tech-section-title {
    margin: 0 0 10px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: rgba(196, 181, 253, 0.92);
  }

  .tech-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px;
  }

  .tech-item {
    display: flex;
    align-items: center;
    gap: 8px;
    border: 1px solid rgba(196, 181, 253, 0.22);
    background: rgba(139, 92, 246, 0.06);
    border-radius: 10px;
    padding: 9px 10px;
    color: rgba(245, 243, 255, 0.96);
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.15px;
    min-height: 38px;
    text-decoration: none;
    transition:
      border-color 0.18s,
      background-color 0.18s,
      transform 0.18s;
  }

  .tech-item:hover {
    border-color: rgba(196, 181, 253, 0.42);
    background: rgba(139, 92, 246, 0.12);
    transform: translateY(-1px);
  }

  .tech-logo {
    width: 16px;
    height: 16px;
    object-fit: contain;
    flex: 0 0 auto;
  }

  @media (max-width: 700px) {
    .hero-badge {
      font-size: 9px;
      line-height: 1.35;
    }

    .team-pill {
      font-size: 11px;
      padding: 7px 12px;
    }
  }

</style>
