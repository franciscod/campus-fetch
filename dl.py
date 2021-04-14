import hashlib
import os
import random
import shutil
import string
import sys

from pathlib import Path

from html2text import HTML2Text
from requests_html import HTMLSession

from youtube_dl import YoutubeDL

from config import MATERIAS

try:
    from config import DNI, PASSWORD
except:
    print("Asegurate de que el archivo config.py tenga "
          "definidas las variables DNI y PASSWORD!")
    sys.exit(1)

from util import slugify

HASH_BUF_SIZE = 65536
OLD_BASE_DIR = '.old'
DOWNLOADS_DIR = 'downloads'

class MoodleDL:
    def __init__(self, base_url='https://campus.exactas.uba.ar/'):
        self._session = HTMLSession()
        self._base_url = base_url
        self._processed_urls = set()

    def head(self, url, *args, **kwargs):
        if not url.startswith('http'):
            url = self._base_url + url

        return self._session.head(url, *args, **kwargs)

    def get(self, url, *args, **kwargs):
        if not url.startswith('http'):
            url = self._base_url + url

        return self._session.get(url, *args, **kwargs)

    def post(self, url, *args, **kwargs):
        if not url.startswith('http'):
            url = self._base_url + url

        return self._session.post(url, *args, **kwargs)

    def normalize_etag(self, etag):
        if etag.startswith('W/"') and etag.endswith('"'):
            return etag[3:-1]
        if etag.startswith('"') and etag.endswith('"'):
            return etag[1:-1]
        return etag

    def etag_sha1_matches(self, url, filename):
        # assumes ETag is the SHA1 of the file
        res = self.head(url, allow_redirects=True)
        etag = self.normalize_etag(res.headers.get('ETag'))

        if not etag:
            for r in res.history:
                etag = r.headers.get('ETag')
                if etag:
                    break
            else:
                print('No ETag on headers', filename, url)
                return False

        if not Path(filename).exists():
            # print('File not previously downloaded', filename, url)
            return False

        sha1 = hashlib.sha1()
        with open(filename, 'rb') as f:
            while True:
                data = f.read(HASH_BUF_SIZE)
                if not data:
                    break
                sha1.update(data)
        digest = sha1.hexdigest()

        if not digest == etag:
            print('Digest and ETag mismatch', filename, url)
            print(digest, etag)
            return False

        return True

    def download_file(self, url, name, basedir):
        if name is not None:
            filename = self.path(name, 'files_' + basedir)
            old_filename = os.path.join(OLD_BASE_DIR, filename)
            if self.etag_sha1_matches(url, old_filename):
                os.rename(old_filename, filename)
                return

        res = self.get(url)
        data = res.content

        if name is None:
            content_disp = res.headers.get('Content-Disposition')
            if content_disp:
                if content_disp.startswith("attachment; filename="):
                    cdname = content_disp[21:]
                    if cdname[0] == cdname[-1] == '"':
                        cdname = cdname[1:-1]
                    name = cdname
            if name is None:
                # TODO: this should be derived from some other information instead
                name = ''.join(random.sample(string.ascii_lowercase, 8))
            filename = self.path(name, 'files_' + basedir)

        with open(filename, 'wb') as f:
            f.write(data)

    def login(self, username, password):
        return self.post('login/index.php', data={
            'action': 'login',
            'username': username,
            'password': password,
        })

    def agree_policy(self, res):
        return self.post('user/policy.php', data={
            'sesskey': res.html.find('#region-main form input[name=sesskey]', first=True).attrs['value'],
            'agree': '1'
        })

    def fetch_course(self, course_name, course_id):
        self._course_id = course_id
        self._course_name = course_name
        self.rename_old()

        # get course main page
        res = self.get('course/view.php?id=%s' % course_id)

        # handle policy
        if 'policy' in res.url:
            res = self.agree_policy(res)

        self.parse_course(res)

    def parse_course(self, res):
        topics = res.html.find('ul.topics > li.section')
        if len(topics) == 1:
            self.recurse_in_tabs(res)
        else:
            raise NotImplementedError

    def base_path(self):
        return Path(DOWNLOADS_DIR) / slugify(self._course_name)

    def path(self, filename, *dir_parts):
        path = os.path.join(self.base_path().resolve(), *dir_parts)
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, filename)

    def rename_old(self):
        path = self.base_path().resolve()
        old_path = os.path.join(OLD_BASE_DIR, path)
        if os.path.isdir(path):
            if os.path.isdir(old_path):
                shutil.rmtree(old_path)
            os.makedirs(old_path, exist_ok=True)
            os.rename(path, old_path)

    def recurse_in_tabs(self, res):
        if res.url in self._processed_urls:
            return
        self._processed_urls.add(res.url)

        for a in res.html.find('.nav-tabs li a'):
            href = a.attrs.get('href')
            if href and href not in self._processed_urls:
                self._processed_urls.add(res.url)
                newres = self._session.get(href)
                self.recurse_in_tabs(newres)

        if res.html.find('.errormessage'):
            return
        self.parse_section(res)

    def parse_content(self, res, title):
        content = res.html.find('#region-main .content', first=True)
        if content is None:
            content = res.html.find('#region-main [role="main"]', first=True)

        h = HTML2Text(baseurl='')
        h.ul_item_mark = '-'
        md_content = h.handle(content.html)

        if md_content.strip() != '':
            with open(self.path(slugify(title) + '.md'), 'w') as f:
                f.write('# ' + title + '\n([fuente](' + res.url + '))\n---\n')
                f.write(md_content)

        return content


    def parse_section(self, res):
        title = res.html.find('.breadcrumb li:last-child span a span', first=True).text
        content = self.parse_content(res, title)

        for a in content.find('a'):
            href = a.attrs.get('href')
            if not href:
                continue

            section_prefix = "https://campus.exactas.uba.ar/course/view.php?id={}&section=".format(self._course_id)

            if '/mod/resource' in href:
                self.fetch_resource(href, slugify(title))
            elif '/mod/forum' in href:
                pass  # ignoring forum
            elif '/mod/url' in href:
                self.fetch_shortened_url(href, slugify(title))
            elif '/mod/page' in href:
                self.fetch_page_resource(href)
            elif href.startswith(section_prefix):
                self.fetch_section(href)
            else:
                print("unhandled resource", href, title, file=sys.stderr)


    def fetch_page_resource(self, url):
        if url in self._processed_urls:
            return

        self._processed_urls.add(url)

        res = self.get(url)
        self.parse_page_resource(res)


    def parse_page_resource(self, res):
        title = res.html.find('.breadcrumb li:last-child span a span', first=True).text
        content = self.parse_content(res, title)

    def fetch_section(self, url):
        """Fetches a section from an URL that should look like
           /course/view.php?id={}&section={}, and then calls parse_section.
        """
        if url in self._processed_urls:
            return

        self._processed_urls.add(url)

        res = self.get(url)

        self.parse_section(res)

    def fetch_resource(self, url, basedir):
        res = self.get(url)


        def resource_url_name():
            content_disp = res.headers.get('Content-Disposition')
            if content_disp:
                if content_disp.startswith("inline; filename="):
                    filename = content_disp[17:]
                    if filename[0] == filename[-1] == '"':
                        filename = filename[1:-1]
                    return url, filename

            # try 'regular' moodle resource download page
            a = res.html.find('object a', first=True)
            if a:
                dl_url = href = a.attrs['href']
                dl_name = href.split('/')[-1]
                return dl_url, dl_name

            # try resourceimage page
            img = res.html.find('img.resourceimage', first=True)
            if img:
                dl_url = href = img.attrs['src']
                dl_name = href.split('/')[-1]
                return dl_url, dl_name

            # try raw download
            return url, None

        dl_url, dl_name = resource_url_name()

        if not dl_url:
            return

        self.download_file(dl_url, dl_name, basedir)

    def fetch_shortened_url(self, url, section):
        """Fetches an url that's behind a "shortened" URL, that looks like
           /mod/url/view.php?id={} and then stores the destination url.
        """
        if url in self._processed_urls:
            return

        url_id = int(url.split('/mod/url/view.php?id=')[-1])

        self._processed_urls.add(url)

        res = self.get(url)

        dest = res.url

        workaround = res.html.find('.urlworkaround', first=True)
        if workaround:
            dest = workaround.find("a", first=True).attrs['href']

        path = (self.base_path() / "urls" / str(url_id))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dest)


if __name__ == '__main__':
    dl = MoodleDL()
    dl.login(username=DNI, password=PASSWORD)

    for args in MATERIAS:
        dl.fetch_course(*args)
