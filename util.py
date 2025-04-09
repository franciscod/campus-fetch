import re
from bs4 import BeautifulSoup
from unicodedata import normalize

import unidecode

_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},:]+')

def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug."""
    result = []
    for word in _punct_re.split(unidecode.unidecode(text).lower()):
        word = normalize('NFKD', word)
        if word:
            result.append(word)

    return delim.join(result)


def log(*args, **kwargs):
    print(*args, 
          **kwargs,
          # file=sys.stderr,
          )


def css_find(res, selector):
    soup = BeautifulSoup(res.text, "html.parser")
    return soup.css.select(selector)


def css_find1(res, selector):
    tags = css_find(res, selector)
    if tags[:1]:
        return tags[0]
    return None
