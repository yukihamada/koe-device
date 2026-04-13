CC      = gcc
CFLAGS  = -O2 -Wall -Wextra -std=c11 \
           $(shell pkg-config --cflags portaudio-2.0 libcurl)
LDFLAGS = $(shell pkg-config --libs   portaudio-2.0 libcurl) -lpthread -lm

BIN     = koe-amp
SRC     = koe-amp.c
SERVICE = koe-amp.service
SVCDIR  = /etc/systemd/system
BINDIR  = /usr/local/bin
CFGDIR  = /etc/koe

.PHONY: all install uninstall clean

all: $(BIN)

$(BIN): $(SRC)
	$(CC) $(CFLAGS) $< -o $@ $(LDFLAGS)

# sudo make install — compile, deploy binary, enable + start systemd service
install: $(BIN)
	install -m 755 $(BIN)     $(BINDIR)/$(BIN)
	install -m 644 $(SERVICE) $(SVCDIR)/$(SERVICE)
	@# Create config dir with sane defaults if not present
	@mkdir -p $(CFGDIR)
	@[ -f $(CFGDIR)/server    ] || echo "https://koe.live" > $(CFGDIR)/server
	@[ -f $(CFGDIR)/room      ] || echo "main"             > $(CFGDIR)/room
	@[ -f $(CFGDIR)/device_id ] || echo "koe-amp-$$(hostname | tr -dc 'a-z0-9' | head -c8)" > $(CFGDIR)/device_id
	systemctl daemon-reload
	systemctl enable $(SERVICE)
	systemctl restart $(SERVICE)
	@echo ""
	@echo "✓ koe-amp installed and running"
	@echo "  Logs:   journalctl -u koe-amp -f"
	@echo "  Config: $(CFGDIR)/"

uninstall:
	-systemctl stop    $(SERVICE)
	-systemctl disable $(SERVICE)
	-rm -f $(SVCDIR)/$(SERVICE) $(BINDIR)/$(BIN)
	systemctl daemon-reload

clean:
	rm -f $(BIN)
