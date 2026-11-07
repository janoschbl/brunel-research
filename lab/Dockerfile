FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential clang git autoconf automake libtool pkg-config \
    libglib2.0-dev libdbus-1-dev libudev-dev libreadline-dev libical-dev \
    python3 python3-venv python3-pip dbus socat bluez-utils iproute2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --depth 1 --branch 5.78 https://github.com/bluez/bluez.git bluez
WORKDIR /src/bluez
COPY patches/crypto-alg-names.patch /tmp/
RUN git apply /tmp/crypto-alg-names.patch
RUN ./bootstrap
RUN CC=clang CFLAGS="-fsanitize=address -fno-omit-frame-pointer -g -O1" \
    LDFLAGS="-fsanitize=address" \
    ./configure --prefix=/opt/bluez --disable-systemd --disable-udev \
    --disable-manpages --disable-cups --disable-obex --disable-mesh \
    --disable-monitor --enable-debug --enable-testing
RUN make -j"$(nproc)" && make install
RUN mkdir -p /opt/bluez/libexec/bluetooth /opt/bluez/bin && \
    cp emulator/btvirt /opt/bluez/libexec/bluetooth/btvirt && \
    cp tools/btgatt-server /opt/bluez/bin/btgatt-server

RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir bumble
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV PATH="/opt/venv/bin:/opt/bluez/bin:/opt/bluez/libexec/bluetooth:$PATH"
ENV ASAN_OPTIONS="detect_leaks=0:abort_on_error=1:symbolize=1"
EXPOSE 9000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
