#!/usr/bin/env python3
"""
Mox EDA - Storage Engine Diagram

Shows the WAL, LSM Tree, and io_uring architecture.
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.generic.storage import Storage
from diagrams.generic.compute import Rack
from diagrams.programming.language import Rust
from diagrams.onprem.inmemory import Memcached
from pathlib import Path

OUTPUT = Path(__file__).parent / "output" / "02_storage_engine"

def generate():
    graph_attr = {
        "fontsize": "18",
        "bgcolor": "white",
        "pad": "0.5",
    }
    
    with Diagram(
        "Storage Engine - WAL + LSM Tree",
        show=False,
        filename=str(OUTPUT),
        direction="TB",
        graph_attr=graph_attr,
    ):
        # Commands come in
        cmd = Rust("Commands")
        
        with Cluster("Write Path"):
            with Cluster("Write-Ahead Log (WAL)"):
                wal_buffer = Memcached("WAL Buffer")
                wal_segment = Storage("WAL Segment\n(append-only)")
                checksum = Rust("CRC32C\nChecksum")
            
            iouring = Rust("io_uring\nDirect I/O")
        
        with Cluster("LSM Tree (State Materialization)"):
            memtable = Memcached("MemTable\n(in-memory)")
            
            with Cluster("SSTables (on disk)"):
                l0 = Storage("Level 0")
                l1 = Storage("Level 1")
                l2 = Storage("Level 2")
            
            compaction = Rust("Compaction")
        
        with Cluster("Read Path"):
            bloom = Rust("Bloom Filter")
            index = Storage("Block Index")
            query = Rust("Query")
        
        # Write path flow
        cmd >> wal_buffer
        wal_buffer >> checksum
        checksum >> wal_segment
        wal_segment >> iouring
        
        # LSM flow
        wal_buffer >> memtable
        memtable >> Edge(label="flush") >> l0
        l0 >> compaction >> l1
        l1 >> compaction >> l2
        
        # Read path
        query >> bloom
        bloom >> index
        index >> memtable

if __name__ == "__main__":
    generate()
    print(f"Generated: {OUTPUT}.png")
