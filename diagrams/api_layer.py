#!/usr/bin/env python3
"""
Mox EDA - API Layer Diagram

Shows the HTTP, WebSocket, and Webhook interfaces.
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.programming.language import Rust
from diagrams.onprem.client import Client
from diagrams.generic.network import Firewall
from diagrams.onprem.network import Internet
from pathlib import Path

OUTPUT = Path(__file__).parent / "output" / "06_api_layer"

def generate():
    graph_attr = {
        "fontsize": "16",
        "bgcolor": "white",
        "pad": "0.5",
    }
    
    with Diagram(
        "API Layer - HTTP, WebSocket, Webhooks",
        show=False,
        filename=str(OUTPUT),
        direction="LR",
        graph_attr=graph_attr,
    ):
        with Cluster("External"):
            web_client = Client("Web App")
            mobile = Client("Mobile")
            stripe_wh = Internet("Stripe\nWebhooks")
            tiktok_wh = Internet("TikTok\nWebhooks")
        
        with Cluster("API Gateway (Axum)"):
            with Cluster("Middleware Stack"):
                trace = Rust("Tracing")
                auth = Rust("Auth")
                rate = Rust("Rate Limit")
            
            with Cluster("REST Endpoints"):
                talents = Rust("/api/talents")
                campaigns = Rust("/api/campaigns")
                contracts = Rust("/api/contracts")
            
            with Cluster("Real-time"):
                ws = Rust("WebSocket\n/ws")
            
            with Cluster("Webhooks"):
                wh_handler = Rust("/webhooks/*")
        
        with Cluster("State Machine"):
            sm = Rust("StateMachine")
        
        # Connections
        web_client >> trace >> auth >> rate
        mobile >> trace
        
        rate >> talents >> sm
        rate >> campaigns >> sm
        rate >> contracts >> sm
        
        web_client >> ws >> sm
        
        stripe_wh >> wh_handler >> sm
        tiktok_wh >> wh_handler >> sm
        
        # Response path
        sm >> Edge(label="events", style="dashed") >> ws

if __name__ == "__main__":
    generate()
    print(f"Generated: {OUTPUT}.png")
