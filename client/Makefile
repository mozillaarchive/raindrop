JAVA =? java
TOOLS = ../tools

YUICOMPRESSOR=$(TOOLS)/bin/yuicompressor
HTMLCOMPRESSOR=$(TOOLS)/bin/htmlcompressor

JS_FILES=$(shell find . -name '*.js' | grep -v bespin )
JS_SOURCES=$(JS_FILES:.js=.js.min)

CSS_FILES=$(shell find . -name '*.css' | grep -v bespin )
CSS_SOURCES=$(CSS_FILES:.css=.css.min)

HTML_FILES=$(shell find . -name '*.html' | grep -v bespin )
HTML_SOURCES=$(HTML_FILES:.html=.html.min)

MINIFY_SOURCES=$(HTML_SOURCES) $(JS_SOURCES) $(CSS_SOURCES)

all: $(MINIFY_SOURCES)

%.js.min: %.js Makefile
	$(YUICOMPRESSOR) --type js -o $@ $< || rm -f $@

%.css.min: %.css Makefile
	$(YUICOMPRESSOR) --type css -o $@ $< || rm -f $@

%.html.min: %.html Makefile
	$(HTMLCOMPRESSOR) --remove-quotes --remove-intertag-spaces --compress-js --compress-css -o $@ $<  || rm -f $@

