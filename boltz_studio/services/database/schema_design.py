"""Design schema: design_targets, design_jobs, synthesis_orders."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    """Create binder design tables."""
    # Design targets library (curated therapeutic targets)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS design_targets (
            id TEXT PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            subcategory TEXT,
            pdb_id TEXT,
            uniprot_id TEXT,
            structure_pdb TEXT,
            binding_site_residues TEXT,
            binding_site_chains TEXT,
            organism TEXT,
            therapeutic_area TEXT,
            is_curated BOOLEAN DEFAULT 1,
            is_public BOOLEAN DEFAULT 1,
            difficulty TEXT,
            design_count INTEGER DEFAULT 0,
            successful_designs INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_design_targets_category
        ON design_targets(category)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_design_targets_slug
        ON design_targets(slug)
    """)

    # Design jobs (BoltzGen runs)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS design_jobs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            target_id TEXT,
            custom_target_pdb TEXT,
            protocol TEXT NOT NULL,
            status TEXT DEFAULT 'queued',
            progress REAL DEFAULT 0.0,
            current_step TEXT,
            num_designs INTEGER DEFAULT 1000,
            binder_length_min INTEGER,
            binder_length_max INTEGER,
            binding_site_residues TEXT,
            constraints TEXT,
            spec_yaml TEXT,
            output_dir TEXT,
            error TEXT,
            total_generated INTEGER,
            total_passed INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (target_id) REFERENCES design_targets(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_design_jobs_user
        ON design_jobs(user_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_design_jobs_status
        ON design_jobs(status)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_design_jobs_target
        ON design_jobs(target_id)
    """)

    # Design results (individual generated designs)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS design_results (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            design_id TEXT,
            rank INTEGER,
            sequence TEXT NOT NULL,
            structure_pdb TEXT,
            plddt_score REAL,
            ptm_score REAL,
            affinity_score REAL,
            confidence_score REAL,
            rmsd REAL,
            secondary_structure TEXT,
            metrics TEXT,
            is_published BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES design_jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_design_results_job
        ON design_results(job_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_design_results_rank
        ON design_results(job_id, rank)
    """)

    # Synthesis orders (DNA synthesis integration)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS synthesis_orders (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            design_result_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            order_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            external_order_id TEXT,
            dna_sequence TEXT,
            codon_optimized_for TEXT,
            quantity TEXT,
            estimated_cost REAL,
            actual_cost REAL,
            tracking_url TEXT,
            notes TEXT,
            ordered_at TIMESTAMP,
            shipped_at TIMESTAMP,
            delivered_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (design_result_id) REFERENCES design_results(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_synthesis_orders_user
        ON synthesis_orders(user_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_synthesis_orders_status
        ON synthesis_orders(status)
    """)


def seed_curated_targets(conn: sqlite3.Connection) -> None:
    """Seed the database with curated therapeutic targets."""
    target_count = conn.execute(
        "SELECT COUNT(*) FROM design_targets WHERE is_curated = 1"
    ).fetchone()[0]

    if target_count > 0:
        return  # Already seeded

    curated_targets = [
        # Cancer - Immune Checkpoints
        {
            "id": "target-pd1",
            "slug": "pd-1",
            "name": "PD-1 (Programmed Death-1)",
            "description": "Immune checkpoint receptor. Blocking PD-1 enhances T-cell anti-tumor activity. Target of pembrolizumab (Keytruda) and nivolumab (Opdivo).",
            "category": "cancer",
            "subcategory": "immune_checkpoint",
            "pdb_id": "5WT9",
            "uniprot_id": "Q15116",
            "organism": "Homo sapiens",
            "therapeutic_area": "Immuno-oncology",
            "difficulty": "medium",
        },
        {
            "id": "target-pdl1",
            "slug": "pd-l1",
            "name": "PD-L1 (Programmed Death-Ligand 1)",
            "description": "Ligand for PD-1. Expressed by tumors to evade immune response. Target of atezolizumab (Tecentriq) and durvalumab (Imfinzi).",
            "category": "cancer",
            "subcategory": "immune_checkpoint",
            "pdb_id": "5JDR",
            "uniprot_id": "Q9NZQ7",
            "organism": "Homo sapiens",
            "therapeutic_area": "Immuno-oncology",
            "difficulty": "medium",
        },
        {
            "id": "target-ctla4",
            "slug": "ctla-4",
            "name": "CTLA-4 (Cytotoxic T-Lymphocyte Antigen 4)",
            "description": "Immune checkpoint receptor on T-cells. Target of ipilimumab (Yervoy), first FDA-approved checkpoint inhibitor.",
            "category": "cancer",
            "subcategory": "immune_checkpoint",
            "pdb_id": "3OSK",
            "uniprot_id": "P16410",
            "organism": "Homo sapiens",
            "therapeutic_area": "Immuno-oncology",
            "difficulty": "medium",
        },
        # Cancer - Growth Factor Receptors
        {
            "id": "target-egfr",
            "slug": "egfr",
            "name": "EGFR (Epidermal Growth Factor Receptor)",
            "description": "Receptor tyrosine kinase overexpressed in many cancers. Target of cetuximab (Erbitux) and panitumumab (Vectibix).",
            "category": "cancer",
            "subcategory": "growth_factor_receptor",
            "pdb_id": "1IVO",
            "uniprot_id": "P00533",
            "organism": "Homo sapiens",
            "therapeutic_area": "Oncology",
            "difficulty": "medium",
        },
        {
            "id": "target-her2",
            "slug": "her2",
            "name": "HER2 (Human Epidermal Growth Factor Receptor 2)",
            "description": "Receptor tyrosine kinase amplified in ~20% of breast cancers. Target of trastuzumab (Herceptin) and pertuzumab (Perjeta).",
            "category": "cancer",
            "subcategory": "growth_factor_receptor",
            "pdb_id": "1N8Z",
            "uniprot_id": "P04626",
            "organism": "Homo sapiens",
            "therapeutic_area": "Oncology",
            "difficulty": "medium",
        },
        {
            "id": "target-vegf",
            "slug": "vegf",
            "name": "VEGF (Vascular Endothelial Growth Factor)",
            "description": "Key regulator of angiogenesis. Target of bevacizumab (Avastin). Blocking VEGF starves tumors of blood supply.",
            "category": "cancer",
            "subcategory": "angiogenesis",
            "pdb_id": "1VPF",
            "uniprot_id": "P15692",
            "organism": "Homo sapiens",
            "therapeutic_area": "Oncology",
            "difficulty": "easy",
        },
        # Infectious Disease
        {
            "id": "target-spike",
            "slug": "sars-cov2-spike",
            "name": "SARS-CoV-2 Spike Protein",
            "description": "Viral surface protein that binds ACE2 for cell entry. Target of COVID-19 vaccines and therapeutic antibodies.",
            "category": "infectious_disease",
            "subcategory": "viral",
            "pdb_id": "6VXX",
            "uniprot_id": "P0DTC2",
            "organism": "SARS-CoV-2",
            "therapeutic_area": "Antiviral",
            "difficulty": "medium",
        },
        {
            "id": "target-hiv-gp120",
            "slug": "hiv-gp120",
            "name": "HIV-1 gp120",
            "description": "HIV envelope glycoprotein that binds CD4. Major target for HIV vaccine and broadly neutralizing antibody development.",
            "category": "infectious_disease",
            "subcategory": "viral",
            "pdb_id": "5T3Z",
            "uniprot_id": "P04578",
            "organism": "HIV-1",
            "therapeutic_area": "Antiviral",
            "difficulty": "hard",
        },
        {
            "id": "target-rsv-f",
            "slug": "rsv-f-protein",
            "name": "RSV F Protein",
            "description": "Respiratory Syncytial Virus fusion protein. Target of palivizumab (Synagis) and new RSV vaccines.",
            "category": "infectious_disease",
            "subcategory": "viral",
            "pdb_id": "4JHW",
            "uniprot_id": "P03420",
            "organism": "RSV",
            "therapeutic_area": "Antiviral",
            "difficulty": "medium",
        },
        # Autoimmune
        {
            "id": "target-tnfa",
            "slug": "tnf-alpha",
            "name": "TNF-α (Tumor Necrosis Factor Alpha)",
            "description": "Pro-inflammatory cytokine. Target of adalimumab (Humira), infliximab (Remicade), etanercept (Enbrel).",
            "category": "autoimmune",
            "subcategory": "cytokine",
            "pdb_id": "1TNF",
            "uniprot_id": "P01375",
            "organism": "Homo sapiens",
            "therapeutic_area": "Immunology",
            "difficulty": "easy",
        },
        {
            "id": "target-il6",
            "slug": "il-6",
            "name": "IL-6 (Interleukin-6)",
            "description": "Pro-inflammatory cytokine. Target of tocilizumab (Actemra) and sarilumab (Kevzara) for rheumatoid arthritis.",
            "category": "autoimmune",
            "subcategory": "cytokine",
            "pdb_id": "1ALU",
            "uniprot_id": "P05231",
            "organism": "Homo sapiens",
            "therapeutic_area": "Immunology",
            "difficulty": "easy",
        },
        {
            "id": "target-il17a",
            "slug": "il-17a",
            "name": "IL-17A (Interleukin-17A)",
            "description": "Pro-inflammatory cytokine. Target of secukinumab (Cosentyx) and ixekizumab (Taltz) for psoriasis.",
            "category": "autoimmune",
            "subcategory": "cytokine",
            "pdb_id": "4HR9",
            "uniprot_id": "Q16552",
            "organism": "Homo sapiens",
            "therapeutic_area": "Immunology",
            "difficulty": "medium",
        },
        # Neurology
        {
            "id": "target-amyloid-beta",
            "slug": "amyloid-beta",
            "name": "Amyloid-β (Aβ)",
            "description": "Peptide that aggregates in Alzheimer's disease. Target of aducanumab (Aduhelm) and lecanemab (Leqembi).",
            "category": "neurology",
            "subcategory": "neurodegeneration",
            "pdb_id": "1IYT",
            "uniprot_id": "P05067",
            "organism": "Homo sapiens",
            "therapeutic_area": "Neurology",
            "difficulty": "hard",
        },
        {
            "id": "target-tau",
            "slug": "tau-protein",
            "name": "Tau Protein",
            "description": "Microtubule-associated protein that forms tangles in Alzheimer's and other tauopathies. Emerging therapeutic target.",
            "category": "neurology",
            "subcategory": "neurodegeneration",
            "pdb_id": "5O3L",
            "uniprot_id": "P10636",
            "organism": "Homo sapiens",
            "therapeutic_area": "Neurology",
            "difficulty": "hard",
        },
        # Metabolic
        {
            "id": "target-pcsk9",
            "slug": "pcsk9",
            "name": "PCSK9",
            "description": "Protein that degrades LDL receptors. Target of evolocumab (Repatha) and alirocumab (Praluent) for hypercholesterolemia.",
            "category": "metabolic",
            "subcategory": "cardiovascular",
            "pdb_id": "2P4E",
            "uniprot_id": "Q8NBP7",
            "organism": "Homo sapiens",
            "therapeutic_area": "Cardiovascular",
            "difficulty": "medium",
        },
        {
            "id": "target-glp1r",
            "slug": "glp1-receptor",
            "name": "GLP-1 Receptor",
            "description": "G protein-coupled receptor for glucagon-like peptide-1. Target of semaglutide (Ozempic/Wegovy) for diabetes and obesity.",
            "category": "metabolic",
            "subcategory": "diabetes",
            "pdb_id": "5VAI",
            "uniprot_id": "P43220",
            "organism": "Homo sapiens",
            "therapeutic_area": "Metabolic",
            "difficulty": "hard",
        },
    ]

    for target in curated_targets:
        conn.execute(
            """
            INSERT INTO design_targets (
                id, slug, name, description, category, subcategory,
                pdb_id, uniprot_id, organism, therapeutic_area, difficulty
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target["id"],
                target["slug"],
                target["name"],
                target["description"],
                target["category"],
                target.get("subcategory"),
                target.get("pdb_id"),
                target.get("uniprot_id"),
                target.get("organism"),
                target.get("therapeutic_area"),
                target.get("difficulty", "medium"),
            ),
        )
