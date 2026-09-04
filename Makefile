NAME := KorSign
IPA_NAME := KorSign
PLATFORM := iphoneos
SCHEMES := KorSign
TMP := $(TMPDIR)/$(NAME)
STAGE := $(TMP)/stage
APP := $(TMP)/Build/Products/Release-$(PLATFORM)
CERT_JSON_URL := https://ryuksign-install.ryuksign.workers.dev/pack.json

.PHONY: all deps clean $(SCHEMES)

all: $(SCHEMES)

clean:
	rm -rf $(TMP)
	rm -rf packages
	rm -rf Payload

deps:
	python3 tools/refresh_server_deps.py --url "$(CERT_JSON_URL)" --output deps

$(SCHEMES): deps
	xcodebuild \
	    -project KorSign.xcodeproj \
	    -scheme "$@" \
	    -configuration Release \
	    -arch arm64 \
	    -sdk $(PLATFORM) \
	    -derivedDataPath $(TMP) \
	    -skipPackagePluginValidation \
	    CODE_SIGNING_ALLOWED=NO \
	    ALWAYS_EMBED_SWIFT_STANDARD_LIBRARIES=NO \
	    OTHER_CFLAGS="-ffile-prefix-map=$(CURDIR)=/src/KorSign" \
	    OTHER_CPLUSPLUSFLAGS="-ffile-prefix-map=$(CURDIR)=/src/KorSign"

	rm -rf Payload
	rm -rf $(STAGE)/
	mkdir -p $(STAGE)/Payload

	mv "$(APP)/$@.app" "$(STAGE)/Payload/$@.app"

	chmod -R 0755 "$(STAGE)/Payload/$@.app"
	codesign --force --sign - --timestamp=none "$(STAGE)/Payload/$@.app"

	cp deps/server.crt deps/server.pem deps/commonName.txt "$(STAGE)/Payload/$@.app/"

	rm -rf "$(STAGE)/Payload/$@.app/_CodeSignature"
	ln -sf "$(STAGE)/Payload" Payload
	
	python3 tools/package_ipa.py --stage "$(STAGE)" --output "packages/$(IPA_NAME).ipa" --deps deps
