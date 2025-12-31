import subprocess
from locust import HttpUser, User, task, between, events
from pathlib import Path
from urllib.parse import urlparse
import random
import json
import grpc
import sys
import os
import time

import grpc.experimental.gevent as grpc_gevent
grpc_gevent.init_gevent()

from glossary_pb2 import (
    GetTermRequest,
    GetAllTermsRequest,
    CreateTermRequest,
    UpdateTermRequest,
    DeleteTermRequest,
    Term
)
from glossary_pb2_grpc import GlossaryServiceStub

DB_PATH = Path(__file__).parent.parent / "db" / "glossary.db"
SEED_SCRIPT = Path(__file__).parent.parent / "scripts" / "seed_db.py"

@events.test_start.add_listener
def seed_once(environment, **kwargs):
    try:
        subprocess.run(["python", str(SEED_SCRIPT), "--db", str(DB_PATH), "--count", "10000"], check=True)
        print("[INFO] Database seeded successfully (once for all users)")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Database seeding failed: {e}")

class RestUser(HttpUser):
    wait_time = between(1, 3)
    host = 'http://localhost:8000'

    @task(40)
    def get_all_terms(self):
        self.client.get("/terms", name="REST: GetAllTerms")

    @task(40)
    def get_term(self):
        keyword = str(random.randint(0, 10000))
        with self.client.get(f"/terms/{keyword}", catch_response=True, name="REST: GetTerm") as response:
            if response.status_code in (200, 404):
                response.success()

    @task(10)
    def create_term(self):
        keyword = str(random.randint(10001, 20000))
        payload = {"keyword": keyword, "description": "description"}
        self.client.post("/terms", json=payload, name="REST: CreateTerm")

    @task(5)
    def update_term(self):
        keyword = str(random.randint(0, 10000))
        payload = {"description": "updated description"}
        with self.client.put(f"/terms/{keyword}", json=payload, catch_response=True, name="REST: UpdateTerm") as response:
            if response.status_code in (200, 404):
                response.success()

    @task(5)
    def delete_term(self):
        keyword = str(random.randint(0, 10000))
        with self.client.delete(f"/terms/{keyword}", catch_response=True, name="REST: DeleteTerm") as response:
            if response.status_code in (200, 404):
                response.success()

class GrpcUser(User):
    wait_time = between(1, 3)
    host = 'localhost:50051'

    def on_start(self):
        options = [
            ('grpc.max_receive_message_length', 100 * 1024 * 1024),
            ('grpc.max_send_message_length', 100 * 1024 * 1024),
            ('grpc.default_timeout_ms', 60000),
            ('grpc.keepalive_time_ms', 10000),
            ('grpc.keepalive_timeout_ms', 5000),
            ('grpc.keepalive_permit_without_calls', True),
            ('grpc.http2.max_pings_without_data', 0),
            ('grpc.enable_http_proxy', False)
        ]
        self.channel = grpc.insecure_channel(self.host)
        self.stub = GlossaryServiceStub(channel=self.channel)
      
    def log_event(self, start_time, name, exception):
        total_time = int((time.time() - start_time) * 1000)
        self.environment.events.request.fire(request_type="grpc",
                                             name=name,
                                             response_time=total_time,
                                             response_length=0,
                                             exception=exception)

    @task(40)
    def get_all_terms(self):
        start_time = time.time()
        success = True
        error_msg = ""

        try:
            self.stub.GetAllTerms(GetAllTermsRequest())
        except grpc.RpcError as e:
            success = False
            error_msg = str(e)

        self.log_event(start_time, "gRPC: GetAllTerms", None if success else error_msg)

    @task(40)
    def get_term(self):
        start_time = time.time()
        success = True
        error_msg = ""
        keyword = f"term_{random.randint(0, 10000)}"

        try:
            self.stub.GetTerm(GetTermRequest(keyword=keyword), timeout=3)
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.NOT_FOUND:
              success = False
              error_msg = str(e)
        
        self.log_event(start_time, "gRPC: GetTerm", None if success else error_msg)

    @task(10)
    def create_term(self):
        start_time = time.time()
        success = True
        error_msg = ""
        keyword = f"new_{random.randint(10001, 20000)}"
        
        try:
            self.stub.CreateTerm(CreateTermRequest(keyword=keyword, description="dynamic description"), timeout=3)
        except grpc.RpcError as e:
            success = False
            error_msg = str(e)
        
        self.log_event(start_time, "gRPC: CreateTerm", None if success else error_msg)

    @task(5)
    def update_term(self):
        start_time = time.time()
        success = True
        error_msg = ""
        keyword = f"term_{random.randint(0, 10000)}"

        try:
            self.stub.UpdateTerm(UpdateTermRequest(keyword=keyword, description="updated description"), timeout=3)
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.NOT_FOUND:
                success = False
                error_msg = str(e)
        
        self.log_event(start_time, "gRPC: UpdateTerm", None if success else error_msg)

    @task(5)
    def delete_term(self):
        start_time = time.time()
        success = True
        error_msg = ""
        keyword = f"term_{random.randint(0, 10000)}"
        try:
            self.stub.DeleteTerm(DeleteTermRequest(keyword=keyword), timeout=3)
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.NOT_FOUND:
                success = False
                error_msg = str(e)
        
        self.log_event(start_time, "gRPC: DeleteTerm", None if success else error_msg)

    def on_stop(self):
        if hasattr(self, 'channel'):
            self.channel.close()