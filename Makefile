download: venv/done
	venv/bin/python3 dl.py
	cd downloads; git add .; git commit -m "download"

venv/done: requirements.txt
	virtualenv -p python3 venv
	# python3 -m virtualenv venv
	venv/bin/pip install -r requirements.txt
	touch venv/done

clean:
	rm -rf downloads

todo:
	grep -n -R TODO *.py || true

.PHONY: download clean todo
