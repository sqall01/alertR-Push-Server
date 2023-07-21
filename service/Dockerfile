FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG ALERTR_UID=999
ARG ALERTR_GID=999

# install basics
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        ca-certificates \
        libmysqlclient-dev \
        libffi-dev \
        python3 \
        python3-dev \
        python3-pip \
        mysql-client \
        pkg-config \
        gcc \
        && \
    rm -rf /var/cache/apt /var/lib/apt/lists/*

RUN pip3 install bcrypt mysqlclient requests

ADD . /push_service

# Create alertr user and group
RUN groupadd --system --gid ${ALERTR_GID} alertr
RUN useradd --shell /usr/sbin/nologin --system --home /push_service --gid ${ALERTR_GID} --uid ${ALERTR_UID} alertr

RUN mkdir /push_service/socket && chown -R alertr:alertr push_service && chmod 755 /push_service/push_server.py

WORKDIR /push_service

# Switch to user
USER alertr:alertr

ENTRYPOINT ["/push_service/push_server.py"]
