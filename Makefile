# comment this to use default python/pip
USE_VENV=1

ifdef USE_VENV
PIP = venv/bin/pip
PY  = venv/bin/python3
VENV_TARGET = venv/done
else
PIP = pip
PY  = python3
VENV_TARGET = 
endif

PY_SYS = python3

download: $(VENV_TARGET) downloads
	$(PY) dl.py
	cd downloads; git add .; git commit -m "download"

oneshot:
	$(PY) dl.py section 'https://campus12-24.exactas.uba.ar/course/view.php?id=3282&section=3'
	# $(PY) dl.py resource 'https://campus12-24.exactas.uba.ar/mod/resource/view.php?id=350539'

venv/done: requirements.txt
	$(PY_SYS) -m venv venv
	$(PIP) install -r requirements.txt
	touch venv/done

downloads:
	mkdir downloads; cd downloads; \
        git init && \
        echo '.old/' > .gitignore && \
        git add .gitignore && \
        git commit -m 'initial commit' --allow-empty

clean:
	rm -rf downloads

todo:
	grep -n -R TODO *.py || true

pudb:
	$(PY) -m pudb dl.py

.PHONY: download clean todo
