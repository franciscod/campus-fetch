download: venv/done downloads
	venv/bin/python3 dl.py
	cd downloads; git add .; git commit -m "download"

venv/done: requirements.txt
	python3 -m venv venv
	venv/bin/pip install -r requirements.txt
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

.PHONY: download clean todo
