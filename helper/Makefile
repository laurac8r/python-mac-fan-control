HELPER_NAME = com.macfancontrol.smcwrite
PLIST = $(HELPER_NAME).plist
INSTALL_DIR = /Library/PrivilegedHelperTools
PLIST_DIR = /Library/LaunchDaemons
BUILD_DIR = .build/release
HELPER_BIN = $(BUILD_DIR)/smcwrite
SIGN_IDENTITY ?= -

.PHONY: test build sign install uninstall clean reload

test:
	swift test

build:
	swift build -c release

sign: build
	codesign --force --sign "$(SIGN_IDENTITY)" $(HELPER_BIN)

install: sign
	sudo mkdir -p $(INSTALL_DIR)
	sudo cp $(HELPER_BIN) $(INSTALL_DIR)/$(HELPER_NAME)
	sudo chown root:wheel $(INSTALL_DIR)/$(HELPER_NAME)
	sudo chmod 544 $(INSTALL_DIR)/$(HELPER_NAME)
	sudo cp $(PLIST) $(PLIST_DIR)/$(PLIST)
	sudo chown root:wheel $(PLIST_DIR)/$(PLIST)
	sudo launchctl bootout system/$(HELPER_NAME) 2>/dev/null || true
	sudo launchctl bootstrap system $(PLIST_DIR)/$(PLIST)
	@echo "Helper installed and started."

uninstall:
	sudo launchctl bootout system/$(HELPER_NAME) 2>/dev/null || true
	sudo rm -f $(INSTALL_DIR)/$(HELPER_NAME)
	sudo rm -f $(PLIST_DIR)/$(PLIST)
	sudo rm -f /var/run/macfancontrol.sock
	@echo "Helper uninstalled."

reload:
	sudo launchctl bootout system/$(HELPER_NAME) 2>/dev/null || true
	sudo launchctl bootstrap system $(PLIST_DIR)/$(PLIST)

clean:
	swift package clean
	rm -rf .build
