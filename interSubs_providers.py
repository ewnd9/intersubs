#! /usr/bin/env python

# v. 2.7
# Interactive subtitles for `mpv` for language learners.

import os
import subprocess
import sys
import random
import re
import time
import requests
import threading
import queue
import calendar
import math
import base64
import numpy
import ast

from bs4 import BeautifulSoup

from urllib.parse import quote
from json import loads

import warnings
from six.moves import urllib

pth = os.path.expanduser('~/.config/mpv/scripts/')
os.chdir(pth)
import interSubs_config as config

pons_combos = [
    'enes',
    'enfr',
    'deen',
    'enpl',
    'ensl',
    'defr',
    'dees',
    'deru',
    'depl',
    'desl',
    'deit',
    'dept',
    'detr',
    'deel',
    'dela',
    'espl',
    'frpl',
    'itpl',
    'plru',
    'essl',
    'frsl',
    'itsl',
    'enit',
    'enpt',
    'enru',
    'espt',
    'esfr',
    'delb',
    'dezh',
    'enzh',
    'eszh',
    'frzh',
    'denl',
    'arde',
    'aren',
    'dade',
    'csde',
    'dehu',
    'deno',
    'desv',
    'dede',
    'dedx']

# returns ([[word, translation]..], [morphology = '', gender = ''])
# pons.com


def pons(word):
    if config.lang_from + config.lang_to in pons_combos:
        url = 'http://en.pons.com/translate?q=%s&l=%s%s&in=%s' % (
            quote(word), config.lang_from, config.lang_to, config.lang_from)
    else:
        url = 'http://en.pons.com/translate?q=%s&l=%s%s&in=%s' % (
            quote(word), config.lang_to, config.lang_from, config.lang_from)

    pairs = []
    fname = 'urls/' + url.replace('/', "-")
    try:
        p = open(fname).read().split('=====/////-----')
        try:
            word_descr = p[1].strip()
        except BaseException:
            word_descr = ''

        if len(p[0].strip()):
            for pi in p[0].strip().split('\n\n'):
                pi = pi.split('\n')
                pairs.append([pi[0], pi[1]])
    except BaseException:
        p = requests.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'}).text

        soup = BeautifulSoup(p, "lxml")
        trs = soup.find_all('dl')

        for tr in trs:
            try:
                tr1 = tr.find('dt').find('div', class_="source").get_text()
                tr1 = re.sub('\n|\r|\t', ' ', tr1)
                tr1 = re.sub(' +', ' ', tr1).strip()
                if not len(tr1):
                    tr1 = '-'

                tr2 = tr.find('dd').find('div', class_="target").get_text()
                tr2 = re.sub('\n|\r|\t', ' ', tr2)
                tr2 = re.sub(' +', ' ', tr2).strip()
                if not len(tr2):
                    tr2 = '-'
            except BaseException:
                continue

            pairs.append([tr1, tr2])

            if config.number_of_translations_to_save and len(
                    pairs) > config.number_of_translations_to_save:
                break

        try:
            word_descr = soup.find_all('h2', class_='')
            if '<i class="icon-bolt">' not in str(word_descr[0]):
                word_descr = re.sub('\n|\r|\t', ' ', word_descr[0].get_text())
                word_descr = re.sub(
                    ' +',
                    ' ',
                    word_descr).replace(
                    '&lt;',
                    '<').replace(
                    '&gt;',
                    '>').replace(
                    ' · ',
                    '·').replace(
                    ' , ',
                    ', ').strip()
            else:
                word_descr = ''
        except BaseException:
            word_descr = ''

        # extra check against double-writing from rouge threads
        if not os.path.isfile(fname):
            print('\n\n'.join(e[0] + '\n' + e[1]
                              for e in pairs), file=open(fname, 'a'))
            print('\n' + '=====/////-----' + '\n', file=open(fname, 'a'))
            print(word_descr, file=open(fname, 'a'))

    if len(word_descr):
        if word_descr.split(' ')[-1] == 'm':
            word_descr_gen = [word_descr[:-2], 'm']
        elif word_descr.split(' ')[-1] == 'f':
            word_descr_gen = [word_descr[:-2], 'f']
        elif word_descr.split(' ')[-1] == 'nt':
            word_descr_gen = [word_descr[:-3], 'nt']
        else:
            word_descr_gen = [word_descr, '']
    else:
        word_descr_gen = ['', '']

    return pairs, word_descr_gen

# https://github.com/ssut/py-googletrans


class TokenAcquirer(object):
    """Google Translate API token generator
    translate.google.com uses a token to authorize the requests. If you are
    not Google, you do have this token and will have to pay for use.
    This class is the result of reverse engineering on the obfuscated and
    minified code used by Google to generate such token.
    The token is based on a seed which is updated once per hour and on the
    text that will be translated.
    Both are combined - by some strange math - in order to generate a final
    token (e.g. 744915.856682) which is used by the API to validate the
    request.
    This operation will cause an additional request to get an initial
    token from translate.google.com.
    Example usage:
            >>> from googletrans.gtoken import TokenAcquirer
            >>> acquirer = TokenAcquirer()
            >>> text = 'test'
            >>> tk = acquirer.do(text)
            >>> tk
            950629.577246
    """

    RE_TKK = re.compile(r'tkk:\'(.+?)\'', re.DOTALL)
    RE_RAWTKK = re.compile(r'tkk:\'(.+?)\'', re.DOTALL)

    def __init__(self, tkk='0', session=None, host='translate.google.com'):
        self.session = session or requests.Session()
        self.tkk = tkk
        self.host = host if 'http' in host else 'https://' + host

    def rshift(self, val, n):
        """python port for '>>>'(right shift with padding)
        """
        return (val % 0x100000000) >> n

    def _update(self):
        """update tkk
        """
        # we don't need to update the base TKK value when it is still valid
        now = math.floor(int(time.time() * 1000) / 3600000.0)
        if self.tkk and int(self.tkk.split('.')[0]) == now:
            return

        r = self.session.get(self.host)

        raw_tkk = self.RE_TKK.search(r.text)
        if raw_tkk:
            self.tkk = raw_tkk.group(1)
            return

        # this will be the same as python code after stripping out a reserved
        # word 'var'
        code = unicode(self.RE_TKK.search(r.text).group(1)).replace('var ', '')
        # unescape special ascii characters such like a \x3d(=)
        if PY3:  # pragma: no cover
            code = code.encode().decode('unicode-escape')
        else:  # pragma: no cover
            code = code.decode('string_escape')

        if code:
            tree = ast.parse(code)
            visit_return = False
            operator = '+'
            n, keys = 0, dict(a=0, b=0)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    name = node.targets[0].id
                    if name in keys:
                        if isinstance(node.value, ast.Num):
                            keys[name] = node.value.n
                        # the value can sometimes be negative
                        elif isinstance(node.value, ast.UnaryOp) and \
                                isinstance(node.value.op, ast.USub):  # pragma: nocover
                            keys[name] = -node.value.operand.n
                elif isinstance(node, ast.Return):
                    # parameters should be set after this point
                    visit_return = True
                elif visit_return and isinstance(node, ast.Num):
                    n = node.n
                elif visit_return and n > 0:
                    # the default operator is '+' but implement some more for
                    # all possible scenarios
                    if isinstance(node, ast.Add):  # pragma: nocover
                        pass
                    elif isinstance(node, ast.Sub):  # pragma: nocover
                        operator = '-'
                    elif isinstance(node, ast.Mult):  # pragma: nocover
                        operator = '*'
                    elif isinstance(node, ast.Pow):  # pragma: nocover
                        operator = '**'
                    elif isinstance(node, ast.BitXor):  # pragma: nocover
                        operator = '^'
            # a safety way to avoid Exceptions
            clause = compile('{1}{0}{2}'.format(
                operator, keys['a'], keys['b']), '', 'eval')
            value = eval(clause, dict(__builtin__={}))
            result = '{}.{}'.format(n, value)

            self.tkk = result

    def _lazy(self, value):
        """like lazy evalution, this method returns a lambda function that
        returns value given.
        We won't be needing this because this seems to have been built for
        code obfuscation.
        the original code of this method is as follows:
           ... code-block: javascript
                   var ek = function(a) {
                        return function() {
                                return a;
                        };
                   }
        """
        return lambda: value

    def _xr(self, a, b):
        size_b = len(b)
        c = 0
        while c < size_b - 2:
            d = b[c + 2]
            d = ord(d[0]) - 87 if 'a' <= d else int(d)
            d = self.rshift(a, d) if '+' == b[c + 1] else a << d
            a = a + d & 4294967295 if '+' == b[c] else a ^ d

            c += 3
        return a

    def acquire(self, text):
        a = []
        # Convert text to ints
        for i in text:
            val = ord(i)
            if val < 0x10000:
                a += [val]
            else:
                # Python doesn't natively use Unicode surrogates, so account
                # for those
                a += [
                    math.floor((val - 0x10000) / 0x400 + 0xD800),
                    math.floor((val - 0x10000) % 0x400 + 0xDC00)
                ]

        b = self.tkk if self.tkk != '0' else ''
        d = b.split('.')
        b = int(d[0]) if len(d) > 1 else 0

        # assume e means char code array
        e = []
        g = 0
        size = len(text)
        while g < size:
            l = a[g]
            # just append if l is less than 128(ascii: DEL)
            if l < 128:
                e.append(l)
            # append calculated value if l is less than 2048
            else:
                if l < 2048:
                    e.append(l >> 6 | 192)
                else:
                    # append calculated value if l matches special condition
                    if (l & 64512) == 55296 and g + 1 < size and \
                            a[g + 1] & 64512 == 56320:
                        g += 1
                        # This bracket is important
                        l = 65536 + ((l & 1023) << 10) + (a[g] & 1023)
                        e.append(l >> 18 | 240)
                        e.append(l >> 12 & 63 | 128)
                    else:
                        e.append(l >> 12 | 224)
                    e.append(l >> 6 & 63 | 128)
                e.append(l & 63 | 128)
            g += 1
        a = b
        for i, value in enumerate(e):
            a += value
            a = self._xr(a, '+-a^+6')
        a = self._xr(a, '+-3^+b+-f')
        a ^= int(d[1]) if len(d) > 1 else 0
        if a < 0:  # pragma: nocover
            a = (a & 2147483647) + 2147483648
        a %= 1000000  # int(1E6)

        return '{}.{}'.format(a, a ^ b)

    def do(self, text):
        self._update()
        tk = self.acquire(text)
        return tk

# translate.google.com


def google(word):
    url = 'https://translate.google.com/translate_a/single?client=t&sl={lang_from}&tl={lang_to}&hl={lang_to}&dt=at&dt=bd&dt=ex&dt=ld&dt=md&dt=qca&dt=rw&dt=rm&dt=ss&dt=t&ie=UTF-8&oe=UTF-8&otf=1&pc=1&ssel=3&tsel=3&kc=2&q={word}'.format(
        lang_from=config.lang_from, lang_to=config.lang_to, word=quote(word))

    pairs = []
    fname = 'urls/' + url.replace('/', "-")
    try:
        p = open(fname).read().split('=====/////-----')
        try:
            word_descr = p[1].strip()
        except BaseException:
            word_descr = ''

        for pi in p[0].strip().split('\n\n'):
            pi = pi.split('\n')
            pairs.append([pi[0], pi[1]])
    except BaseException:
        acquirer = TokenAcquirer()
        tk = acquirer.do(word)

        url = '{url}&tk={tk}'.format(url=url, tk=tk)
        p = requests.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'}).text
        p = loads(p)

        try:
            pairs.append([p[0][0][0], p[0][0][1]])
        except BaseException:
            pass

        if p[1] is not None:
            for translations in p[1]:
                for translation in translations[2]:
                    try:
                        t1 = translation[5] + ' ' + translation[0]
                    except BaseException:
                        t1 = translation[0]

                    t2 = ', '.join(translation[1])

                    if not len(t1):
                        t1 = '-'
                    if not len(t2):
                        t2 = '-'

                    pairs.append([t1, t2])

        word_descr = ''
        # extra check against double-writing from rouge threads
        if not os.path.isfile(fname):
            print('\n\n'.join(e[0] + '\n' + e[1]
                              for e in pairs), file=open(fname, 'a'))
            print('\n' + '=====/////-----' + '\n', file=open(fname, 'a'))
            print(word_descr, file=open(fname, 'a'))

    return pairs, ['', '']

# reverso.net


def reverso(word):
    reverso_combos = {
        'ar': 'Arabic',
        'de': 'German',
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'he': 'Hebrew',
        'it': 'Italian',
        'nl': 'Dutch',
        'pl': 'Polish',
        'pt': 'Portuguese',
        'ro': 'Romanian',
        'ru': 'Russian'}

    if config.lang_from in reverso_combos and not config.lang_to not in reverso_combos:
        return [['Language code is not correct.', '']], ['', '']

    url = 'http://context.reverso.net/translation/%s-%s/%s' % (
        reverso_combos[config.lang_from].lower(), reverso_combos[config.lang_to].lower(), quote(word))

    pairs = []
    fname = 'urls/' + url.replace('/', "-")
    try:
        p = open(fname).read().split('=====/////-----')

        if len(p[0].strip()):
            for pi in p[0].strip().split('\n\n'):
                pi = pi.split('\n')
                pairs.append([pi[0], pi[1]])
    except BaseException:
        p = requests.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'}).text

        soup = BeautifulSoup(p, "lxml")
        trs = soup.find_all(class_=re.compile('translation.*ltr.*'))
        exmpls = soup.find_all(class_='example')

        tr_combined = []
        for tr in trs:
            tr_combined.append(tr.get_text().strip().replace('\n', ' '))

            if len(tr_combined) == 4:
                pairs.append(['-', ' :: '.join(tr_combined)])
                tr_combined = []

        for exmpl in exmpls:
            pairs.append([x.strip()
                          for x in exmpl.get_text().split('\n') if len(x.strip())])

        # extra check against double-writing from rouge threads
        if not os.path.isfile(fname):
            print('\n\n'.join(e[0] + '\n' + e[1]
                              for e in pairs), file=open(fname, 'a'))
            print('\n' + '=====/////-----' + '\n', file=open(fname, 'a'))

    return pairs, ['', '']

# linguee.com (unfinished; site blocks frequent requests)


def linguee(word):
    url = 'https://www.linguee.com/german-english/search?source=german&query=%s' % quote(
        word)

    pairs = []
    fname = 'urls/' + url.replace('/', "-")
    try:
        p = open(fname).read().split('=====/////-----')
        try:
            word_descr = p[1].strip()
        except BaseException:
            word_descr = ''

        for pi in p[0].strip().split('\n\n'):
            pi = pi.split('\n')
            pairs.append([pi[0], pi[1]])
    except BaseException:
        #p = open('/home/lom/d/1.html', encoding="ISO-8859-15").read()
        p = requests.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'}).text

        soup = BeautifulSoup(p, "lxml")
        trs = soup.find_all('div', class_="lemma featured")

        for tr in trs:
            pairs.append([tr.find_all('a')[0].get_text(), '-'])
            for tr2 in tr.find_all('a')[1:]:
                if len(tr2.get_text()):
                    # print(tr2.get_text())
                    pairs.append(['-', tr2.get_text()])
        word_descr = ''

        # extra check against double-writing from rouge threads
        if not os.path.isfile(fname):
            print('\n\n'.join(e[0] + '\n' + e[1]
                              for e in pairs), file=open(fname, 'a'))
            print('\n' + '=====/////-----' + '\n', file=open(fname, 'a'))
            print(word_descr, file=open(fname, 'a'))

    return pairs, ['', '']

# dict.cc


def dict_cc(word):
    url = 'https://%s-%s.dict.cc/?s=%s' % (
        config.lang_from, config.lang_to, quote(word))

    pairs = []
    fname = 'urls/' + url.replace('/', "-")
    try:
        p = open(fname).read().split('=====/////-----')
        try:
            word_descr = p[1].strip()
        except BaseException:
            word_descr = ''

        if len(p[0].strip()):
            for pi in p[0].strip().split('\n\n'):
                pi = pi.split('\n')
                pairs.append([pi[0], pi[1]])
    except BaseException:
        p = requests.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'}).text

        p = re.sub('<div style="float:right;color:#999">\d*</div>', '', p)
        p = re.sub(
            '<span style="color:#666;font-size:10px;padding:0 2px;position:relative;top:-3px">\d*</span>',
            '',
            p)

        soup = BeautifulSoup(p, "lxml")
        trs = soup.find_all('tr', id=re.compile('tr\d*'))

        for tr in trs:
            tr2 = tr.find_all('td', class_='td7nl')
            pairs.append([tr2[1].get_text(), tr2[0].get_text()])

            if config.number_of_translations_to_save and len(
                    pairs) > config.number_of_translations_to_save:
                break

        word_descr = ''

        # extra check against double-writing from rouge threads
        if not os.path.isfile(fname):
            print('\n\n'.join(e[0] + '\n' + e[1]
                              for e in pairs), file=open(fname, 'a'))
            print('\n' + '=====/////-----' + '\n', file=open(fname, 'a'))
            print(word_descr, file=open(fname, 'a'))

    return pairs, ['', '']

# redensarten-index.de


def redensarten(word):
    if len(word) < 3:
        return [], ['', '']

    url = 'https://www.redensarten-index.de/suche.php?suchbegriff=' + \
        quote(word) + '&bool=relevanz&gawoe=an&suchspalte%5B%5D=rart_ou&suchspalte%5B%5D=rart_varianten_ou&suchspalte%5B%5D=erl_ou&suchspalte%5B%5D=erg_ou'

    pairs = []
    fname = 'urls/' + url.replace('/', "-")
    try:
        p = open(fname).read().split('=====/////-----')
        try:
            word_descr = p[1].strip()
        except BaseException:
            word_descr = ''

        if len(p[0].strip()):
            for pi in p[0].strip().split('\n\n'):
                pi = pi.split('\n')
                pairs.append([pi[0], pi[1]])
    except BaseException:
        p = requests.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'})
        p.encoding = 'utf-8'
        p = p.text

        soup = BeautifulSoup(p, "lxml")

        for a in soup.find_all('a', class_='autosyn-icon'):
            a.decompose()

        try:
            table = soup.find_all('table', id='tabelle')[0]
            trs = table.find_all('tr')

            for tr in trs[1:]:
                tds = tr.find_all('td')
                if len(tds) > 1:
                    pairs.append([re.sub(' +', ' ', tds[0].get_text()).strip(),
                                  re.sub(' +', ' ', tds[1].get_text()).strip()])
        except BaseException:
            pass

        word_descr = ''

        # extra check against double-writing from rouge threads
        if not os.path.isfile(fname):
            print('\n\n'.join(e[0] + '\n' + e[1]
                              for e in pairs), file=open(fname, 'a'))
            print('\n' + '=====/////-----' + '\n', file=open(fname, 'a'))
            print(word_descr, file=open(fname, 'a'))

    return pairs, ['', '']

# leo.org


def leo(word):
    language = config.lang_from if config.lang_from != 'de' else config.lang_to

    url = "https://dict.leo.org/dictQuery/m-vocab/%sde/query.xml?tolerMode=nof&rmWords=off&rmSearch=on&searchLoc=0&resultOrder=basic&multiwordShowSingle=on&lang=de&search=%s" % (
        language, word)

    pairs = []
    fname = 'urls/' + url.replace('/', "-")
    try:
        p = open(fname).read().split('=====/////-----')
        try:
            word_descr = p[1].strip()
        except BaseException:
            word_descr = ''

        if len(p[0].strip()):
            for pi in p[0].strip().split('\n\n'):
                pi = pi.split('\n')
                pairs.append([pi[0], pi[1]])
    except BaseException:
        req = requests.get(url.format(lang=language))

        content = BeautifulSoup(req.text, "xml")
        pairs = []
        for section in content.sectionlist.findAll('section'):
            if int(section['sctCount']):
                for entry in section.findAll('entry'):
                    res0 = entry.find('side', attrs={'hc': '0'})
                    res1 = entry.find('side', attrs={'hc': '1'})
                    if res0 and res1:
                        line0 = re.sub('\s+', ' ', res0.repr.getText())
                        line1 = re.sub('\s+', ' ', res1.repr.getText())
                        line0 = line0.rstrip('|').strip()
                        line1 = line1.rstrip('|').strip()

                        if res0.attrs['lang'] == config.lang_from:
                            pairs.append([line0, line1])
                        else:
                            pairs.append([line1, line0])

        word_descr = ''
        # extra check against double-writing from rouge threads
        if not os.path.isfile(fname):
            print('\n\n'.join(e[0] + '\n' + e[1]
                              for e in pairs), file=open(fname, 'a'))
            print('\n' + '=====/////-----' + '\n', file=open(fname, 'a'))
            print(word_descr, file=open(fname, 'a'))

    return pairs, ['', '']

# offline dictionary with word \t translation


def tab_divided_dict(word):
    if word in offdict:
        tr = re.sub(
            '<.*?>',
            '',
            offdict[word]) if config.tab_divided_dict_remove_tags_B else offdict[word]
        tr = tr.replace('\\n', '\n').replace('\\~', '~')
        return [[tr, '-']], ['', '']
    else:
        return [], ['', '']

# morfix.co.il


def morfix(word):

    url = "http://www.morfix.co.il/en/%s" % quote(word)

    pairs = []
    fname = 'urls/' + url.replace('/', "-")
    try:
        p = open(fname).read().split('=====/////-----')
        try:
            word_descr = p[1].strip()
        except BaseException:
            word_descr = ''

        if len(p[0].strip()):
            for pi in p[0].strip().split('\n\n'):
                pi = pi.split('\n')
                pairs.append([pi[0], pi[1]])
    except BaseException:
        req = requests.get(url)
        soup = BeautifulSoup(req.text, "lxml")
        divs = soup.find_all('div', class_='title_ph')

        pairs = []
        for div in divs:
            he = div.find('div', class_=re.compile('translation_he'))
            he = re.sub('\s+', ' ', he.get_text()).strip()

            en = div.find('div', class_=re.compile('translation_en'))
            en = re.sub('\s+', ' ', en.get_text()).strip()

            if config.lang_from == 'he':
                pairs.append([he, en])
            else:
                pairs.append([en, he])

        word_descr = ''
        # extra check against double-writing from rouge threads
        if not os.path.isfile(fname):
            print('\n\n'.join(e[0] + '\n' + e[1]
                              for e in pairs), file=open(fname, 'a'))
            print('\n' + '=====/////-----' + '\n', file=open(fname, 'a'))
            print(word_descr, file=open(fname, 'a'))

    return pairs, ['', '']

# deepl.com
# https://github.com/EmilioK97/pydeepl


def deepl(text):
    l1 = config.lang_from.upper()
    l2 = config.lang_to.upper()

    if len(text) > 5000:
        return 'Text too long (limited to 5000 characters).'

    parameters = {
        'jsonrpc': '2.0',
        'method': 'LMT_handle_jobs',
        'params': {
            'jobs': [
                {
                    'kind': 'default',
                    'raw_en_sentence': text
                }
            ],
            'lang': {

                'source_lang_user_selected': l1,
                'target_lang': l2
            }
        }
    }

    response = requests.post(
        'https://www2.deepl.com/jsonrpc',
        json=parameters).json()
    print(response)
    if 'result' not in response:
        return 'DeepL call resulted in a unknown result.'

    translations = response['result']['translations']

    if len(translations) == 0 \
            or translations[0]['beams'] is None \
            or translations[0]['beams'][0]['postprocessed_sentence'] is None:
        return 'No translations found.'

    return translations[0]['beams'][0]['postprocessed_sentence']


def listen(word, type='gtts'):
    if type == 'pons':
        if config.lang_from + config.lang_to in pons_combos:
            url = 'http://en.pons.com/translate?q=%s&l=%s%s&in=%s' % (
                quote(word), config.lang_from, config.lang_to, config.lang_from)
        else:
            url = 'http://en.pons.com/translate?q=%s&l=%s%s&in=%s' % (
                quote(word), config.lang_to, config.lang_from, config.lang_from)

        p = requests.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'}).text
        x = re.findall(
            '<dl id="([a-zA-Z0-9]*?)" class="dl-horizontal kne(.*?)</dl>',
            p,
            re.DOTALL)
        x2 = re.findall(
            'class="audio tts trackable trk-audio" data-pons-lang="(.*?)"',
            x[0][1])

        for l in x2:
            if config.lang_from in l:
                mp3 = 'http://sounds.pons.com/audio_tts/%s/%s' % (l, x[0][0])
                break

        os.system('(cd /tmp; wget ' + mp3 + '; mpv --load-scripts=no --loop=1 --volume=40 --force-window=no ' +
                  mp3.split('/')[-1] + '; rm ' + mp3.split('/')[-1] + ') &')
    elif type == 'gtts':
        gTTS(text=word, lang=config.lang_from,
             slow=False).save('/tmp/gtts_word.mp3')
        os.system(
            '(mpv --load-scripts=no --loop=1 --volume=75 --force-window=no ' +
            '/tmp/gtts_word.mp3' +
            '; rm ' +
            '/tmp/gtts_word.mp3' +
            ') &')
    elif type == 'forvo':
        url = 'https://forvo.com/word/%s/%s/' % (config.lang_from, quote(word))

        try:
            data = requests.get(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'}).text

            soup = BeautifulSoup(data, "lxml")
            trs = soup.find_all(
                'article', class_='pronunciations')[0].find_all(
                'span', class_='play')

            mp3s = ''
            for tr in trs[:2]:
                tr = tr['onclick']
                tr = re.findall('Play\((.*?)\)', tr)[0]
                tr = tr.split(',')[4].replace("'", '')
                tr = base64.b64decode(tr)
                tr = tr.decode("utf-8")

                mp3s += 'mpv --load-scripts=no --loop=1 --volume=111 --force-window=no https://audio00.forvo.com/audios/mp3/%s ; ' % tr
            os.system('(%s) &' % mp3s)
        except BaseException:
            return

# https://github.com/Boudewijn26/gTTS-token


class Token:
    """ Token (Google Translate Token)
    Generate the current token key and allows generation of tokens (tk) with it
    Python version of `token-script.js` itself from translate.google.com
    """

    SALT_1 = "+-a^+6"
    SALT_2 = "+-3^+b+-f"

    def __init__(self):
        self.token_key = None

    def calculate_token(self, text, seed=None):
        """ Calculate the request token (`tk`) of a string
        :param text: str The text to calculate a token for
        :param seed: str The seed to use. By default this is the number of hours since epoch
        """

        if seed is None:
            seed = self._get_token_key()

        [first_seed, second_seed] = seed.split(".")

        try:
            d = bytearray(text.encode('UTF-8'))
        except UnicodeDecodeError:
            # This will probably only occur when d is actually a str containing UTF-8 chars, which means we don't need
            # to encode.
            d = bytearray(text)

        a = int(first_seed)
        for value in d:
            a += value
            a = self._work_token(a, self.SALT_1)
        a = self._work_token(a, self.SALT_2)
        a ^= int(second_seed)
        if 0 > a:
            a = (a & 2147483647) + 2147483648
        a %= 1E6
        a = int(a)
        return str(a) + "." + str(a ^ int(first_seed))

    def _get_token_key(self):
        if self.token_key is not None:
            return self.token_key

        response = requests.get("https://translate.google.com/")
        tkk_expr = re.search("(tkk:.*?),", response.text)
        if not tkk_expr:
            raise ValueError(
                "Unable to find token seed! Did https://translate.google.com change?"
            )

        tkk_expr = tkk_expr.group(1)
        try:
            # Grab the token directly if already generated by function call
            result = re.search("\d{6}\.[0-9]+", tkk_expr).group(0)
        except AttributeError:
            # Generate the token using algorithm
            timestamp = calendar.timegm(time.gmtime())
            hours = int(math.floor(timestamp / 3600))
            a = re.search("a\\\\x3d(-?\d+);", tkk_expr).group(1)
            b = re.search("b\\\\x3d(-?\d+);", tkk_expr).group(1)

            result = str(hours) + "." + str(int(a) + int(b))

        self.token_key = result
        return result

    """ Functions used by the token calculation algorithm """

    def _rshift(self, val, n):
        return val >> n if val >= 0 else (val + 0x100000000) >> n

    def _work_token(self, a, seed):
        for i in range(0, len(seed) - 2, 3):
            char = seed[i + 2]
            d = ord(char[0]) - 87 if char >= "a" else int(char)
            d = self._rshift(a, d) if seed[i + 1] == "+" else a << d
            a = a + d & 4294967295 if seed[i] == "+" else a ^ d
        return a

# https://github.com/pndurette/gTTS


class gTTS:
    """ gTTS (Google Text to Speech): an interface to Google's Text to Speech API """

    # Google TTS API supports two read speeds
    # (speed <= 0.3: slow; speed > 0.3: normal; default: 1)
    class Speed:
        SLOW = 0.3
        NORMAL = 1

    GOOGLE_TTS_URL = 'https://translate.google.com/translate_tts'
    MAX_CHARS = 100  # Max characters the Google TTS API takes at a time
    LANGUAGES = {
        'af': 'Afrikaans',
        'sq': 'Albanian',
        'ar': 'Arabic',
        'hy': 'Armenian',
        'bn': 'Bengali',
        'ca': 'Catalan',
        'zh': 'Chinese',
        'zh-cn': 'Chinese (Mandarin/China)',
        'zh-tw': 'Chinese (Mandarin/Taiwan)',
        'zh-yue': 'Chinese (Cantonese)',
        'hr': 'Croatian',
        'cs': 'Czech',
        'da': 'Danish',
        'nl': 'Dutch',
        'en': 'English',
        'en-au': 'English (Australia)',
        'en-uk': 'English (United Kingdom)',
        'en-us': 'English (United States)',
        'eo': 'Esperanto',
        'fi': 'Finnish',
        'fr': 'French',
        'de': 'German',
        'el': 'Greek',
        'hi': 'Hindi',
        'hu': 'Hungarian',
        'is': 'Icelandic',
        'id': 'Indonesian',
        'it': 'Italian',
        'iw': 'Hebrew',
        'ja': 'Japanese',
        'km': 'Khmer (Cambodian)',
        'ko': 'Korean',
        'la': 'Latin',
        'lv': 'Latvian',
        'mk': 'Macedonian',
        'no': 'Norwegian',
        'pl': 'Polish',
        'pt': 'Portuguese',
        'ro': 'Romanian',
        'ru': 'Russian',
        'sr': 'Serbian',
        'si': 'Sinhala',
        'sk': 'Slovak',
        'es': 'Spanish',
        'es-es': 'Spanish (Spain)',
        'es-us': 'Spanish (United States)',
        'sw': 'Swahili',
        'sv': 'Swedish',
        'ta': 'Tamil',
        'th': 'Thai',
        'tr': 'Turkish',
        'uk': 'Ukrainian',
        'vi': 'Vietnamese',
        'cy': 'Welsh'
    }

    def __init__(self, text, lang='en', slow=False, debug=False):
        self.debug = debug
        if lang.lower() not in self.LANGUAGES:
            raise Exception('Language not supported: %s' % lang)
        else:
            self.lang = lang.lower()

        if not text:
            raise Exception('No text to speak')
        else:
            self.text = text

        # Read speed
        if slow:
            self.speed = self.Speed().SLOW
        else:
            self.speed = self.Speed().NORMAL

        # Split text in parts
        if self._len(text) <= self.MAX_CHARS:
            text_parts = [text]
        else:
            text_parts = self._tokenize(text, self.MAX_CHARS)

        # Clean
        def strip(x): return x.replace('\n', '').strip()
        text_parts = [strip(x) for x in text_parts]
        text_parts = [x for x in text_parts if len(x) > 0]
        self.text_parts = text_parts

        # Google Translate token
        self.token = Token()

    def save(self, savefile):
        """ Do the Web request and save to `savefile` """
        with open(savefile, 'wb') as f:
            self.write_to_fp(f)

    def write_to_fp(self, fp):
        """ Do the Web request and save to a file-like object """
        for idx, part in enumerate(self.text_parts):
            payload = {'ie': 'UTF-8',
                       'q': part,
                       'tl': self.lang,
                       'ttsspeed': self.speed,
                       'total': len(self.text_parts),
                       'idx': idx,
                       'client': 'tw-ob',
                       'textlen': self._len(part),
                       'tk': self.token.calculate_token(part)}
            headers = {
                "Referer": "http://translate.google.com/",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36"}
            if self.debug:
                print(payload)
            try:
                # Disable requests' ssl verify to accomodate certain proxies and firewalls
                # Filter out urllib3's insecure warnings. We can live without
                # ssl verify here
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)
                    r = requests.get(self.GOOGLE_TTS_URL,
                                     params=payload,
                                     headers=headers,
                                     proxies=urllib.request.getproxies(),
                                     verify=False)
                if self.debug:
                    print("Headers: {}".format(r.request.headers))
                    print("Request url: {}".format(r.request.url))
                    print(
                        "Response: {}, Redirects: {}".format(
                            r.status_code, r.history))
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=1024):
                    fp.write(chunk)
            except Exception as e:
                raise

    def _len(self, text):
        """ Get char len of `text`, after decoding if Python 2 """
        try:
            # Python 2
            return len(text.decode('utf8'))
        except AttributeError:
            # Python 3
            return len(text)

    def _tokenize(self, text, max_size):
        """ Tokenizer on basic roman punctuation """

        punc = "¡!()[]¿?.,;:—«»\n"
        punc_list = [re.escape(c) for c in punc]
        pattern = '|'.join(punc_list)
        parts = re.split(pattern, text)

        min_parts = []
        for p in parts:
            min_parts += self._minimize(p, " ", max_size)
        return min_parts

    def _minimize(self, thestring, delim, max_size):
        """ Recursive function that splits `thestring` in chunks
        of maximum `max_size` chars delimited by `delim`. Returns list. """

        if self._len(thestring) > max_size:
            idx = thestring.rfind(delim, 0, max_size)
            return [thestring[:idx]] + \
                self._minimize(thestring[idx:], delim, max_size)
        else:
            return [thestring]
