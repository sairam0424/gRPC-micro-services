FROM postgres:15

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/patroni/venv
RUN /opt/patroni/venv/bin/pip install patroni[etcd] psycopg2-binary

ENV PATH="/opt/patroni/venv/bin:$PATH"

# Run patroni directly using environment variables for configuration
ENTRYPOINT ["patroni"]
