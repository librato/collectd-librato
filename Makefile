PLUGIN = collectd-librato.py
PLUGIN_DIR = lib
VERSION := $(shell cat $(PLUGIN_DIR)/$(PLUGIN) | egrep ^'version =' | cut -d ' ' -f 3 | cut -d \" -f 2)
DEST_DIR = /opt/collectd-librato-$(VERSION)

install:
	@mkdir -p $(DEST_DIR)/$(PLUGIN_DIR)
	@cp $(PLUGIN_DIR)/$(PLUGIN) $(DEST_DIR)/$(PLUGIN_DIR)
	@echo "Installed collected-librato plugin, add this"
	@echo "to your collectd configuration to load this plugin:"
	@echo
	@echo '    <LoadPlugin "python">'
	@echo '        Globals true'
	@echo '    </LoadPlugin>'
	@echo
	@echo '    <Plugin "python">'
	@echo '        # $(PLUGIN) is at $(DEST_DIR)/$(PLUGIN_DIR)/$(PLUGIN)'
	@echo '        ModulePath "$(DEST_DIR)/$(PLUGIN_DIR)"'
	@echo
	@echo '        Import "collectd-librato"'
	@echo
	@echo '        <Module "collectd-librato">'
	@echo '            APIToken "1985481910fe29ab201302011054857292"'
	@echo '            Email    "joe@example.com"'
	@echo '        </Module>'
	@echo '    </Plugin>'
