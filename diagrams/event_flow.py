#!/usr/bin/env python3
"""
Mox EDA - Event Flow Lifecycle Diagram

Shows how events flow through the system from API to storage.
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.programming.language import Rust
from diagrams.generic.storage import Storage
from diagrams.onprem.client import Client
from diagrams.generic.network import Firewall
from pathlib import Path

OUTPUT = Path(__file__).parent / "output" / "04_event_flow"

def generate():
    graph_attr = {
        "fontsize": "18",
        "bgcolor": "white",
        "pad": "0.5",
        "rankdir": "LR",
    }
    
    with Diagram(
        "Event Lifecycle - Command to Persisted Event",
        show=False,
        filename=str(OUTPUT),
        direction="LR",
        graph_attr=graph_attr,
    ):
        # Step 1: Client Request
        client = Client("Client")
        
        with Cluster("1. API Layer"):
            api = Firewall("HTTP/WS")
            auth = Rust("Auth\nMiddleware")
            validate = Rust("Validate\nRequest")
        
        with Cluster("2. Command Processing"):
            cmd = Rust("Command\n(CreateTalent)")
            sm = Rust("State Machine\nprocess()")
        
        with Cluster("3. Event Generation"):
            event = Rust("Event\n(TalentCreated)")
            envelope = Rust("CloudEvent\nEnvelope")
        
        with Cluster("4. Consensus"):
            propose = Rust("Propose to\nRaft Leader")
            replicate = Rust("Replicate to\nFollowers")
            commit = Rust("Commit\n(Quorum)")
        
        with Cluster("5. Persistence"):
            wal = Storage("WAL\nAppend")
            lsm = Storage("LSM\nUpdate")
        
        with Cluster("6. Response"):
            response = Rust("Success\nResponse")
        
        # Flow
        client >> api >> auth >> validate
        validate >> cmd >> sm
        sm >> event >> envelope
        envelope >> propose >> replicate >> commit
        commit >> wal >> lsm
        lsm >> response >> client

if __name__ == "__main__":
    generate()
    print(f"Generated: {OUTPUT}.png")
