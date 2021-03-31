download: venv/done
	venv/bin/python3 dl.py
	cd downloads; git add .; git commit -m "le"

venv/done: requirements.txt
	virtualenv -p python3 venv
	# python3 -m virtualenv venv
	venv/bin/pip install -r requirements.txt
	touch venv/done

clean:
	rm -rf downloads

.PHONY: download
