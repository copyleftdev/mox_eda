#!/usr/bin/env python3
"""
Generate all architecture diagrams for Mox EDA.

This script uses the 'diagrams' library (Diagram as Code) to generate
visual representations of the TigerBeetle-inspired architecture.

Usage:
    pip install diagrams
    python diagrams/generate_all.py

Output:
    diagrams/output/*.png
"""

from pathlib import Path

# Ensure output directory exists
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Import diagram generators
from architecture_overview import generate as gen_overview
from storage_engine import generate as gen_storage
from consensus_cluster import generate as gen_consensus
from event_flow import generate as gen_event_flow
from domain_model import generate as gen_domain
from api_layer import generate as gen_api
from development_workflow import generate as gen_workflow

def main():
    print("🎨 Generating Mox EDA Architecture Diagrams")
    print("=" * 50)
    
    generators = [
        ("Architecture Overview", gen_overview),
        ("Storage Engine", gen_storage),
        ("Consensus & Cluster", gen_consensus),
        ("Event Flow Lifecycle", gen_event_flow),
        ("Domain Model", gen_domain),
        ("API Layer", gen_api),
        ("Development Workflow", gen_workflow),
    ]
    
    for name, generator in generators:
        print(f"\n📊 Generating: {name}")
        try:
            generator()
            print(f"   ✓ Complete")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 50)
    print(f"✅ Diagrams saved to: {OUTPUT_DIR.absolute()}")
    print("\nGenerated files:")
    for f in sorted(OUTPUT_DIR.glob("*.png")):
        print(f"  - {f.name}")

if __name__ == "__main__":
    main()
