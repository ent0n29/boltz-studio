# BoltzStudio 🧬

**Protein Design & Visualization Studio** powered by Boltz

An interactive web application for protein structure prediction and design, featuring:
- Real-time structure prediction using Boltz-2
- Interactive 3D molecular visualization with confidence coloring
- Protein design tools (mutation analysis, optimization)
- Export capabilities for downstream analysis

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│    Backend      │────▶│     Boltz       │
│    (React +     │◀────│    (FastAPI)    │◀────│    (PyTorch)    │
│    3Dmol.js)    │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
     Port 3000              Port 8000
```

## Quick Start

### Prerequisites
- Python 3.10+ with Boltz installed (see main README)
- Node.js 18+ (for frontend development)

### 1. Start the Backend

```bash
cd studio/backend

# Install dependencies
pip install fastapi uvicorn pyyaml

# Start the API server
python app.py
```

The API will be available at http://localhost:8000

### 2. Start the Frontend

```bash
cd studio/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at http://localhost:3000

## API Endpoints

### Structure Prediction

```bash
# Submit a prediction job
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "sequences": [{"id": "A", "sequence": "MVTPEG...", "type": "protein"}],
    "name": "my_protein",
    "recycling_steps": 1,
    "sampling_steps": 50
  }'

# Check job status
curl http://localhost:8000/job/{job_id}

# Get structure
curl http://localhost:8000/job/{job_id}/structure?format=pdb
```

### Design Tools

```bash
# Random mutation
curl -X POST "http://localhost:8000/design/random-mutate?sequence=MVTPEG...&num_mutations=1"
```

## Features

### 🔬 Structure Prediction
- Full Boltz-2 integration
- Automatic MSA generation via ColabFold
- Configurable prediction parameters

### 🎨 3D Visualization
- Interactive molecular viewer (3Dmol.js)
- pLDDT confidence coloring (AlphaFold style)
- Rotate, zoom, and explore structures

### 🧬 Protein Design
- Random mutation generator
- Position-specific mutations
- Mutation effect comparison (coming soon)

### 📊 Metrics
- Confidence scores (pLDDT, pTM, iPTM)
- Per-residue confidence visualization
- Export PAE/PDE matrices

## Development

### Project Structure

```
studio/
├── backend/
│   ├── app.py              # FastAPI application
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Main application
│   │   ├── api.ts          # API client
│   │   └── components/
│   │       ├── MolstarViewer.tsx   # 3D viewer
│   │       ├── SequenceEditor.tsx  # Sequence input
│   │       ├── DesignTools.tsx     # Design actions
│   │       └── MetricsBar.tsx      # Metrics display
│   ├── index.html
│   └── package.json
└── README.md
```

### Tech Stack

**Backend:**
- FastAPI - High-performance Python API framework
- Boltz - Structure prediction engine
- Pydantic - Data validation

**Frontend:**
- React 18 + TypeScript
- 3Dmol.js - Molecular visualization
- Vite - Build tool

## Roadmap

- [ ] Protein-ligand docking interface
- [ ] Batch prediction support
- [ ] Mutation effect predictor
- [ ] Structure comparison view
- [ ] PDB database search integration
- [ ] Export to PyMOL/ChimeraX

## License

MIT License - Same as Boltz

---

Built with ❤️ using [Boltz](https://github.com/jwohlwend/boltz)
