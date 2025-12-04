#!/usr/bin/env python3
"""
Mox EDA - Consensus & Cluster Diagram

Shows Raft consensus with Viewstamped Replication extensions.
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.compute import Server
from diagrams.programming.language import Rust
from diagrams.generic.storage import Storage
from pathlib import Path

OUTPUT = Path(__file__).parent / "output" / "03_consensus_cluster"

def generate():
    graph_attr = {
        "fontsize": "18",
        "bgcolor": "white",
        "pad": "0.5",
    }
    
    with Diagram(
        "Raft Consensus with VR Extensions",
        show=False,
        filename=str(OUTPUT),
        direction="LR",
        graph_attr=graph_attr,
    ):
        with Cluster("Cluster (Quorum: 2 of 3)"):
            with Cluster("Node 1 - LEADER"):
                leader = Server("mox-node-1")
                leader_log = Storage("Log\n[1,2,3,4,5]")
                leader_state = Rust("State Machine")
                leader >> leader_log >> leader_state
            
            with Cluster("Node 2 - FOLLOWER"):
                follower1 = Server("mox-node-2")
                f1_log = Storage("Log\n[1,2,3,4,5]")
                f1_state = Rust("State Machine")
                follower1 >> f1_log >> f1_state
            
            with Cluster("Node 3 - FOLLOWER"):
                follower2 = Server("mox-node-3")
                f2_log = Storage("Log\n[1,2,3,4]")
                f2_state = Rust("State Machine")
                follower2 >> f2_log >> f2_state
        
        # Raft RPCs
        leader >> Edge(
            label="AppendEntries\nHeartbeat",
            color="blue",
            style="bold"
        ) >> follower1
        
        leader >> Edge(
            label="AppendEntries\nHeartbeat", 
            color="blue",
            style="bold"
        ) >> follower2
        
        follower1 >> Edge(
            label="RequestVote\n(election)",
            color="orange",
            style="dashed"
        ) >> leader
        
        # Client interaction
        with Cluster("Clients"):
            client = Rust("Client")
        
        client >> Edge(label="Write", color="green") >> leader
        leader >> Edge(label="Replicate", color="blue") >> follower1
        leader >> Edge(label="Ack (committed)", color="green") >> client

if __name__ == "__main__":
    generate()
    print(f"Generated: {OUTPUT}.png")
