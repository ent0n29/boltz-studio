# Boltz Studio - Vision

**Mission:** Democratize protein design. Make what requires a PhD and expensive software accessible to anyone in 5 minutes.

---

## The Opportunity

Boltz-2 is the first open-source model that does:
- Protein-ligand binding prediction
- Binding affinity scoring
- Multi-chain complexes

This is what pharma companies pay millions for (Schrödinger, etc). But there's no good UI for it.

**We're building that UI.**

---

## Phase A: Perfect the Core (Local Experience)

### A1. Drug Discovery Workflow
The complete design loop:
```
Design ligand → Dock to protein → Predict affinity →
Mutate protein → Re-predict → Compare → Iterate
```

Features:
- [x] Download PDB - Export predicted structures
- [x] Protein + Ligand - Predict protein-small molecule complexes
- [x] Binding Affinity - Predict how strongly molecules bind
- [x] Structure Comparison - Side-by-side "before/after" view
- [ ] Mutation workflow - Mutate → Predict → Compare delta

### A2. Design Library (Local)
- [x] Prediction history (localStorage)
- [ ] Save designs with notes
- [ ] Track lineage (what came from what)
- [x] Export in multiple formats (PDB, FASTA, JSON)

### A3. UX Polish
- [x] Dark/light mode toggle
- [ ] Keyboard shortcuts
- [ ] Mobile responsive
- [x] PDB Database - Load existing structures from RCSB

### A4. Advanced Features
- [ ] Batch predictions
- [ ] Sequence alignment visualization

---

## Phase B: Go Social (Community Platform)

### B1. Accounts & Profiles
- User registration/login
- Profile page with published designs
- Reputation/contribution score

### B2. Publish & Discover
- One-click publish from local library
- Tagging: target, organism, purpose
- Search by sequence similarity, target, affinity
- Filter: high confidence, most downloaded, best affinity

### B3. Social Features
- **Stars** - Bookmark interesting designs
- **Forks** - "I improved this design" with attribution
- **Comments** - Discussion, lab validation reports
- **Collections** - Curated lists of designs

### B4. Design Entries
```
📁 Insulin-B28-Pro→Lys
   Author: @researcher42
   Parent: Wild-type insulin (P01308)
   Mutation: B28 Pro→Lys
   Affinity: +15% improved binding
   pLDDT: 94%
   Downloads: 1,247
   Lab Validated: ✓
```

### B5. "Find Similar" (AI-Powered)
- Given any design, find community designs with similar:
  - Sequence
  - Structure
  - Target
- Learn from the entire community's work instantly

### B6. The Collaboration Loop
```
User A designs protein-ligand complex
        ↓
Publishes to Community
        ↓
User B finds it, forks it, improves affinity by 23%
        ↓
User A gets notified
        ↓
User A pulls the improvement back
        ↓
Science accelerates
```

---

## Phase C: Ecosystem (Future)

### C1. Integrations
- Import from: PDB, UniProt, ChEMBL, AlphaFold DB
- Export to: PyMOL, ChimeraX, Blender
- API for programmatic access

### C2. Lab Validation Pipeline
- Flag designs as "tested in lab"
- Upload experimental results
- Validated designs ranked higher

### C3. AI-Assisted Design
- "Suggest mutations to improve binding"
- "Find similar proteins in PDB"
- "Optimize for stability"

### C4. Teams & Organizations
- Private team workspaces
- Shared libraries
- Role-based access

---

## Why This Wins

1. **No competition** - Nothing like this exists in open-source
2. **Network effects** - More users → More designs → More valuable
3. **Flywheel** - Community validates designs → Better data → Better recommendations
4. **Timing** - Boltz-2 just released, we're first movers

---

## Technical Foundation (Completed)

- [x] FastAPI backend with proper architecture
- [x] SQLite persistence
- [x] WebSocket real-time updates
- [x] Direct Boltz API integration (model caching)
- [x] Rate limiting
- [x] Test suite (56 tests)
- [x] Clean, maintainable codebase

---

## Next Steps

1. **Download PDB** - Quick win, essential feature
2. **Protein + Ligand** - Unlock Boltz-2's real power
3. **Binding Affinity** - The killer feature
4. **Structure Comparison** - Enable the design workflow
5. **Local History** - Foundation for community publishing

Let's build something incredible.
