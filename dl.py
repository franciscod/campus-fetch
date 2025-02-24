import hashlib
import os
import random
import shutil
import string
import sys
import urllib.parse

from pathlib import Path

from html2text import HTML2Text
from requests import Session
from bs4 import BeautifulSoup

from config import MATERIAS

from util import slugify
from util import log

try:
    from secret import DNI, PASSWORD
except:
    log("el archivo secret.py debería tener la definicion de DNI y PASSWORD")
    log("(ver el archivo secret.example.py)")
    sys.exit(1)


HASH_BUF_SIZE = 65536
OLD_BASE_DIR = '.old'
DOWNLOADS_DIR = 'downloads'

class MoodleDL:
    def __init__(self, base_url='https://campus12-24.exactas.uba.ar/'):
        self._session = Session()
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

    def css_find(self, res, selector):
        soup = BeautifulSoup(res.text, "html.parser")
        return soup.css.select(selector)

    def css_find1(self, res, selector):
        tags = self.css_find(res, selector)
        if tags[:1]:
            return tags[0]
        return None

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
            print('File not previously downloaded', filename, url)
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
        if url in self._processed_urls:
            return

        self._processed_urls.add(url)
        log("download_file", url, name)

        if name is None:
            # ???
            pass

        if name is not None:
            filename = self.path(name, 'files_' + basedir)
            old_filename = self.old_path(name, 'files_' + basedir)
            if self.etag_sha1_matches(url, old_filename):
                new_parent, _ = os.path.split(filename)
                os.makedirs(new_parent, exist_ok=True)
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

        Path(filename).parent.mkdir(parents=True, exist_ok=True)
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
            'sesskey': self.css_find1(res, '#region-main form input[name=sesskey]').attrs['value'],
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
        sections = self.css_find(res, 'ul.topics > li.section')
        self.recurse_in_tabs(res)
        # if len(sections) == 1:
        #     pass
        # else:
        #     print(f"huh, en lugar de 1 section hay {len(sections)=}")
        #     raise NotImplementedError

    def base_path(self):
        return Path(DOWNLOADS_DIR) / slugify(self._course_name)

    def old_base_path(self):
        path = self.base_path()
        return (path.parent / OLD_BASE_DIR / path.name).resolve()

    def path(self, filename, *dir_parts):
        path = os.path.join(self.base_path().resolve(), *dir_parts)
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, filename)

    def old_path(self, filename, *dir_parts):
        path = os.path.join(self.old_base_path(), *dir_parts)
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, filename)

    def rename_old(self):
        path = self.base_path().resolve()
        old_path = self.old_base_path()

        if os.path.isdir(path):
            if os.path.isdir(old_path):
                shutil.rmtree(old_path)
            os.makedirs(old_path, exist_ok=True)
            os.rename(path, old_path)

    def recurse_in_tabs(self, res):
        if res.url in self._processed_urls:
            return
        self._processed_urls.add(res.url)

        log("recurse_in_tabs", res.url)

        for a in self.css_find(res, '.nav-tabs li a'):
            href = a.attrs.get('href')
            if href and href not in self._processed_urls:
                self._processed_urls.add(res.url)
                newres = self._session.get(href)
                self.recurse_in_tabs(newres)

        if self.css_find(res, '.errormessage'):
            return
        self.parse_section(res)

    def parse_content(self, res, title):
        contents = self.css_find(res, '#region-main .content')
        if contents is None:
            contents = self.css_find(res, '#region-main [role="main"]')

        if contents is None:
            contents = self.css_find(res, '#region-main [role="main"]')

        content = None
        if len(contents) == 0:
            log("empty content")
        elif len(contents) == 1:
            content = contents[0]
        else:
            # hay muchos sections, pero normalmente hay uno solo..

            # HACK para proba
            img = contents[0].find('img')
            if img:
                src = img.get('src')
                if src == 'https://campus12-24.exactas.uba.ar/pluginfile.php/581414/course/section/66736/fondo.png':
                    # wtf, proba tiene un section adicional para poner un logo en todas las paginas
                    # vamos al segundo section
                    content = contents[1]

            if content == None:
                raise NotImplementedError
                # ahora que lo pienso, capaz se pueden parsear
                # todos los sections y concatenarlos?

        extra = []
        if content:
            for iframe in self.css_find(content, 'iframe'):
                src = iframe.attrs.get('src')
                if not src:
                    continue
                extra.append("- iframe: URL=" + src)

        h = HTML2Text(baseurl='')
        h.ul_item_mark = '-'
        md_content = h.handle(str(content))

        if extra:
            md_extra_content = '\n\n'.join(extra)
            md_content += md_extra_content

        if md_content.strip() != '':
            with open(self.path(slugify(title) + '.md'), 'w', encoding='utf-8') as f:
                f.write('# ' + title + '\n([fuente](' + res.url + '))\n---\n')
                f.write(md_content)

        return content


    def parse_section(self, res):
        log("parse_section", res.url)
        title = self.css_find1(res, '.breadcrumb li:last-child span a span').text
        content = self.parse_content(res, title)

        for a in content.find_all('a'):
            href = a.attrs.get('href')
            if not href:
                continue

            section_prefix = "https://campus12-24.exactas.uba.ar/course/view.php?id={}&section=".format(self._course_id)

            if '/mod/resource' in href:
                self.fetch_resource(href, slugify(title))
            elif '/mod/forum' in href:
                self.fetch_forum(href)
            elif '/mod/url' in href:
                self.fetch_shortened_url(href, a.text)
            elif '/mod/page' in href:
                self.fetch_page_resource(href)
            elif '/mod/folder' in href:
                self.fetch_folder(href, slugify(title))
            elif 'pluginfile.php/' in href:
                self.fetch_pluginfile(href, slugify(title))
            elif href.startswith(section_prefix):
                self.fetch_section(href)
            else:
                log("unhandled resource", href, title)

        self.parse_page_fp_filename(content, slugify(title))


    def parse_page_fp_filename(self, content, basedir):
        if content is None:
            return

        for a in content.find_all('a'):
            href = a.attrs.get('href')

            if href is None or "mod_folder" not in href:
                continue

            dl_url = href
            dl_name = urllib.parse.unquote(href.split('mod_folder/content/0/')[1].split('?')[0])

            self.download_file(dl_url, dl_name, basedir)


    def fetch_folder(self, url, basedir):
        if url in self._processed_urls:
            return

        self._processed_urls.add(url)

        res = self.get(url)
        title = self.css_find1(res, '.breadcrumb li:last-child span a span').text
        basedir += "/" + slugify(title)

        content = self.parse_content(res, title)

        self.parse_page_fp_filename(content, basedir)


    def fetch_forum(self, url):
        if url in self._processed_urls:
            return
        self._processed_urls.add(url)
        log("fetch_forum", url)

        res = self.get(url)
        for tr in self.css_find(res, '.discussion'):
            a = self.css_find1(tr, '.topic a')
            if a:
                href = a.attrs['href']
                self.fetch_discuss(href)


    def fetch_discuss(self, url):
        if url in self._processed_urls:
            return
        self._processed_urls.add(url)
        log("fetch_discuss", url)

        out = ""

        res = self.get(url)
        for post in self.css_find(res, '.forumpost'):
            h = HTML2Text(baseurl='')
            h.ul_item_mark = '-'
            md_post = h.handle(post.html)
            out += md_post + '\n\n'

        forum = self.css_find1(res, 'h2').text
        title = self.css_find1(res, 'h3.discussionname').text

        desired_path = f'discuss/{slugify(forum)}/'
        name = f'{slugify(title)}.md'
        ensured_path = self.path(name, desired_path)

        with open(ensured_path, 'w', encoding='utf-8') as f:
            f.write('# ' + title + '\n([fuente](' + res.url + '))\n---\n')
            f.write(out)


    def fetch_page_resource(self, url):
        if url in self._processed_urls:
            return

        self._processed_urls.add(url)

        res = self.get(url)
        self.parse_page_resource(res)


    def parse_page_resource(self, res):
        title = self.css_find1(res, '.breadcrumb li:last-child span a span').text
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


    def fetch_pluginfile(self, url, basedir):
        key = ("res", url)
        if key in self._processed_urls:
            return
        self._processed_urls.add(key)
        log("fetch_pluginfile", url, basedir)

        self.download_file(url, url.split('/')[-1], basedir)

    def fetch_resource(self, url, basedir):
        key = ("res", url)
        if key in self._processed_urls:
            return
        self._processed_urls.add(key)
        log("fetch_resource", url)

        res = self.get(url)


        def resource_url_name():
            content_disp = res.headers.get('Content-Disposition')
            if content_disp:
                if content_disp.startswith("inline; filename="):
                    filename = content_disp[17:]
                    if filename[0] == filename[-1] == '"':
                        filename = filename[1:-1]

                    # TODO: grab this from somewhere else -- meta in html, headers, etc
                    IMPLICIT_ENCODING = 'latin1'

                    filename = bytes(filename, IMPLICIT_ENCODING).decode() 
                    return url, filename

            # try 'regular' moodle resource download page
            a = self.css_find1(res, 'object a')
            if a:
                dl_url = href = a.attrs['href']
                dl_name = href.split('/')[-1]
                return dl_url, dl_name

            # try resourceimage page
            img = self.css_find1(res, 'img.resourceimage')
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

    def fetch_shortened_url(self, url, text):
        """Fetches an url that's behind a "shortened" URL, that looks like
           /mod/url/view.php?id={} and then stores the destination url.
        """
        if url in self._processed_urls:
            return

        url_id = int(url.split('/mod/url/view.php?id=')[-1])

        self._processed_urls.add(url)

        log("fetch_shortened_url", url)

        hres = self.head(url)
        loc = hres.headers.get('Location')
        if loc:
            dest = loc
        else:
            res = self.get(url)
            dest = res.url

            workaround = self.css_find1(res, '.urlworkaround')
            if workaround:
                dest = workaround.find("a").attrs['href']

        path = (self.base_path() / "urls" / str(url_id))
        path.parent.mkdir(parents=True, exist_ok=True)
        if text.endswith("URL"):
            text = text[:-3]
        path.write_text('# {}\nURL="{}"'.format(text, dest))


if __name__ == '__main__':
    dl = MoodleDL()
    dl.login(username=DNI, password=PASSWORD)

    if 'section' in sys.argv:
        url = sys.argv[1+sys.argv.index('section')]
        dl._course_id = 9999
        dl._course_name = "oneshot"
        dl.fetch_section(url)
        exit(0)

    if 'resource' in sys.argv:
        url = sys.argv[1+sys.argv.index('resource')]
        dl._course_id = 9999
        dl._course_name = "oneshot"
        dl.fetch_resource(url, "oneshot_resource")
        exit(0)

    for args in MATERIAS:
        print("fetching", args)
        dl.fetch_course(*args)
