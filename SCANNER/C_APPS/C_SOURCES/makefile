ODIR = ./objects
IDIR = ./includes
SDIR = ./source

CC = gcc
CFLAGS = -I$(IDIR) -Wall -Wextra `pkg-config --cflags glib-2.0 gio-2.0`

TARTGET_1 = mxsr_bin
TARTGET_2 = helper
TARTGET_3 = ntp_sync

INSTALL_DEST = /SCANNER/C_APPS

_DEPS := autoprep.h system_functions.h bluetooth.h md5.h
_SRCS:= bluetooth.c system_functions.c autoprep.c md5.c 
_OBJ := $(_SRCS:.c=.o)

OBJ := $(patsubst %,$(ODIR)/%,$(_OBJ))
DEPS := $(patsubst %,$(IDIR)/%,$(_DEPS))
SRC:= $(patsubst %,$(SDIR)/%,$(_SRCS))

LIBS = -lbluetooth -lsqlite3 -lwiringPi -pthread `pkg-config --libs glib-2.0 gio-2.0`

all:$(TARTGET_1) $(TARTGET_2) $(TARTGET_3)
	echo "Make done !"

$(TARTGET_3):
	$(CC) -o $@ ./others/ntp_sync.c
	
$(ODIR)/%.o:$(SDIR)/%.c $(DEPS)
	$(CC) $(CFLAGS) -c -o $@ $<
	
$(TARTGET_2):
	gcc -o $@ ./others/helper.c -lwiringPi

$(TARTGET_1):$(OBJ)
	$(CC) -o $@ $^ $(CFLAGS) $(LIBS) 
	
$(ODIR)/%.o:$(SDIR)/%.c $(DEPS)
	$(CC) $(CFLAGS) -c -o $@ $<
	
clean : 
	rm -f $(TARTGET_1) $(TARTGET_2) $(TARTGET_3) $(OBJ)
	echo "Clean done !"

install:
	rm -f $(INSTALL_DEST)/$(TARTGET_1)
	cp -f $(TARTGET_1) $(INSTALL_DEST)/
	chmod +x $(INSTALL_DEST)/$(TARTGET_1)
	rm -f $(INSTALL_DEST)/$(TARTGET_2)
	cp -f $(TARTGET_2) $(INSTALL_DEST)/
	chmod +x $(INSTALL_DEST)/$(TARTGET_2)
	rm -f $(INSTALL_DEST)/$(TARTGET_3)
	cp -f $(TARTGET_3) $(INSTALL_DEST)/
	chmod +x $(INSTALL_DEST)/$(TARTGET_3)
	echo "Installation done !"
uninstall:
	rm -f $(INSTALL_DEST)/$(TARTGET_1)
	rm -f $(INSTALL_DEST)/$(TARTGET_2)
	rm -f $(INSTALL_DEST)/$(TARTGET_3)