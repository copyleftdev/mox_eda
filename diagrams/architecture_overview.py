#!/usr/bin/env python3
"""
Mox EDA - Architecture Overview Diagram

Shows the high-level TigerBeetle-inspired single-binary architecture.
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.custom import Custom
from diagrams.onprem.compute import Server
from diagrams.onprem.client import Client, Users
from diagrams.onprem.network import Nginx
from diagrams.programming.language import Rust
from diagrams.generic.storage import Storage
from diagrams.generic.network import Firewall
from pathlib import Path

OUTPUT = Path(__file__).parent / "output" / "01_architecture_overview"

def generate():
    graph_attr = {
        "fontsize": "20",
        "bgcolor": "white",
        "pad": "0.5",
        "splines": "spline",
    }
    
    with Diagram(
        "Mox EDA - TigerBeetle-Inspired Architecture",
        show=False,
        filename=str(OUTPUT),
        direction="TB",
        graph_attr=graph_attr,
    ):
        # Clients
        with Cluster("Clients"):
            web = Client("Web App")
            mobile = Client("Mobile")
            api_client = Client("API Client")
        
        # Load Balancer
        lb = Nginx("Load Balancer")
        
        # The Single Binary Cluster
        with Cluster("Mox Cluster (3-5 Replicas)"):
            with Cluster("Replica 1 (Leader)"):
                node1 = Server("mox-node")
                with Cluster("Components"):
                    api1 = Firewall("API Layer")
                    sm1 = Rust("State Machine")
                    raft1 = Rust("Raft Consensus")
                    wal1 = Storage("WAL + LSM")
            
            with Cluster("Replica 2 (Follower)"):
                node2 = Server("mox-node")
                wal2 = Storage("WAL + LSM")
            
            with Cluster("Replica 3 (Follower)"):
                node3 = Server("mox-node")
                wal3 = Storage("WAL + LSM")
        
        # Connections
        web >> lb
        mobile >> lb
        api_client >> lb
        
        lb >> api1
        
        api1 >> sm1
        sm1 >> raft1
        raft1 >> wal1
        
        # Raft replication
        raft1 >> Edge(label="replicate", style="dashed") >> node2
        raft1 >> Edge(label="replicate", style="dashed") >> node3

if __name__ == "__main__":
    generate()
    print(f"Generated: {OUTPUT}.png")
