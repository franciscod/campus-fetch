import sys

from util import css_find1

try:
    from secret import IDEX, IDEX_PASSWORD
except:
    print("el archivo secret.py debería tener la definicion de IDEX y IDEX_PASSWORD", file=sys.stderr)
    print("(ver el archivo secret.example.py)", file=sys.stderr)
    sys.exit(1)


def login(session):
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
    print(login(sess).text)
