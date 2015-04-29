# -*- coding: utf-8 -*-

import re
import unicodedata

from django.utils.encoding import smart_unicode
from django.utils.text import unescape_entities

from typogrify.templatetags import typogrify


def adjust_plural(name, items):
    """
    Remove '(s)' if there's more then one item, else remove the
    around the 's'.
    """
    if not isinstance(items, int):
        items = len(items)
    if items > 1:
        return name.replace('(s)', 's')
    return name.replace('(s)', '')


def strip_accents(text):
    """
    Remove accents (diacritic) from all characters.
    """
    return ''.join((char for char
                    in unicodedata.normalize('NFD', text)
                    if not unicodedata.combining(char)))


def strip_to_base(text, chars='alpha', accents=True, lower=True):
    if accents:
        text = strip_accents(text)
    if lower:
        text = text.lower()
    if chars == 'alpha':
        text = re.sub('[^a-z]*', '', text)
    elif chars:
        for char in chars:
            text = text.replace(char, '')
    return text


ligatures = (
    (u'boeuf', u'bœuf'),
    (u'Boeuf', u'Bœuf'),
    (u'BOEUF', u'BŒUF'),

    (u'choeur', u'chœur'),
    (u'Choeur', u'Chœur'),
    (u'CHOEUR', u'CHŒUR'),

    (u'coelacanthe', u'cœlacanthe'),
    (u'Coelacanthe', u'Cœlacanthe'),
    (u'COELACANTHE', u'CŒLACANTHE'),

    (u'coelentéré', u'cœlentéré'),
    (u'Coelentéré', u'Cœlentéré'),
    (u'COELENTÉRÉ', u'CŒLENTÉRÉ'),

    (u'coeur', u'cœur'),
    (u'Coeur', u'Cœur'),
    (u'COEUR', u'CŒUR'),

    (u'foetus', u'fœtus'),
    (u'Foetus', u'Fœtus'),
    (u'FOETUS', u'FŒTUS'),

    (u'manoeuvre', u'manœuvre'),
    (u'Manoeuvre', u'Manœuvre'),
    (u'MANOEUVRE', u'MANŒUVRE'),

    (u'moeurs', u'mœurs'),
    (u'Moeurs', u'Mœurs'),
    (u'MOEURS', u'MŒURS'),

    (u'noeud', u'nœud'),
    (u'Noeud', u'Nœud'),
    (u'NOEUD', u'NŒUD'),

    (u'soeur', u'sœur'),
    (u'Soeur', u'Sœur'),
    (u'SOEUR', u'SŒUR'),

    (u'voeu', u'vœu'),
    (u'Voeu', u'Vœu'),
    (u'VOEU', u'VŒU'),

    (u'oecuménique', u'œcuménique'),
    (u'Oecuménique', u'Œcuménique'),
    (u'OEcuménique', u'Œcuménique'),
    (u'OECUMÉNIQUE', u'ŒCUMÉNIQUE'),

    (u'oedème', u'œdème'),
    (u'Oedème', u'Œdème'),
    (u'OEdème', u'Œdème'),
    (u'OEDÈME', u'ŒDÈME'),

    (u'oedicnème', u'œdicnème'),
    (u'Oedicnème', u'Œdicnème'),
    (u'OEdicnème', u'Œdicnème'),
    (u'OEDICNÈME', u'ŒDICNÈME'),

    (u'oeil', u'œil'),
    (u'Oeil', u'Œil'),
    (u'OEil', u'Œil'),
    (u'OEIL', u'ŒIL'),

    (u'oeillet', u'œillet'),
    (u'Oeillet', u'Œillet'),
    (u'OEillet', u'Œillet'),
    (u'OEILLET', u'ŒILLET'),

    (u'oenochoé', u'œnochoé'),
    (u'Oenochoé', u'Œnochoé'),
    (u'OEnochoé', u'Œnochoé'),
    (u'OENOCHOÉ', u'ŒNOCHOÉ'),

    (u'oenologie', u'œnologie'),
    (u'Oenologie', u'Œnologie'),
    (u'OEnologie', u'Œnologie'),
    (u'OENOLOGIE', u'ŒNOLOGIE'),

    (u'oersted', u'œrsted'),
    (u'Oersted', u'Œrsted'),
    (u'OErsted', u'Œrsted'),
    (u'OERSTED', u'ŒRSTED'),

    (u'oesophage', u'œsophage'),
    (u'Oesophage', u'Œsophage'),
    (u'OEsophage', u'Œsophage'),
    (u'OESOPHAGE', u'ŒSOPHAGE'),

    (u'oestrogène', u'œstrogène'),
    (u'Oestrogène', u'Œstrogène'),
    (u'OEstrogène', u'Œstrogène'),
    (u'OESTROGÈNE', u'ŒSTROGÈNE'),

    (u'oestrus', u'œstrus'),
    (u'Oestrus', u'Œstrus'),
    (u'OEstrus', u'Œstrus'),
    (u'OESTRUS', u'ŒSTRUS'),

    (u'oeuf', u'œuf'),
    (u'Oeuf', u'Œuf'),
    (u'OEuf', u'Œuf'),
    (u'OEUF', u'ŒUF'),

    (u'oeuvre', u'œuvre'),
    (u'Oeuvre', u'Œuvre'),
    (u'OEuvre', u'Œuvre'),
    (u'OEUVRE', u'ŒUVRE'),

    (u'oedipe', u'Œdipe'),
    (u'Oedipe', u'Œdipe'),
    (u'OEdipe', u'Œdipe'),
    (u'OEDIPE', u'ŒDIPE'),

    (u'oeniadæ', u'Œniadæ'),
    (u'Oeniadæ', u'Œniadæ'),
    (u'OEniadæ', u'Œniadæ'),
    (u'OENIADÆ', u'ŒNIADÆ'),
    (u'oeniadoe', u'Œniadæ'),
    (u'Oeniadoe', u'Œniadæ'),
    (u'OEniadoe', u'Œniadæ'),
    (u'OENIADOE', u'ŒNIADÆ'),

    (u'oenone', u'Œnone'),
    (u'Oenone', u'Œnone'),
    (u'OEnone', u'Œnone'),
    (u'OENONE', u'ŒNONE'),


    (u'caecum', u'cæcum'),
    (u'Caecum', u'Cæcum'),
    (u'CAECUM', u'CÆCUM'),

    (u'curriculum vitae', u'curriculum vitæ'),
    (u'Curriculum vitae', u'Curriculum vitæ'),
    (u'CURRICULUM VITAE', u'CURRICULUM VITÆ'),

    (u'ex aequo', u'ex æquo'),
    (u'Ex aequo', u'Ex æquo'),
    (u'EX AEQUO', u'EX ÆQUO'),

    (u'iléo-caecal', u'iléo-cæcal'),
    (u'Iléo-caecal', u'Iléo-cæcal'),
    (u'ILÉO-CAECAL', u'ILÉO-CÆCAL'),

    (u'naevus', u'nævus'),
    (u'Naevus', u'Nævus'),
    (u'NAEVUS', u'NÆVUS'),

    (u'praesidium', u'præsidium'),
    (u'Praesidium', u'Præsidium'),
    (u'PRAESIDIUM', u'PRÆSIDIUM'),

    (u'taenia', u'tænia'),
    (u'Taenia', u'Tænia'),
    (u'TAENIA', u'TÆNIA'),
)


def adjust_typo(texte, html=True):
    texte = smart_unicode(texte).strip()
    if not texte or (html and re.match(r'(\s*<(/?[^>]*[^>/]|br /)>\s*)+$', texte, re.UNICODE | re.IGNORECASE)):
        return u''

    # TODO: add unit tests
    # TODO: in regex add code to ignore tags replacement

    if html:
        # remove HTML tags before processing text
        tokens = re.findall(u'<[^>]+>', texte)

        for idx, value in enumerate(tokens):
            texte = texte.replace(value, ']TAG%s[' % idx, 1)

    # replace OE and AE by their correct ligature, Œ and Æ.
    for old, new in ligatures:
        texte = texte.replace(old, new)

# TODO: verify if these cases are cover
#    s/—/&#151;/g;
#    s/ - / &#151; /g;
#    s/--/—/g;
#    s/—/&#151;/g;
#    s/ — / —&nbsp;/g;
#    s/—/&#151;/g;

    # do some typographic adjustments (mostly putting non-breaking space where needed)
    regexs = [
        (u'  +', u' '),  # remove more then one normal space
        (u'  +', u' '),  # remove more then one special space
        (u'«(\s| )+', u'«&nbsp;'),  # make space non-breaking after «
        (u'(\s| )+»', u'&nbsp;»'),  # make space non-breaking before »
        (u'«([^&])', u'«&nbsp;\g<1>'),  # add non-breaking space after «
        (u'([^;])»', u'\g<1>&nbsp;»'),  # add non-breaking space before »
        (u'(\s| )+(:|;|\?|!|$|%)', u'&nbsp;\g<2>'),  # make space non-breaking before :, ?, !, $, %
        (u'(\d)(\s| )+(cm)', u'\g<1>&nbsp;\g<3>'),  # put non-breaking space between groups in long numbers (ex.: 23 000)
        (u'(\d)(\s| )+(\d{3})', u'\g<1>&nbsp;\g<3>'),  # put non-breaking space between groups in long numbers (ex.: 23 000)
        (u'(\s| )P\.(\s| )', u'\g<1>P.&nbsp;'),  # put non-breaking space after Page abbreviation
        (u'(\s| )p\.', u'&nbsp;p.'),  # put non-breaking space before page abbreviation

        (u' -- ', u' — '),  # changed 2 hyphen in a EM dash

        (u'&(l|g)t;', u'&amp;\g<1>t;'),  # to keep &lt; and &gt; as entities when doing unescape_entities
    ]

    if html:
        regexs.extend([
            (u'(\d)(ème|e|es)(\s| |-)', u'\g<1><sup>\g<2></sup>\g<3>'),  # put number extension in exposant (ex. 2e)
            (u'([IVX])e(\s| )', u'\g<1><sup>e</sup>\g<2>'),  # put roman number extension in exposant (ex. Xe)
            (u'1er(\s| |-)', u'1<sup>er</sup>\g<1>'),  # put 1 extension in exposant (ex. 1er)
        ])

    for old, new in regexs:
        texte = re.sub(old, new, texte)

    # replace html tags at their good location
    if html:
        for idx, value in enumerate(tokens):
            texte = texte.replace(']TAG%s[' % idx, value, 1)

    # do more typographic adjustments with smartypants
    texte = typogrify.smartypants(texte)
    return unescape_entities(texte).strip()
