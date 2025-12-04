#!/usr/bin/env python3
"""
Mox EDA - Domain Model Diagram

Shows the 14 domains and their relationships.
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.programming.language import Rust
from diagrams.generic.blank import Blank
from pathlib import Path

OUTPUT = Path(__file__).parent / "output" / "05_domain_model"

def generate():
    graph_attr = {
        "fontsize": "16",
        "bgcolor": "white",
        "pad": "0.5",
    }
    
    with Diagram(
        "Domain Model - 14 Domains, 122 Events",
        show=False,
        filename=str(OUTPUT),
        direction="TB",
        graph_attr=graph_attr,
    ):
        with Cluster("Core Domains"):
            auth = Rust("Auth\n(2 events)")
            tenant = Rust("Tenant\n(12 events)")
            talent = Rust("Talent\n(5 events)")
        
        with Cluster("Project Management"):
            project = Rust("Project\n(4 events)")
            schedule = Rust("Schedule\n(3 events)")
            battle = Rust("Battle\n(3 events)")
        
        with Cluster("AI & Communication"):
            semantic = Rust("Semantic\n(2 events)")
            notification = Rust("Notification\n(2 events)")
            audit = Rust("Audit\n(1 event)")
        
        with Cluster("Business Operations"):
            contract = Rust("Contract\n(7 events)")
            campaign = Rust("Campaign\n(10 events)")
            outreach = Rust("Outreach\n(16 events)")
        
        with Cluster("External Integrations"):
            integration = Rust("Integration\n(18 events)")
            stripe = Rust("Stripe\n(16 events)")
            analytics = Rust("Analytics\n(21 events)")
        
        # Key relationships
        auth >> tenant
        tenant >> talent
        talent >> campaign
        talent >> contract
        campaign >> outreach
        contract >> stripe
        integration >> analytics
        
        # Cross-cutting
        tenant >> Edge(style="dashed") >> audit
        campaign >> Edge(style="dashed") >> analytics

if __name__ == "__main__":
    generate()
    print(f"Generated: {OUTPUT}.png")
