# -*- coding: utf-8 -*-

import re

from django.utils.encoding import force_unicode
from django.utils.functional import allow_lazy
from django.utils.text import unescape_entities


_block_tags = 'address|blockquote|div|dl|h[1-6]|ol|p|pre|table|ul'
# Replace new lines inside text by space
_re_newline_in_text = re.compile('([^<>\s])\n([^\s<>])', flags=re.IGNORECASE)
# Add space after TD, TH and IMG
_re_space = re.compile('(</(?:td|th)>|<img [^>]+ />)(\S)',
                       flags=re.IGNORECASE | re.UNICODE)
# Add new line after BR, DD, DT, LI, TFOOT, TBODY, THEAD, TR
_re_newline = re.compile('(?:<br />|</(?:dd|dt|li|tfoot|tbody|thead|tr)>)',
                         flags=re.IGNORECASE)
# Add 2 new lines after BLOCKQUOTE, DIV, DL, H1, H2, H3, H4, H5, H6,
# HR, OL, P, PRE, TABLE, UL
_re_2newlines = re.compile('(?:<hr />|</(?:%s)>)' % _block_tags,
                           flags=re.IGNORECASE)
# Strip HTML tags
_re_strip_html = re.compile('<[^>]*?>')
# Remove superflous new lines
_re_strip_newlines = re.compile('\n\n+')
# Remove superflous spaces
_re_strip_spaces = re.compile('  +')


def html_to_text(html):
    """
    Return formated text from HTML source (keeping words separated and
    completed, paragraphs and new lines). The output is supposed to be fine for
    words and phrases searches.
    """
    text = force_unicode(html)
    text = text.strip()
    if text:
        # Format HTML source to ouput readable/searchable text
        text = _re_newline_in_text.sub('\g<1> \g<2>', text)
        text = text.replace('\n', '')
        text = _re_space.sub('\g<1> \g<2>', text)
        text = _re_newline.sub('\g<0>\n', text)
        text = _re_2newlines.sub('\g<0>\n\n', text)
        text = _re_strip_html.sub('', text)
        text = _re_strip_newlines.sub('\n\n', text.strip())
        text = _re_strip_spaces.sub(' ', text)
        text = unescape_entities(text)
        text = text.replace('&amp;', '&')
    return text
html_to_text = allow_lazy(html_to_text)
