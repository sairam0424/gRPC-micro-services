import os

# etcd3 (unmaintained since 2020) ships generated _pb2.py stubs built with a
# pre-3.19 protoc. Modern protobuf's default upb/C++ backend refuses to load
# those stubs ("TypeError: Descriptors cannot be created directly"), which
# breaks importing app.consensus (and transitively app.main) as soon as
# etcd3 is imported. Forcing the pure-Python protobuf implementation lets
# the legacy-style generated code load under the same protobuf install.
# Must be set before etcd3/app.main are imported by any test module, so it
# lives in conftest.py, which pytest loads before collecting test files.
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
