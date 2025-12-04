#!/usr/bin/env python3
"""
Mox EDA - Intent-Driven Development Workflow

Shows the methodology: Spec → RFCs → JSON → Issues → Implementation
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.programming.language import Rust
from diagrams.generic.storage import Storage
from diagrams.generic.compute import Rack
from diagrams.onprem.vcs import Github
from diagrams.saas.chat import Slack
from pathlib import Path

OUTPUT = Path(__file__).parent / "output" / "07_development_workflow"

def generate():
    graph_attr = {
        "fontsize": "16",
        "bgcolor": "white",
        "pad": "0.5",
    }
    
    with Diagram(
        "Intent-Driven Development Workflow",
        show=False,
        filename=str(OUTPUT),
        direction="TB",
        graph_attr=graph_attr,
    ):
        with Cluster("1. Define Intent (AsyncAPI Spec)"):
            spec = Storage("asyncapi.yaml\n122 Events\n14 Domains")
            schemas = Storage("Schemas\nMessages\nChannels")
            spec >> schemas
        
        with Cluster("2. Architecture RFCs"):
            with Cluster("8 RFCs"):
                rfc1 = Rust("RFC-0001\nArchitecture")
                rfc2 = Rust("RFC-0002\nStorage")
                rfc3 = Rust("RFC-0003\nConsensus")
                rfc_rest = Rust("RFC-0004\n...\nRFC-0008")
        
        with Cluster("3. Machine-Readable JSON"):
            json_schema = Storage("rfc-schema.json")
            json_rfcs = Storage("RFC-*.json\n74 Tasks\n73 Acceptance Criteria")
            json_schema >> json_rfcs
        
        with Cluster("4. GitHub Project Management"):
            script = Rust("import_issues.py")
            gh = Github("GitHub Issues\n82 Issues\n8 Milestones")
            script >> gh
        
        with Cluster("5. Implementation"):
            code = Rust("Rust\nImplementation")
            tests = Rust("Deterministic\nSimulation Tests")
            code >> tests
        
        with Cluster("6. Validation"):
            ci = Rack("CI/CD")
            deploy = Rust("Deploy")
            ci >> deploy
        
        # Flow
        schemas >> Edge(label="informs") >> rfc1
        rfc1 >> rfc2 >> rfc3 >> rfc_rest
        rfc_rest >> Edge(label="transform") >> json_rfcs
        json_rfcs >> Edge(label="import") >> script
        gh >> Edge(label="guides") >> code
        tests >> Edge(label="verify") >> ci

if __name__ == "__main__":
    generate()
    print(f"Generated: {OUTPUT}.png")
