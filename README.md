<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0D1117,50:FF9800,100:0D1117&height=200&section=header&text=Roydon%20Sequeira&fontSize=56&fontColor=ffffff&animation=twinkling&fontAlignY=42" width="100%" />

<a href="https://github.com/roydonsequeira">
  <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=25&duration=2600&pause=800&color=FF9800&center=true&vCenter=true&width=680&height=50&lines=GenAI+Engineer;AI+Agent+Architect;LLM+%26+RAG+Systems+Engineer;Healthcare+AI+Specialist;Open-Source+Tooling+Builder" alt="Typing SVG" />
</a>

<br/>

[![LinkedIn](https://img.shields.io/static/v1?label=&message=roydon-sequeira&color=0A66C2&style=for-the-badge&logo=linkedin&logoColor=white&labelColor=0A66C2)](https://www.linkedin.com/in/roydon-sequeira/)
[![GitHub](https://img.shields.io/static/v1?label=&message=roydonsequeira&color=181717&style=for-the-badge&logo=github&logoColor=white&labelColor=181717)](https://github.com/roydonsequeira)
[![X](https://img.shields.io/static/v1?label=&message=%40roydonsequeiraa&color=000000&style=for-the-badge&logo=x&logoColor=white&labelColor=000000)](https://x.com/roydonsequeiraa)
[![Email](https://img.shields.io/static/v1?label=&message=roydnsequeira%40gmail.com&color=EA4335&style=for-the-badge&logo=gmail&logoColor=white&labelColor=EA4335)](https://mail.google.com/mail/?view=cm&fs=1&to=roydnsequeira@gmail.com)
[![Portfolio](https://img.shields.io/static/v1?label=&message=roydonsequeira.com&color=FF9800&style=for-the-badge&logo=googlechrome&logoColor=white&labelColor=FF9800)](https://roydonsequeira.com)

</div>

<br/>

```bash
$ whoami
GenAI engineer based in Udupi, India — ~2 years shipping production AI systems.

$ cat focus.txt
Autonomous agents, RAG pipelines, and LLM systems that hold up under real load —
not just in a demo. Deep in agent orchestration, memory architectures, and
healthcare-grade automation right now.

$ history | grep -i experience
ReinHealth.ai   →  medical AI agents, RAG pipelines, clinical automation  (2024–2026)
Freelance       →  agent systems, automation platforms, AI backend work  (ongoing)
```

---

## How I Build Agents

```mermaid
flowchart LR
    U["User / Trigger"] --> O["Agent Orchestrator"]
    O --> MEM[("Memory Store")]
    O --> RAG["RAG Retrieval"]
    O --> TOOL["Tool Calls"]
    RAG --> VDB[("Vector DB — Qdrant / Chroma")]
    TOOL --> EXT["External APIs / DBs"]
    O --> CHK{"Safety & Validation"}
    CHK -->|pass| RESP["Response"]
    CHK -->|fail| FALL["Escalate / Fallback"]
```

Reasoning stays in the orchestrator. Retrieval and tool calls are isolated so failures are traceable, not silent. Nothing reaches the user without a validation pass — this is the pattern behind most of what's below.

---

## Featured Builds

### CORTEX — Local AI Agent Framework
> A private, local-first agent framework built for control instead of API dependency.

`Python` `LATS Orchestration` `Four-Tier Memory` `OpenTelemetry`

- Four-tier memory: short-term, episodic, semantic, procedural
- LATS-based orchestration for tree-search style agent planning
- Full observability via OpenTelemetry tracing
- **Status:** Open-sourceable · **Domain:** Agent Infrastructure

---

### NEXUS — AI Content Creation SaaS
> End-to-end content pipeline: crawl, draft, generate, and publish — with billing built in.

`Python` `LangChain` `DALL-E 3` `Stripe`

- Multi-source crawling for content research
- Auto-publishing to LinkedIn and X
- DALL·E 3 generated cover images per post
- Stripe-metered subscription billing
- **Domain:** AI SaaS

---

### ADILA — WhatsApp Umrah Visa Automation
> A WhatsApp-native automation platform that handles Umrah visa workflows end to end.

`n8n` `WhatsApp API` `LLM Chains`

- Conversational intake and document collection over WhatsApp
- Automated visa processing workflow with status tracking
- **Domain:** Travel & Immigration Automation

---

### Clinical Automation Workflows (n8n)
> Production automation suite for clinical operations — appointments, notes, and documentation.

`n8n` `LLM Chains` `PostgreSQL` `STT/TTS`

- Intelligent appointment booking, rescheduling, and conflict detection
- Speech-to-text clinical documentation pipelines
- Strict validation to prevent fabricated medical data
- **Status:** Production · **Domain:** Healthcare Automation

<details>
<summary><b>More builds</b></summary>
<br/>

**AI Resume Analyzer** — FastAPI + BGE embeddings + Qdrant + Gemini, three-agent evaluation pipeline

**Personal AI Proxy Agent** — WhatsApp-based JARVIS-style assistant with message routing, calendar management, and lead qualification (Twilio, FastAPI, LangChain, Claude API, Qdrant)

**GitHub Code Review Agent** — Automated PR review system with tool-based reasoning

**Skin Lesion Segmentation** — U-Net vs ResUNet comparison on the ISIC 2018 dataset (2,596 dermoscopic images), Streamlit interface for clinical visualization

</details>

---

## Stack

<div align="center">
<img src="https://skillicons.dev/icons?i=python,fastapi,flask,docker,linux,postgres,redis,nextjs,git,github,vscode,opencv,tensorflow&theme=dark" />
</div>

```yaml
agents:      [LangChain, Claude API, OpenAI, Gemini, Ollama]
retrieval:   [Qdrant, ChromaDB, PostgreSQL]
backend:     [FastAPI, Flask, Redis, Docker, Linux]
automation:  [n8n, Twilio, Stripe]
ml_cv:       [TensorFlow, Keras, OpenCV, scikit-learn, Streamlit]
tools:       [Git, GitHub Actions, VS Code, Cursor]
```

---

## Experience

**Independent GenAI Engineer** — Freelance / Contract · `2026 – Present`
Agent systems, automation platforms, and AI backend work for early-stage teams and healthcare clients.

**GenAI Engineer** — ReinHealth.ai (Stealth Healthcare Startup) · `Jul 2024 – Feb 2026`
Designed and shipped autonomous medical AI agents, RAG pipelines, and clinical workflow automation for production healthcare environments.

**Machine Learning Intern** — Igeeks Technologies, Bangalore · `Jun 2023 – Jul 2023`
Built image classification models using CNNs, AlexNet, and MLP architectures on custom dataset pipelines.

## Education

**B.E., Artificial Intelligence & Machine Learning** — NMAM Institute of Technology · `2020 – 2024`
**Executive PG, Data Science & AI** — IIT Roorkee (via Intellipaat) · `Ongoing`

---

<div align="center">

<img height="165" src="https://github-readme-stats.vercel.app/api?username=roydonsequeira&show_icons=true&theme=tokyonight&hide_border=true&title_color=FF9800&icon_color=FF9800&text_color=c9d1d9&bg_color=0D1117" />
<img height="165" src="https://streak-stats.demolab.com/?user=roydonsequeira&theme=tokyonight&hide_border=true&background=0D1117&ring=FF9800&fire=FF9800&currStreakLabel=FF9800" />

<img src="https://github-readme-stats.vercel.app/api/top-langs/?username=roydonsequeira&layout=compact&theme=tokyonight&hide_border=true&title_color=FF9800&bg_color=0D1117" />

<img src="https://github-readme-activity-graph.vercel.app/graph?username=roydonsequeira&theme=tokyo-night&hide_border=true&bg_color=0D1117&color=FF9800&line=FF9800&point=ffffff" width="95%" />

<img src="https://github-profile-trophy.vercel.app/?username=roydonsequeira&theme=tokyonight&no-frame=true&row=1&column=6" />

<!-- Needs .github/workflows/snake.yml enabled once — see the file from earlier in this chat -->
<img src="https://raw.githubusercontent.com/roydonsequeira/roydonsequeira/output/github-contribution-grid-snake.svg" width="100%" />

<img src="https://quotes-github-readme.vercel.app/api?type=horizontal&theme=tokyonight" />

</div>

---

<div align="center">

**Open to work on AI Engineering, GenAI, LLM systems, and healthcare AI.**
Building something that needs production-grade AI? Let's talk.

[![LinkedIn](https://img.shields.io/static/v1?label=&message=roydon-sequeira&color=0A66C2&style=for-the-badge&logo=linkedin&logoColor=white&labelColor=0A66C2)](https://www.linkedin.com/in/roydon-sequeira/)
[![Email](https://img.shields.io/static/v1?label=&message=roydnsequeira%40gmail.com&color=EA4335&style=for-the-badge&logo=gmail&logoColor=white&labelColor=EA4335)](https://mail.google.com/mail/?view=cm&fs=1&to=roydnsequeira@gmail.com)
[![X](https://img.shields.io/static/v1?label=&message=%40roydonsequeiraa&color=000000&style=for-the-badge&logo=x&logoColor=white&labelColor=000000)](https://x.com/roydonsequeiraa)
[![Portfolio](https://img.shields.io/static/v1?label=&message=roydonsequeira.com&color=FF9800&style=for-the-badge&logo=googlechrome&logoColor=white&labelColor=FF9800)](https://roydonsequeira.com)

<img src="https://komarev.com/ghpvc/?username=roydonsequeira&color=ff9800&style=flat-square&label=Profile+Views" />

</div>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0D1117,50:FF9800,100:0D1117&height=120&section=footer" width="100%" />
