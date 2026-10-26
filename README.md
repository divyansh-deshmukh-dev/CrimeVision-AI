# CrimeVision AI — Multimodal Forensic Decision-Support Platform

[![Status: Active Development](https://img.shields.io/badge/Status-Phases%201--10%20Complete-10B981.svg)]()
[![Tests: 281 Passing](https://img.shields.io/badge/Tests-281%20Passed-3B82F6.svg)]()
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-F59E0B.svg)]()
[![Framework: Flask](https://img.shields.io/badge/Framework-Flask%203.0+-EF4444.svg)]()
[![3D: Three.js](https://img.shields.io/badge/3D-Three.js%20WebGL-8B5CF6.svg)]()

CrimeVision AI is an air-gap-capable multimodal forensic decision-support and evidence correlation platform. It empowers digital evidence examiners, investigators, and academic evaluators to ingest multi-source multimedia (images, audio intercepts, CCTV video recordings) into strictly isolated case workspaces, execute deep learning computer-vision and speech-to-text models, synthesize multi-source findings into explainable cross-modal correlations, interrogate evidence via a grounded conversational AI assistant, explore spatial relationships in an interactive 3D WebGL scene, and export structured forensic PDF reports with full cryptographic provenance.

> [!IMPORTANT]
> **Forensic Decision-Support Notice**: CrimeVision AI is an investigative decision-support and research platform. All automated detections, scene captions, acoustic transcriptions, and assistant responses are machine-assisted observations. They are intended to assist human analysis and **do not constitute guaranteed court-admissible forensic proof** without independent verification and corroboration by qualified forensic examiners.

---

## Table of Contents
1. [Core Architecture & Forensic Philosophy](#core-architecture--forensic-philosophy)
2. [AI Architecture and Deployment Decisions](#ai-architecture-and-deployment-decisions)
3. [Supported Operational Experiences](#supported-operational-experiences)
   - [Evaluator / Demo Access (`user-12`)](#1-evaluator--demo-access-user-12)
   - [Registered Examiner Accounts (Multi-Tenant Isolation)](#2-registered-examiner-accounts-multi-tenant-isolation)
4. [Phased Delivery Summary (Phases 1–10)](#phased-delivery-summary-phases-110)
5. [Project Folder Structure](#project-folder-structure)
6. [Prerequisites & System Requirements](#prerequisites--system-requirements)
7. [Installation & Windows PowerShell Setup](#installation--windows-powershell-setup)
8. [Environment Variables Configuration](#environment-variables-configuration)
9. [Running the Application](#running-the-application)
10. [Automated Testing & Live Results](#automated-testing--live-results)
11. [Cloud Storage & Database Architecture](#cloud-storage--database-architecture)
12. [Data Migration & Demo Provisioning](#data-migration--demo-provisioning)
13. [Deployment Readiness & Storage Caveats](#deployment-readiness--storage-caveats)
14. [Forensic Limitations & Technical Disclaimers](#forensic-limitations--technical-disclaimers)
15. [Troubleshooting Guide](#troubleshooting-guide)
16. [License & Ethics Notice](#license--ethics-notice)

---

## Core Architecture & Forensic Philosophy

CrimeVision AI is built around the principles of **cryptographic integrity, tenant isolation, and verifiable machine provenance**:

- **Cryptographic Provenance**: Every ingested evidence file is hashed with SHA-256 upon ingest, verified against tampering, stored with read-only permissions in local storage or S3-compatible cloud storage, and recorded in the database.
- **Strict Multi-Tenant Isolation**: Case boundaries and user ownership are enforced at the query level across database queries, storage directories, model pipelines, file downloads, chat history, and PDF reports. Evidence from Case A cannot be accessed, leaked, or cited in Case B.
- **Explainable Findings & Provenance Tracking**: Deep learning models report raw confidence percentages and class labels. The system explicitly distinguishes fresh model inference, cached database results, precomputed demo data, and deterministic fallbacks.
- **Honest Spatial Projections**: Standard surveillance cameras do not provide LiDAR point clouds. 3D spatial mappings are disclosed as *illustrative 2D-to-3D projections*, explicitly preventing misleading representations of metric real-world depth.

```
                          ┌────────────────────────┐
                          │   Surveillance Image   │
                          │   Audio Intercept / 911│
                          │   CCTV / Bodycam Video │
                          └───────────┬────────────┘
                                      │ Ingest & SHA-256 Hash
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │       Case-Isolated Evidence Storage (SQLite)     │
             └───────┬──────────────────┬─────────────────┬─────┘
                     │                  │                 │
       ┌─────────────▼──────┐ ┌─────────▼───────┐ ┌───────▼────────────┐
       │   Image Analyzer   │ │  Audio Analyzer │ │   Video Analyzer   │
       │  • RT-DETR Vision  │ │ • OpenAI Whisper│ │ • OpenCV Sampler   │
       │  • Dynamic Scaling │ │ • Timestamps    │ │ • RT-DETR Frames   │
       │  • CLIP Taxonomy   │ │ • Language ID   │ │ • Aggregate Counts │
       │  • BLIP Captioning │ │ • Fallback Intel│ │ • Scene Intel      │
       └─────────────┬──────┘ └─────────┬───────┘ └───────┬────────────┘
                     │                  │                 │
                     └──────────────────┼─────────────────┘
                                        ▼
             ┌──────────────────────────────────────────────────┐
             │       Multimodal Evidence Fusion Engine          │
             │   • Cross-Modal Category Corroboration           │
             │   • Audio-Video Chronological Timeline Alignment │
             │   • Conflict & Contradiction Detection           │
             └───────┬──────────────────┬─────────────────┬─────┘
                     │                  │                 │
       ┌─────────────▼──────┐ ┌─────────▼───────┐ ┌───────▼────────────┐
       │ Three.js 3D Space  │ │ AI Chat Assist. │ │ ReportLab PDF Gen  │
       │ • Interactive Mesh │ │ • Grounded LLM  │ │ • Audit-Trailed    │
       │ • Timeline Z-layer │ │ • Citations     │ │ • Full Provenance  │
       │ • Category Filters │ │ • Local Fallback│ │ • Bounding Boxes   │
       └────────────────────┘ └─────────────────┘ └────────────────────┘
```

---

## AI Architecture and Deployment Decisions

CrimeVision AI is designed with a dual-engine architecture that bridges **local high-assurance forensic investigation** with **zero-cost, resource-constrained cloud evaluation**:

### 1. Why the Local Tech Stack Uses PyTorch, RT-DETR, BLIP, Whisper, and OpenCV
- **Air-Gap Capability & Data Sovereignty**: Law enforcement and sensitive forensic laboratories require zero network leakage. The core engine runs 100% offline using in-process PyTorch pipelines.
- **Deterministic Coordinate Mapping**: Local RT-DETR (`PekingU/rtdetr_r50vd`) generates exact, reproducible pixel bounding boxes for physical evidence localization without dependency on third-party API availability or commercial terms of service.
- **Controlled Semantic Taxonomy**: Local CLIP (`openai/clip-vit-base-patch32`) scores evidence against an auditable forensic label taxonomy with exact mathematical cosine similarities.
- **Verifiable Acoustic Phonetics**: Local OpenAI Whisper (`openai/whisper-base`) runs sequential speech decoding under `torch.no_grad()`, guaranteeing reproducible phoneme-level transcriptions.
- **Full Video Ingest & Frame Decoding**: Local OpenCV (`cv2.VideoCapture`) processes video streams directly from disk with deterministic timestamp alignment.

### 2. Why the Deployed Render Application Uses Cloud APIs (Gemini Vision & Groq Whisper)
- **Render Free Tier Resource Constraints (512 MB RAM)**: Running full PyTorch vision models (RT-DETR ~160 MB weights + CLIP ~600 MB + BLIP ~900 MB) requires at least 1.5 GB to 2.5 GB of RAM. In a 512 MB cloud container, loading PyTorch neural weights triggers uncatchable OS `SIGKILL` (Out-of-Memory) crashes that abruptly terminate the web server.
- **Strict ₹0 Monthly Cloud Budget**: CrimeVision AI was configured to operate under a strict monthly budget of **₹0**, precluding paid GPU nodes or high-memory instances ($25–$85/month).
- **Zero-RAM Cloud AI Integration**:
  - **Audio Transcription**: Uses **Groq Cloud Whisper API** (`whisper-large-v3-turbo`). Groq consumes < 5 MB RAM on Render, executes speech decoding in ~1.5 seconds, and handles MP3/WAV/M4A streams natively without needing heavy local `ffmpeg` binaries.
  - **Image Understanding & Object Detection**: Uses **Google Gemini 2.0 Flash Vision API** (`gemini-2.0-flash`). Gemini delivers 2D bounding boxes (`[ymin, xmin, ymax, xmax]`), natural language scene captions (replacing BLIP), and scene classifications (replacing CLIP) in a single request consuming < 15 MB RAM.
  - **Video Analysis**: Uses **OpenCV** to extract keyframes locally (< 5 MB RAM), then sends sampled frames in a single batched multimodal request to Gemini 2.0 Flash.

### 3. Complete Preservation of Local Models
The local deep learning tech stack was **strictly preserved rather than removed or replaced**:
- The codebase retains full local implementations in [`services/image_analyzer.py`](file:///d:/CrimeVision-AI/services/image_analyzer.py), [`services/audio_analyzer.py`](file:///d:/CrimeVision-AI/services/audio_analyzer.py), and [`services/video_analyzer.py`](file:///d:/CrimeVision-AI/services/video_analyzer.py).
- A centralized router in [`services/provider_manager.py`](file:///d:/CrimeVision-AI/services/provider_manager.py) selects between cloud and local providers based on the `INFERENCE_PROVIDER` environment variable and host hardware memory detection.
- Local workstations with ample RAM continue running PyTorch models offline by default, maintaining complete backward compatibility, air-gapped readiness, and test suite fidelity.

### 4. Technical Comparison: Local PyTorch Stack vs Cloud Gemini/Groq Stack

| Dimension | Local PyTorch Stack (`INFERENCE_PROVIDER=local`) | Cloud API Stack (`INFERENCE_PROVIDER=cloud`) |
|---|---|---|
| **Active Vision Models** | RT-DETR-R50vd + CLIP ViT-B/32 + BLIP-Base | Google Gemini 2.0 Flash Vision (`gemini-2.0-flash`) |
| **Active Speech Model** | Local Transformers Whisper (`openai/whisper-base`) | Groq Cloud Hosted Whisper (`whisper-large-v3-turbo`) |
| **RAM Footprint** | ~1,800 MB – 2,800 MB (Requires >= 2 GB RAM) | **< 25 MB** (Runs comfortably on Render 512 MB Free tier) |
| **CPU Usage** | High (Multi-threaded matrix multiplication) | Minimal (Network I/O only) |
| **Container Disk Usage**| ~2.2 GB (PyTorch, Torchvision, CUDA/MKL, HuggingFace cache) | Lightweight (~180 MB application runtime) |
| **Inference Latency** | Image: 4–12s (CPU) \| Audio: 6–20s \| Video: 15–45s | Image: ~1.2s \| Audio: ~1.5s \| Video: ~2.5s |
| **Monthly Cost** | **₹0** (Utilizes local machine hardware) | **₹0** (Utilizes free tiers: Groq 20 RPM / Gemini 15 RPM) |
| **Capabilities & Accuracy**| Exact COCO 80-class detection + zero-shot taxonomy | Generalized open-vocabulary detection + 2D bounding boxes |
| **Forensic Provenance** | `ResultSource.FRESH_INFERENCE`, local reproducibility | `ResultSource.EXTERNAL_API_GENERATION`, provider tagged (`groq`/`gemini`) |
| **Air-Gap / Offline** | **Yes** (100% offline, zero network leakage) | No (Requires outbound HTTPS access to Groq & Google APIs) |

### 5. Video Frame Sampling & Quota Disclosure
To preserve the **₹0 monthly budget** and strictly respect the **15 requests-per-minute (RPM)** free-tier rate limit of Google AI Studio, video analysis on the cloud tier uses **multimodal frame snapshot sampling**:
- **Sampling Rate**: Keyframes are extracted at **1 frame every 1.0 second** (configurable from 0.5s to 5.0s), capped at a **maximum of 5 frames per video** on the cloud tier.
- **Single-Request Multimodal Batching**: All extracted frame snapshots are compressed to 800px JPEG and dispatched in a **single batched multimodal API call** to Gemini. This guarantees that an entire video analysis consumes only **1 single API request**, eliminating any risk of hitting the 15 RPM limit.
- **Forensic Disclosure**: As transparently documented in generated forensic PDF reports and UI badges, *sampled snapshot detections represent discrete temporal intervals and do NOT prove continuous, unbroken action across unanalyzed intermediate frames*. Continuous real-time video streaming is not performed on Render Free due to bandwidth and rate limit boundaries.

### 6. Evaluator Instructions: Running Locally vs Cloud on Render

#### Running Locally (PyTorch / Offline Models)
On a local machine with at least 4 GB RAM, CrimeVision AI runs the native PyTorch models offline:
```powershell
# In your local .env or PowerShell session:
$env:INFERENCE_PROVIDER="local"
python app.py
```
*(No external API keys are required for core inference in local mode).*

#### Running in Cloud / on Render (Groq + Gemini APIs)
On Render Free (512 MB RAM) or cloud containers, configure your environment variables in the Render Dashboard (**Dashboard $\rightarrow$ Environment**):

##### Required Configuration
| Environment Variable | Recommended Value | Description |
|---|---|---|
| `INFERENCE_PROVIDER` | `cloud` | **Explicitly forces cloud API inference** across all modalities (Image, Audio, Video). (If omitted, `auto` mode automatically activates cloud on Render containers). |
| `GEMINI_API_KEY` | `AIzaSy...` | **Google Gemini API Key** (Free tier: 15 RPM). Reused for both Image/Video understanding and the Forensic AI Chat Assistant without duplication. |
| `GROQ_API_KEY` | `gsk_...` | **Groq Cloud API Key** (Free tier: 20 RPM). Reused for both Speech-to-Text Whisper transcription and secondary LLM fallback. |

##### Model Identifiers & Backward Compatibility
| Environment Variable | Recommended Value | Fallback / Behavior | Description |
|---|---|---|---|
| `GEMINI_VISION_MODEL` | `gemini-2.0-flash` | Falls back to `GEMINI_MODEL` or `gemini-2.0-flash` | Multimodal model for image 2D bounding boxes and batched video analysis. |
| `GROQ_WHISPER_MODEL` | `whisper-large-v3-turbo` | Falls back to `whisper-large-v3-turbo` | Speech-to-Text Whisper model on Groq Cloud. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Defaults to `gemini-2.5-flash` | Model used by the Forensic AI Chat Assistant (Phase 7). |
| `AI_PROVIDER` | `gemini` | Defaults to `gemini` | Backend for Forensic AI Chat Assistant (`gemini` or `groq`). |
| `WHISPER_MODEL_NAME` | `openai/whisper-base` | N/A | Local PyTorch HuggingFace Whisper identifier; safely ignored by cloud Groq inference to prevent model ID errors. |

##### Application & Security Defaults
| Environment Variable | Value | Description |
|---|---|---|
| `FLASK_ENV` | `production` | Enforces production mode and strict security checks. |
| `SECRET_KEY` | *(Random 32-char hex)* | Session cookie cryptographic signing secret (required in production). |
| `DEMO_DISPLAY_NAME` | `user` | Evaluator display name. |
| `DEMO_CASE_NAME` | `test case` | Default demo case name. |

```bash
# Example Render Environment Variable Settings:
INFERENCE_PROVIDER=cloud
GEMINI_API_KEY=AIzaSy_your_free_gemini_api_key_here
GROQ_API_KEY=gsk_your_free_groq_api_key_here
GEMINI_VISION_MODEL=gemini-2.0-flash
GROQ_WHISPER_MODEL=whisper-large-v3-turbo
AI_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash
WHISPER_MODEL_NAME=openai/whisper-base
FLASK_ENV=production
SECRET_KEY=generate_a_secure_random_32_character_string_here
```

---

## Supported Operational Experiences

### 1. Evaluator / Demo Access (`user-12`)
Designed for evaluators, mentors, and academic review:
- **Simplified Demo Login**: The `/login` page includes a **Demo Login** button that pre-populates evaluator credentials (`user-12` / `user1234`) without auto-submitting, allowing manual review and submission.
- **Full Investigator Capabilities**: Evaluator accounts operate as normal users with permissions to create cases, upload new multimedia evidence, trigger live deep learning inference, converse with the AI assistant, and export reports.
- **Legacy Sentinel Case (`case_demo_sentinel`)**: Also supports an optional read-only demo case provisioned via `python provision_demo.py` with precomputed findings.

### 2. Registered Examiner Accounts (Multi-Tenant Isolation)
Designed for active practitioners and multiple users:
- **Isolated Registration & Authentication**: Examiners register at `/signup` with PBKDF2 password hashing, session-based cookie management, and strict CSRF token validation.
- **Autonomous Case Management**: Examiners manage private cases, ingest multimedia evidence (images, audio, video), execute on-demand deep learning models, converse with the AI Assistant, and generate forensic PDF reports.
- **Multi-Tenant IDOR Protection**: Row-level user authorization ensures users can never access, inspect, download, or delete cases belonging to other users.

---

## Phased Delivery Summary (Phases 1–10)

| Phase | Title | Status | Description |
|---|---|:---:|---|
| **Phase 1** | Foundation & Case Management | ✅ Complete | Flask application factory, SQLite database schema, secure evidence upload, SHA-256 cryptographic provenance, read-only storage, case isolation. |
| **Phase 2** | Image Analysis Pipeline | ✅ Complete | Object detection via RT-DETR (`PekingU/rtdetr_r50vd`), natural language captioning via BLIP (`Salesforce/blip-image-captioning-base`), zero-shot taxonomy matching via CLIP (`openai/clip-vit-base-patch32`), and dynamic downscaling (1280px max) with original-coordinate mapping. |
| **Phase 3** | Forensic PDF Report Generation | ✅ Complete | Multi-page structured forensic PDF generation using ReportLab, with case metadata, SHA-256 verification hashes, bounding box detection tables, and legal disclaimers. |
| **Phase 4** | Multilingual Audio Transcription | ✅ Complete | Speech-to-text transcription powered by OpenAI Whisper (`openai/whisper-base`), timestamped segment intervals, detected language extraction, and grounded entity extraction fallback. |
| **Phase 5** | Video Analysis & Frame Sampling | ✅ Complete | OpenCV video decoding, metadata inspection (FPS, resolution, duration), bounded frame sampling intervals, discrete RT-DETR frame inference, and chronological event timelines. |
| **Phase 6** | Multimodal Evidence Fusion | ✅ Complete | Rule-based explainable correlation engine linking observations across image, audio, and video modalities; highlights cross-modal corroborations and temporal alignments while surfacing scene contradictions. |
| **Phase 7** | Grounded Forensic AI Chat | ✅ Complete | Natural language investigation assistant powered by Google Gemini (`gemini-2.5-flash`) via official `google-genai` SDK (with Groq fallback and offline deterministic fallback); strictly grounded in case evidence with exact citations `[ev_xxx @ ts]`. |
| **Phase 8** | Interactive 3D Spatial Scene | ✅ Complete | WebGL Three.js workspace projecting 2D detections onto an illustrative 3D grid with procedural meshes, orbit controls, raycasting, category/confidence filters, and direct evidence jump links. |
| **Phase 9** | Testing & Hardened Documentation | ✅ Complete | Automated test suite expanded to 281 tests (100% passing), security audits, cloud storage abstraction, dual SQLite/PostgreSQL support, and provenance tracking. |
| **Phase 10** | Stitch Forensic UI Redesign | ✅ Complete | Professional dark theme inspired by Google Stitch (`#0c0e13` canvas, `#111318` surfaces, `#38bdf8` steel cyan accents), Google `Inter` + `JetBrains Mono` typography, responsive layouts, and zero-backend-modification guarantee. |

---

## Project Folder Structure

```
CrimeVision-AI/
├── .env.example                  # Environment configuration template (safe for VCS)
├── .gitignore                    # Enforces exclusion of .env, local DB, models, scratch, and uploads
├── README.md                     # Comprehensive platform documentation (this file)
├── api/
│   └── index.py                  # Vercel serverless WSGI entry point
├── app.py                        # Flask application factory and local development entry point
├── config.py                     # Centralized environment variable and storage configuration
├── create_admin.py               # Administrative user provisioning CLI
├── migrate_data.py               # Data migration CLI (local SQLite/storage -> cloud PostgreSQL/S3)
├── provision_demo.py             # Mentor Demo provisioning CLI (seeds demo account and sentinel case)
├── pytest.ini                    # Pytest options, paths, and test discovery rules
├── requirements.txt              # Production and test Python dependencies
├── vercel.json                   # Vercel deployment configuration and route rewrites
├── routes/
│   ├── __init__.py               # Package initializer
│   ├── auth.py                   # Authentication, registration, login, demo-login, and logout routes
│   ├── cases.py                  # Case management, evidence upload, analysis, chat, 3D routes
│   └── health.py                 # System health check, storage check, and API key readiness
├── services/
│   ├── __init__.py               # Package initializer
│   ├── audio_analyzer.py         # Whisper audio decoding, resampling, and speech transcription
│   ├── auth_service.py           # Password hashing, session validation, and case authorization
│   ├── chat_assistant.py         # Grounded Gemini/Groq LLM assistant with citation mechanics
│   ├── csrf.py                   # HMAC-based CSRF protection and token verification
│   ├── fusion_analyzer.py        # Cross-modal correlation, temporal alignment, and conflict detection
│   ├── image_analyzer.py         # RT-DETR object detection, BLIP captioning, CLIP zero-shot scoring
│   ├── pdf_report.py             # ReportLab forensic PDF builder with tables, disclaimers, and metadata
│   ├── provenance.py             # Evidence analysis provenance tracking and cache auditing
│   ├── rate_limiter.py           # In-memory sliding window rate limiter with trusted proxy support
│   ├── spatial_mapper.py         # 2D-to-3D illustrative spatial mapping for Three.js workspace
│   ├── storage_service.py        # Abstract storage layer (LocalStorageProvider & S3StorageProvider)
│   └── video_analyzer.py         # OpenCV video frame sampler and RT-DETR frame inference
├── static/
│   ├── css/
│   │   ├── landing.css           # Public landing page styling
│   │   ├── main.css              # Legacy dark workstation styling
│   │   └── workspace.css         # Stitch-redesigned forensic workstation stylesheet
│   └── js/
│       ├── app.js                # Legacy frontend controller
│       ├── landing.js            # Landing page event dispatcher
│       ├── workspace.js          # Forensic workspace interactive controller & API dispatcher
│       └── vendor/
│           ├── OrbitControls.js  # Three.js camera orbit controls
│           └── three.min.js      # Three.js r128 3D rendering engine
├── storage/
│   ├── database.py               # Dual SQLite & PostgreSQL database adapter with connection pooling
│   ├── cases_store.py            # Case CRUD operations and database accessors
│   ├── chat_store.py             # Chat history persistence and session clear
│   ├── evidence_store.py         # Evidence persistence, SHA-256 calculation, and provenance checks
│   ├── migrate_data.py           # Core migration logic with checksum verification
│   ├── provision_demo.py         # Demo account and synthetic case provisioning engine
│   ├── reports_store.py          # Report metadata recording and retrieval
│   └── users_store.py            # User management, password verification, and role checks
├── templates/
│   ├── index.html                # Stitch-redesigned platform overview & landing page
│   ├── login.html                # Stitch-redesigned examiner login with Demo Login button
│   ├── signup.html               # Stitch-redesigned examiner registration page
│   └── workspace.html            # Forensic investigation workstation template
└── tests/
    ├── conftest.py               # Pytest fixtures, isolated SQLite DB, and synthetic media fixtures
    ├── test_audio_analysis.py    # Whisper audio pipeline and segment tests
    ├── test_auth.py              # User authentication, registration, session, and CSRF tests
    ├── test_authorization.py     # Multi-tenant case ownership, IDOR defenses, and role tests
    ├── test_cases.py             # Case creation, listing, retrieval, and validation tests
    ├── test_chat_assistant.py    # AI Chat Assistant, citation, and history persistence tests
    ├── test_cloud_and_demo.py    # S3 storage, DB adapter, demo login, and Vercel handler tests
    ├── test_csrf_upload.py       # CSRF protection, multipart upload headers/form, & security tests
    ├── test_evidence.py          # Evidence upload, MIME detection, size limits, and SHA-256 tests
    ├── test_fusion_analysis.py   # Multimodal evidence fusion and cross-modal tests
    ├── test_health.py            # API health endpoint, directory checks, and key status tests
    ├── test_image_analysis.py    # RT-DETR, CLIP, and BLIP pipeline tests
    ├── test_mentor_login_and_workspace.py # Evaluator credentials and workspace behavior tests
    ├── test_pdf_report.py        # ReportLab PDF generation and content assertions (pypdf)
    ├── test_performance_and_resilience.py # Model caching, chunking, and downscaling tests
    ├── test_provenance_and_reliability.py # Provenance tracking, fallback labeling, and cache tests
    ├── test_regression_phase9.py # Full multimodal case PDF, security, and edge-case tests
    ├── test_video_analysis.py    # OpenCV video extraction, RT-DETR frames, & real inference
    └── test_visualization_3d.py  # 3D spatial mapping, projection, and isolation tests
```

---

## Prerequisites & System Requirements

- **Operating System**: Windows 10/11 (64-bit), Ubuntu 20.04+, or macOS 12+
- **Python**: Version 3.10, 3.11, 3.12, or 3.13 (64-bit recommended)
- **RAM**: Minimum 8.0 GB (16.0 GB recommended for deep learning computer vision and speech models on CPU)
- **Disk Space**: At least 5 GB free disk space for PyTorch, model weights, and evidence storage
- **FFmpeg**: Required on the system PATH for audio transcoding and certain video codec decodings

---

## Installation & Windows PowerShell Setup

### 1. Clone the Repository
```powershell
git clone https://github.com/your-org/CrimeVision-AI.git
cd CrimeVision-AI
```

### 2. Create and Activate Virtual Environment
**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux / macOS (Bash):**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
For standard CPU workstations, install PyTorch CPU wheels first, followed by the project dependencies:

```powershell
# Install PyTorch CPU wheels
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install remaining requirements
pip install -r requirements.txt
```

---

## Environment Variables Configuration

CrimeVision AI includes a template: `.env.example`.

### Setup Instructions
1. Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
   *(On Linux/macOS: `cp .env.example .env`)*

2. Open `.env` and configure your settings:
   ```ini
   # ── Flask & Core Security ──────────────────────────────────────────────────
   FLASK_ENV=development
   FLASK_DEBUG=1
   FLASK_HOST=0.0.0.0
   FLASK_PORT=5000
   SECRET_KEY=change-me-to-a-strong-random-secret
   SESSION_COOKIE_SECURE=0
   TRUSTED_PROXIES=

   # ── Database Configuration ─────────────────────────────────────────────────
   # Leave blank to use local SQLite (storage/crimevision.db).
   # For production PostgreSQL:
   DATABASE_URL=
   # DATABASE_URL=postgresql+pg8000://user:password@host:5432/dbname?sslmode=require

   # ── Storage Configuration ──────────────────────────────────────────────────
   # Storage backend: 'local' (default) or 's3' (AWS S3, Cloudflare R2, MinIO)
   STORAGE_BACKEND=local
   S3_BUCKET_NAME=
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=
   AWS_SECRET_ACCESS_KEY=
   S3_ENDPOINT_URL=

   # ── AI Chat Assistant (Phase 7) ────────────────────────────────────────────
   AI_PROVIDER=gemini
   GEMINI_API_KEY=
   GEMINI_MODEL=gemini-2.5-flash

   # ── Groq API (Fallback) ────────────────────────────────────────────────────
   GROQ_API_KEY=

   # ── Deep Learning Model Identifiers (Optional) ─────────────────────────────
   RTDETR_MODEL_NAME=PekingU/rtdetr_r50vd
   CLIP_MODEL_NAME=openai/clip-vit-base-patch32
   BLIP_MODEL_NAME=Salesforce/blip-image-captioning-base
   WHISPER_MODEL_NAME=openai/whisper-base
   ```

### Production Security Parameters
- **`SECRET_KEY` (Mandatory in Production)**: Must be set when `FLASK_ENV=production`. Minimum 16 characters, validated against known default placeholders at startup.
- **`TRUSTED_PROXIES`**: Must contain only known reverse proxy IPs when behind Nginx or Cloudflare. Must remain empty if directly exposed.
- **`SESSION_COOKIE_SECURE`**: Set to `1` when serving over HTTPS.

---

## Running the Application

### Local Development Server
```powershell
python app.py
```

Startup output:
```text
[CrimeVision AI] Starting on http://0.0.0.0:5000 debug=True
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

### Production WSGI Server
- **Windows (Waitress)**:
  ```powershell
  waitress-serve --listen=0.0.0.0:5000 app:app
  ```
- **Linux (Gunicorn)**:
  ```bash
  gunicorn -w 2 -b 0.0.0.0:5000 "app:create_app()"
  ```

### Accessing the Workspace
- **Browser**: Navigate to [http://127.0.0.1:5000](http://127.0.0.1:5000).
- **Evaluator Access**: On the login screen, click **Demo Login** to prefill `user-12` / `user1234`, then click **Sign In**.
- **Health Check**:
  ```powershell
  curl.exe -i http://127.0.0.1:5000/api/health
  ```

---

## Automated Testing & Live Results

The test suite comprises **281 automated tests** across 19 test modules.

### Run All Tests
```powershell
python -m pytest tests/ -v
```

### Actual Live Test Execution Results
```text
============================= test session starts =============================
platform win32 -- Python 3.13.1, pytest-9.1.1
collected 281 items

tests/test_audio_analysis.py .........................                  [  8%]
tests/test_auth.py ...................................                  [ 21%]
tests/test_authorization.py ..........................                  [ 30%]
tests/test_cases.py ...........                                         [ 34%]
tests/test_chat_assistant.py ............                               [ 38%]
tests/test_cloud_and_demo.py ...................                        [ 45%]
tests/test_csrf_upload.py ......                                        [ 47%]
tests/test_evidence.py .................................                [ 59%]
tests/test_fusion_analysis.py ........                                  [ 62%]
tests/test_health.py ...........                                        [ 66%]
tests/test_image_analysis.py .........................                  [ 75%]
tests/test_mentor_login_and_workspace.py ........                       [ 77%]
tests/test_pdf_report.py .........                                      [ 81%]
tests/test_performance_and_resilience.py ...........                    [ 85%]
tests/test_provenance_and_reliability.py ...........                    [ 88%]
tests/test_regression_phase9.py ....................                    [ 96%]
tests/test_video_analysis.py ............................               [ 96%]
tests/test_visualization_3d.py ...........                              [100%]

======================= 281 passed in 149.34s (0:02:29) =======================
```

### Test Methodology
- **Deterministic Route & Auth Testing**: Model inference for Hugging Face and external LLM APIs are mocked in unit/API tests, ensuring fast, reproducible execution without external API dependencies.
- **Real Inference Verification**: Tests such as `test_rtdetr_detection_maps_to_original_coordinates` and `test_real_video_pipeline_inference` perform live coordinate scaling and frame extraction on synthetic images/videos.
- **PDF Binary Parsing**: `pypdf.PdfReader` parses generated binary PDFs to assert exact metadata, SHA-256 hashes, and section content.

---

## Cloud Storage & Database Architecture

- **Dual Database Engine (`storage/database.py`)**:
  - Default: SQLite (`storage/crimevision.db`) with WAL journal mode, connection timeouts, and foreign key enforcement.
  - Production: SQLAlchemy adapter connecting via `DATABASE_URL` to PostgreSQL (Neon, Supabase, AWS RDS).
- **Pluggable Storage Layer (`services/storage_service.py`)**:
  - `LocalStorageProvider`: Stores files locally under `storage/uploads/` and `storage/reports/` with read-only permissions (`0o444`).
  - `S3StorageProvider`: Connects via `boto3` to S3-compliant object storage (AWS S3, Cloudflare R2, MinIO).

---

## Data Migration & Demo Provisioning

### 1. Provisioning the Demo Account (`provision_demo.py`)
```powershell
python provision_demo.py
```
Provisions the `demo_mentor` account and seeds the sample case `case_demo_sentinel`.

### 2. Data Migration (`migrate_data.py`)
```powershell
# Dry-run inspection
python migrate_data.py --dry-run

# Execute migration from local SQLite/storage to cloud PostgreSQL/S3
python migrate_data.py
```

---

## Deployment Readiness & Storage Caveats

### Target Assessment: Serverless (Vercel) vs Persistent Container (Render / VM)

1. **Vercel Serverless (`vercel.json`)**:
   - **Ephemeral Storage**: Vercel serverless functions have a read-only root filesystem with only a temporary, unshared `/tmp` directory. Local SQLite databases and uploaded evidence stored locally **will not persist across lambda invocations or restarts**.
   - **Bundle Size Limit**: Deep learning dependencies (`torch`, `transformers`, `torchvision`, `opencv`) and model weight files (RT-DETR ~160MB, Whisper ~140MB, CLIP ~600MB, BLIP ~900MB) **greatly exceed Vercel's 250 MB uncompressed bundle limit**.
   - **Execution Timeouts**: CPU inference can take 30–100 seconds per high-resolution file, exceeding Vercel serverless timeout limits (10s Hobby / 60s Pro).
   - **Viability**: Vercel is suitable **only** for lightweight frontend presentation and precomputed demo data using remote PostgreSQL (`DATABASE_URL`) and S3 (`STORAGE_BACKEND=s3`), with live inference delegated to an external asynchronous worker.

2. **Persistent Container / VM (Render, AWS EC2, Docker) — Recommended**:
   - For real-time, on-server deep learning inference (PyTorch, RT-DETR, Whisper, OpenCV) and persistent local evidence storage, deploy to a platform that supports persistent disks and containerized environments.
   - Run via Gunicorn or Waitress with a persistent volume mounted at `storage/`.

---

## Forensic Limitations & Technical Disclaimers

1. **Illustrative 3D Projections**: The 3D scene workspace projects 2D computer vision bounding boxes onto an illustrative ground grid. It does **not** represent metric LiDAR point clouds or calibrated physical depth.
2. **Audio Transcription & Voice Attribution**: OpenAI Whisper transcribes acoustic speech phonemes into text. It does **not** perform speaker voice biometrics or verify speaker identity.
3. **Discrete Video Sampling**: Video analysis extracts frames at configurable sampling intervals (e.g. 1.0s, 2.0s). Transitory events between sampled frames may not appear in detection tables.
4. **Machine-Assisted Decision Support**: AI detections, captions, similarity scores, and chat answers are machine-assisted decision support outputs and must be verified by certified forensic examiners before court presentation.

---

## Troubleshooting Guide

### 1. Port 5000 is Already in Use
- **Windows (PowerShell)**:
  ```powershell
  Get-NetTCPConnection -LocalPort 5000
  Stop-Process -Id <ProcessId> -Force
  ```
- Alternatively, modify `FLASK_PORT=5001` in `.env`.

### 2. Missing Audio Codec / Librosa Errors
Install FFmpeg on your system PATH:
- **Windows**: `winget install Gyan.FFmpeg` or `choco install ffmpeg`
- **Ubuntu/Debian**: `sudo apt-get install ffmpeg libsndfile1`
- **macOS**: `brew install ffmpeg`

### 3. Running Pytest in PowerShell
Always invoke pytest via the active Python module:
```powershell
python -m pytest tests/ -v
```

---

## License & Ethics Notice

CrimeVision AI is designed strictly for authorized forensic investigation, evidence management, and research purposes. All evidence handling, hash generation, and analysis pipelines adhere to digital forensics best practices and chain-of-custody preservation principles.
