import re
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
