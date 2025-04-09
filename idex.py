import sys

from bs4 import BeautifulSoup

try:
    from secret import IDEX, IDEX_PASSWORD
except:
    print("el archivo secret.py debería tener la definicion de IDEX y IDEX_PASSWORD", file=sys.stderr)
    print("(ver el archivo secret.example.py)", file=sys.stderr)
    sys.exit(1)


def css_find(res, selector):
    soup = BeautifulSoup(res.text, "html.parser")
    return soup.css.select(selector)


def css_find1(res, selector):
    tags = css_find(res, selector)
    if tags[:1]:
        return tags[0]
    return None


def idex_login(session):
    url = "https://campus.exactas.uba.ar/login/index.php"
    res = session.get(url)

    btn = css_find1(res, ".login-identityprovider-btn")
    url = btn.attrs.get('href')
    res = session.get(url)

    form = css_find1(res, "#kc-form-login")
    res = session.post(form.attrs.get('action'), data={
        'username': IDEX,
        'password': IDEX_PASSWORD,
    })

    # session should have the proper cookies now

    return res


if __name__ == "__main__":
    from requests import Session
    sess = Session()
    print(idex_login(sess).text)
