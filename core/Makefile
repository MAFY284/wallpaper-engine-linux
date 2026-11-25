# Makefile del motor nativo wel-wallpaperd
# Requiere: gcc, wayland-scanner, pkg-config, libmpv-dev, libwayland-dev, libegl1-mesa-dev

CC       := gcc
PKGS     := mpv egl wayland-client wayland-egl
CFLAGS   := -O2 -Wall -Wextra -std=c11 $(shell pkg-config --cflags $(PKGS))
LDLIBS   := $(shell pkg-config --libs $(PKGS)) -lm

GEN      := src/generated
LS_XML   := protocol/wlr-layer-shell-unstable-v1.xml
XO_XML   := protocol/xdg-output-unstable-v1.xml
XS_XML   := /usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml
LS_C     := $(GEN)/wlr-layer-shell-protocol.c
LS_H     := $(GEN)/wlr-layer-shell-unstable-v1-client-protocol.h
XO_C     := $(GEN)/xdg-output-protocol.c
XO_H     := $(GEN)/xdg-output-unstable-v1-client-protocol.h
XS_C     := $(GEN)/xdg-shell-protocol.c
XS_H     := $(GEN)/xdg-shell-client-protocol.h

BIN      := ../bin/wel-wallpaperd

.PHONY: all clean

all: $(BIN)

$(GEN):
	mkdir -p $(GEN)

$(LS_C) $(LS_H) &: $(LS_XML) | $(GEN)
	wayland-scanner private-code $< $(LS_C)
	wayland-scanner client-header $< $(LS_H)

$(XO_C) $(XO_H) &: $(XO_XML) | $(GEN)
	wayland-scanner private-code $< $(XO_C)
	wayland-scanner client-header $< $(XO_H)

$(XS_C) $(XS_H) &: $(XS_XML) | $(GEN)
	wayland-scanner private-code $< $(XS_C)
	wayland-scanner client-header $< $(XS_H)

$(BIN): src/wel-wallpaperd.c $(LS_C) $(LS_H) $(XO_C) $(XO_H) $(XS_C) $(XS_H)
	$(CC) $(CFLAGS) -o $@ src/wel-wallpaperd.c $(LS_C) $(XO_C) $(XS_C) $(LDLIBS)

clean:
	rm -f $(BIN) $(LS_C) $(LS_H) $(XO_C) $(XO_H) $(XS_C) $(XS_H)
