# Smart Traffic Management Project

This repository contains simulation, computer vision, and web app components for a smart traffic management system.

## Current Structure

```text
.
├── smart_tms/
│   ├── backend/        # API/app logic
│   ├── frontend/       # UI assets
│   └── simulations/    # simulation modules
├── .gitignore
└── README.md
```

## Recommended Organization

- Keep production/project code inside `smart_tms/`.
- Treat root-level standalone scripts as temporary/prototype files.
- Keep large videos and raw datasets out of git (already covered by `.gitignore`).

Suggested target folders if you continue organizing:

- `scripts/` for one-off runnable files
- `data/` for local datasets/assets (ignored)
- `tests/` for test code

## Setup and Running

### 1. New Device Setup

#### 🐧 Linux / macOS
```bash
git clone https://github.com/dineshkumar200cmd/TMS.git
cd TMS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 🪟 Windows
```powershell
git clone https://github.com/dineshkumar200cmd/TMS.git
cd TMS
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. How to Run

#### 🐧 Linux / macOS
```bash
chmod +x run.sh
./run.sh
```

#### 🪟 Windows
Double-click `run.bat` or run:
```cmd
run.bat
```

### 3. Accessing Dashboards
- **3D Traffic Simulation**: [http://localhost:8000/traffic_3d.html](http://localhost:8000/traffic_3d.html)
- **AI Signal Dashboard**: [http://localhost:8000/traffic_video.html](http://localhost:8000/traffic_video.html)
- **Smart TMS Dashboard**: [http://localhost:8000/smart_tms/frontend/index.html](http://localhost:8000/smart_tms/frontend/index.html)
