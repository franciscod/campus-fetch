import hashlib
import os
import random
import shutil
import string
import sys

from pathlib import Path

from html2text import HTML2Text
from requests_html import HTMLSession

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
                name = ''.join(random.sample(string.ascii, 8))
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
        self._course_name = course_name
        self.rename_old()

        # get course main page
        res = self.get('course/view.php?id=%s' % course_id)

        # handle policy
        if 'policy' in res.url:
            res = self.agree_policy(res)

        topics = res.html.find('ul.topics > li.section')
        if len(topics) == 1:
            self.fetch_section_tab(res)
        else:
            for topic in topics:
                self.fetch_section_li(res, topic)

    def base_path(self):
        return (Path(DOWNLOADS_DIR) / slugify(self._course_name)).resolve()

    def path(self, filename, *dir_parts):
        path = os.path.join(self.base_path(), *dir_parts)
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, filename)

    def rename_old(self):
        path = self.base_path()
        old_path = os.path.join(OLD_BASE_DIR, path)
        if os.path.isdir(path):
            if os.path.isdir(old_path):
                shutil.rmtree(old_path)
            os.makedirs(old_path, exist_ok=True)
            os.rename(path, old_path)

    def fetch_section_li(self, res, topic):
        title = topic.find('.content .sectionname', first=True).text
        content = topic.find('.content .summary', first=True)
        self.fetch_section(res, title, content)

    def fetch_section_tab(self, res):
        if res.url in self._processed_urls:
            return
        self._processed_urls.add(res.url)

        for a in res.html.find('.nav-tabs li a'):
            href = a.attrs.get('href')
            if href:
                self.fetch_section_tab(self._session.get(href))

        if res.html.find('.errormessage'):
            return
        title = res.html.find('.active span', first=True).text
        content = res.html.find('#region-main .content', first=True)
        self.fetch_section(res, title, content)

    def fetch_section(self, res, title, content):
        h = HTML2Text(baseurl='')
        h.ul_item_mark = '-'
        md_content = h.handle(content.html)
        if md_content.strip() != '':
            with open(self.path(slugify(title) + '.md'), 'w') as f:
                f.write('# ' + title + '\n([fuente](' + res.url + '))\n---\n')
                f.write(md_content)

        for a in content.find('a'):
            href = a.attrs.get('href')
            if not href:
                continue

            if '/mod/resource' in href:
                self.fetch_resource(href, slugify(title))

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


if __name__ == '__main__':
    dl = MoodleDL()
    dl.login(username=DNI, password=PASSWORD)

    for args in MATERIAS:
        dl.fetch_course(*args)
