# -*- coding: utf-8 -*-

import datetime
import re
import time
from xml.etree.cElementTree import XML
from xml.parsers.expat import ExpatError

from django import forms
from django.contrib.admin import options
from django.core import exceptions, validators
from django.db import models
from django.utils import datetime_safe, html
from django.utils.functional import allow_lazy
from django.utils.safestring import mark_safe
from django.utils.text import _replace_entity, _entity_re
from django.utils.translation import ugettext as _

from south.modelsinspector import add_introspection_rules

from .filters import adjust_typo
from .html import html_to_text


def _local_replace_entity(match):
    text = match.group(1)
    if text in ('lt', 'gt'):
        return match.group(0)
    return _replace_entity(match)


def unescape_entities(text):
    return _entity_re.sub(_local_replace_entity, text)
unescape_entities = allow_lazy(unescape_entities, unicode)


re_parent_title = re.compile(u"^(?P<article>(?:THE|The|A|An|AN|LE|Le|LA|La|LES|Les) |(?:L'|L’))(?P<title>.+)$")
re_unparent_title = re.compile(u"^(?P<title>.+) \((?:(?P<space>THE|The|A|An|AN|LE|Le|LA|La|LES|Les)|(?P<quote>L'|L’))\)$")


class TitleField(models.CharField):
    __metaclass__ = models.SubfieldBase

    def get_prep_value(self, value):
        """
        Put leading article, if there's one, in parenthesis at the title end.
        """
        def check_matches(matches):
            return u'%s (%s)' % (matches.group('title'),
                                 matches.group('article').strip())

        value = super(TitleField, self).get_prep_value(value)
        if value:
            value = re_parent_title.sub(check_matches, value, 1)
        return value

    def get_prep_lookup(self, lookup_type, value):
        """
        Deal with leading article for lookup.
        """
        if lookup_type in ('contains', 'icontains', 'iexact', 'startswith', 'istartswith'):
            value = self.get_prep_value(value)
        value = super(TitleField, self).get_prep_lookup(lookup_type, value)
        if lookup_type in ('contains', 'icontains', 'startswith', 'istartswith'):
            # strip the article in parenthesis
            value = re_unparent_title.sub('\g<title>', value, 1)
        return value

    def to_python(self, value):
        """
        Put back article to the title start if there's one in parenthesis at
        the end.
        """
        def check_matches(matches):
            if matches.group('space'):
                return '%s %s' % (matches.group('space'), matches.group('title'))
            if matches.group('quote'):
                return '%s%s' % (matches.group('quote'), matches.group('title'))

        if isinstance(value, basestring):
            value = re_unparent_title.sub(check_matches, value, 1)
        return super(TitleField, self).to_python(value)


class HTMLField(models.TextField):
    __metaclass__ = models.SubfieldBase

    default_error_messages = {
        'invalid': _(u'Le code XHTML de ce champ est invalide.'),
    }

    def __init__(self, verbose_name=None, name=None, search_text=True, xml=True,
                 filter_text=False, **kwargs):
        self.search_text = search_text
        self.xml = xml
        self.filter_text = filter_text
        self._splitter = '\n<><><><><><><><>\n'
        super(HTMLField, self).__init__(verbose_name, name, **kwargs)

    def to_python(self, value):
        # Remove the text part if any, only keep the HTML part
        if isinstance(value, basestring):
            return mark_safe(value.split(self._splitter, 1)[0])
        return value

    def validate(self, value, model_instance):
        super(HTMLField, self).validate(value, model_instance)
        if self.xml and value and value.strip():
            try:
                value = self.get_prep_value(value)
                if isinstance(value, unicode):
                    value = value.encode('utf-8')
                XML('<root>%s</root>' % value)
            except (ExpatError, SyntaxError):
                raise exceptions.ValidationError(self.error_messages['invalid'])

    def clean(self, value, model_instance):
        if self.filter_text and value:
            if not callable(self.filter_text):
                self.filter_text = adjust_typo
            value = self.filter_text(value)
        return super(HTMLField, self).clean(value, model_instance)

    def get_prep_value(self, value):
        "Standardize encoding, entities, etc."
        value = super(HTMLField, self).get_prep_value(value)
        if isinstance(value, basestring):
            value = html.fix_ampersands(unescape_entities(value))
        return value

    def get_db_prep_save(self, value, connection):
        """
        If search_text is True, add the text version after the HTML content in
        the database.
        """
        if value and self.search_text:
            value = self._splitter.join((value, html_to_text(value)))
        return super(HTMLField, self).get_db_prep_save(value, connection=connection)

    def formfield(self, **kwargs):
        """
        Add html-field CSS class to the textarea so, it's easy to add RTE.
        """
        defaults = {'widget': forms.Textarea(attrs={'class': 'html-field'})}
        defaults.update(kwargs)
        return super(HTMLField, self).formfield(**defaults)


class TextOrHTMLField(HTMLField):
    __metaclass__ = models.SubfieldBase

    def __init__(self, selector_field=None, verbose_name=None, name=None,
                 search_text=True, xml=True, filter_text=False, **kwargs):
        self.selector_field = selector_field
        super(TextOrHTMLField, self).__init__(verbose_name=verbose_name,
                                              name=name,
                                              search_text=search_text,
                                              xml=xml,
                                              filter_text=filter_text,
                                              **kwargs)

    def validate(self, value, model_instance):
        if getattr(model_instance, self.selector_field):
            super(TextOrHTMLField, self).validate(value, model_instance)
        else:
            self.search_text = False
            super(HTMLField, self).validate(value, model_instance)

    def clean(self, value, model_instance):
        if getattr(model_instance, self.selector_field):
            return super(TextOrHTMLField, self).clean(value, model_instance)
        self.search_text = False
        if self.filter_text and value:
            value = adjust_typo(value, html=False)
        return super(HTMLField, self).clean(value, model_instance)

    def save_form_data(self, instance, data):
        if not getattr(instance, self.selector_field):
            self.search_text = False
        super(TextOrHTMLField, self).save_form_data(instance, data)


class FlexibleDate(object):
    """
    Represent a date that can be partial, ie. that have some parts missing.
    Theses dates can be partial year, year-month or complete, year-month-day.
    Dates can also have square brackets to show that some parts are not validated.
    Dates can also have question marks to show that some parts are unknown.
    Dates can have circa (around this year).

    First argument can a string, a date object or a datetime object.
    Circa should be a string, use when outputting a date with a circa.
    Separator should be a string, use when outputting a date
    Set raw to True if you want to pass a datetime object directly to the inner
    _date value, like when you're creating a date from serialize data or from
    a database.
    """

    # Hour = Precision (year, year-month or year-month-day)
    PRESC_DAY = 16
    PRESC_MONTH = 12
    PRESC_YEAR = 8
    PRESCS = (PRESC_DAY, PRESC_MONTH, PRESC_YEAR)

    # Minute = Question marks / Circa
    NO_QSTN = 40

    QSTN_CIRCA = 30

    QSTN_0_DAY = 28
    QSTN_0_MONTH = 26
    QSTN_1_MONTH = 24
    QSTN_0_YEAR = 22
    QSTN_1_YEAR = 20
    QSTN_2_YEAR = 18

    QSTNS = (NO_QSTN, QSTN_CIRCA, QSTN_0_DAY, QSTN_0_MONTH, QSTN_1_MONTH,
             QSTN_0_YEAR, QSTN_1_YEAR, QSTN_2_YEAR)

    # Second = Square brackets (close are added to open to create the final value)
    NO_BRKT = 50

    OPEN_BRKT_DAY = 40
    OPEN_BRKT_MONTH = 30
    OPEN_BRKT_YEAR = 20

    CLOSE_BRKT_DAY = 2
    CLOSE_BRKT_MONTH = 4
    CLOSE_BRKT_YEAR = 6

    BRKTS = (NO_BRKT,
             OPEN_BRKT_DAY + CLOSE_BRKT_DAY,
             OPEN_BRKT_MONTH + CLOSE_BRKT_DAY,
             OPEN_BRKT_MONTH + CLOSE_BRKT_MONTH,
             OPEN_BRKT_YEAR + CLOSE_BRKT_DAY,
             OPEN_BRKT_YEAR + CLOSE_BRKT_MONTH,
             OPEN_BRKT_YEAR + CLOSE_BRKT_YEAR)

    NORMAL_TIME = datetime.time(PRESC_DAY, NO_QSTN, NO_BRKT)

    def __init__(self, date_input, circa=None, separator=None, raw=False):
        """
        Create a FlexibleDate from a string representing a date.
        The string should have 1, 2 or 3 groups of digit separated by one of
        these delimiters (/-,.), in this order: year-month-day.
        Or it can be from 4 to 8 digits without any separator, question marks
        square brackets and circa:
            YYYY
            YYYYMM
            YYYYMMDD

        FlexibleDate are encoded internally in a datetime object. So they inherit
        automatically most of the features of dates objects (comparison, etc.).
        Year, month and day are encoded directly as year, month and day of the
        datetime object.
         - When parts of the year are undefined, they are replace by zeros.
         - When parts of the month are undefined, they are replace by ones.
         - When parts of the day are undefined, they are replace by ones.

         - When month and/or day are not define, they are replace by one (01).

        Square brackets informations are encoded in the seconds (see below for rules).
        Question marks and circa are encoded in the minutes (see below for rules).
        Resolution (just year, year and month or year, month and day) are encoded
        in the hour.

        This way the normal datetime sorting order is the good one.

        20??            2000-01-01 08:18:50
        200?            2000-01-01 08:20:50
        2000?           2000-01-01 08:22:50
        ca2000          2000-01-01 08:30:50
        [2000]          2000-01-01 08:40:26
        2000            2000-01-01 08:40:50
        [2000?-01]      2000-01-01 12:22:24
        [2000-0?]       2000-01-01 12:24:24
        2000-01?        2000-01-01 12:26:50
        [2000-01]       2000-01-01 12:40:24
        [2000]-01       2000-01-01 12:40:26
        2000-[01]       2000-01-01 12:40:34
        2000-01         2000-01-01 12:40:50
        2000-01-01?     2000-01-01 16:28:50
        [2000-01-01]    2000-01-01 16:40:22
        [2000-01]-01    2000-01-01 16:40:24
        [2000]-01-01    2000-01-01 16:40:26
        2000-[01-01]    2000-01-01 16:40:32
        2000-[01]-01    2000-01-01 16:40:34
        2000-01-[01]    2000-01-01 16:40:42
        2000-01-01      2000-01-01 16:40:50
        [2000-01-02]    2000-01-02 16:40:22
        2000-01-02      2000-01-02 16:40:50
        2000-01-03      2000-01-03 16:40:50
        """

        if isinstance(circa, basestring):
            self.circa_text = circa
        else:
            self.circa_text = u'ca'

        if isinstance(separator, basestring):
            self.separator = separator
        else:
            self.separator = u'-'

        if raw and isinstance(date_input, datetime.datetime):
            # We initialize self._date directly from the datetime object
            # after having check that H:M:S are valid for a FlexibleDate
            if (date_input.hour in self.PRESCS
                and date_input.minute in self.QSTNS
                and date_input.second in self.BRKTS
                and (date_input.hour == self.PRESC_DAY
                     or (date_input.hour == self.PRESC_MONTH
                         and date_input.minute != self.QSTN_0_DAY
                         and date_input.second not in (self.BRKTS[1], self.BRKTS[2], self.BRKTS[4]))
                     or (date_input.hour == self.PRESC_YEAR
                         and date_input.minute not in (self.QSTN_0_DAY, self.QSTN_0_MONTH, self.QSTN_1_MONTH)
                         and date_input.second in (self.BRKTS[0], self.BRKTS[6])))):
                self._date = date_input
            else:
                raise ValueError('Invalid Time values for a FlexibleDate')

        elif isinstance(date_input, datetime.date):
            if isinstance(date_input, datetime.datetime):
                # If it’s a datetime, keep only date information, because we
                # want a date
                date_input = date_input.date()
            # Add time info to set the date without any particularities ([], ?, ...)
            self._date = datetime.datetime.combine(date_input, self.NORMAL_TIME)

        elif isinstance(date_input, basestring):
            # Strip all whitespaces
            date_input = re.sub(r'\s+', u'', date_input)

            # Some early validations
            if not date_input:
                raise ValueError('Invalid date: empty string.')

            # Circa and ? are exclusive
            if u'?' in date_input and u'c' in date_input:
                raise ValueError('Invalid date: could not have circa and ? at the same time.')

            # Their should be at most one group of one or more question marks.
            if not re.match(r'[^\?]+\?*[^\?]*$', date_input):
                raise ValueError('Invalid date: more then one group of question marks (?).')

            # Their should have only one or no square brackets pair, the opening
            # bracket should be first and their should be at least one character
            # between the brackets.
            if not re.match(r'[^\[\]]*(\[[^\[\]]+\][^\[\]]*)?$', date_input):
                raise ValueError('Invalid date: square brackets problem.')

            match = re.match(r'(?P<circa>ca?)?\[?(?P<year>(?:\d{1,4}|\d{2}\?{2}|\d{3}\?|\d{4}\?))\]?(?:[/\-,.]\[?(?P<month>\d{1,2}\??)\]?(?:[/\-,.]\[?(?P<day>(?:\d{1,2}|\d{2}\??))\]?)?)?$', date_input)
            if not match:
                # In this case check for a date without separator (only digit and circa).
                match = re.match(r'(?P<circa>ca? ?)?(?P<year>\d{4})(?:(?P<month>[0-1]\d)(?:(?P<day>[0-3]\d))?)?$', date_input)
            if match:
                circa, year, month, day = match.group('circa', 'year', 'month', 'day')

                if u'[' in date_input:
                    # Define brackets value in function of their positions
                    # [0000]-[00]-[00]
                    # |    | |  | |  |   [ + ]
                    # |    | |  | |  +->    02
                    # |    | |  | +----> 40
                    # |    | |  +------>    04
                    # |    | +---------> 30
                    # |    +----------->    06
                    # +----------------> 20
                    #
                    # without brackets = 50

                    # Remove everything except brackets and separators
                    # (result should be like this '[-]-')
                    brackets_str = re.sub(r'[^\[\]/\-,.]', u'', date_input)
                    # Compute value from the brackets positions
                    seconds = 28 + (10 * brackets_str.index(u'[')) - (2 * brackets_str.index(u']'))
                else:
                    seconds = self.NO_BRKT

                if circa:
                    minutes = self.QSTN_CIRCA
                elif u'?' not in date_input:
                    minutes = self.NO_QSTN
                elif u'?' in year:
                    minutes = 18 + (2 * (year.index(u'?') - 2))
                elif u'?' in month:
                    minutes = 22 + (2 * month.index(u'?'))
                else:
                    minutes = self.QSTN_0_DAY

                if len(year) > 4:
                    year = year[:4]
                years = int(year.replace(u'?', '0'))
                hours = self.PRESC_YEAR

                if month:
                    if len(month) > 2:
                        month = month[:2]
                    months = int(month.replace(u'?', '1'))
                    if months:
                        hours = self.PRESC_MONTH
                    elif seconds % 10 in (self.CLOSE_BRKT_MONTH, self.CLOSE_BRKT_DAY):
                        raise ValueError('Invalid date: brackets not permitted around an empty month.')
                    elif minutes == self.QSTN_0_DAY:
                        raise ValueError('Invalid date: question marks to day not permitted after an empty month.')
                    else:
                        months = 1
                else:
                    months = 1

                if day:
                    if len(day) > 2:
                        day = day[:2]
                    days = int(day)
                    if days:
                        if hours != self.PRESC_MONTH:
                            raise ValueError('Invalid date: cannot have a day after an empty month.')
                        hours = self.PRESC_DAY
                    elif seconds % 10 == self.CLOSE_BRKT_DAY:
                        raise ValueError('Invalid date: brackets not permitted around an empty day.')
                    elif minutes == self.QSTN_0_DAY:
                        raise ValueError('Invalid date: question marks not permitted after an empty day.')
                    else:
                        days = 1
                else:
                    days = 1

                try:
                    self._date = datetime.datetime(years, months, days, hours, minutes, seconds)
                except ValueError, e:
                    raise ValueError(e)

            else:
                raise ValueError('Invalid date')

        else:
            raise TypeError('Invalid type')

    def __str__(self):
        """
        Return a string representation of the date, showing only parts that
        are defined. Ex.: if there's no day the output will be YYYY-MM.
        """
        date_str = []
        close_bracket = self._date.second % 10
        open_bracket = self._date.second - close_bracket
        if self._date.minute == self.QSTN_CIRCA:
            date_str.append(self.circa_text)
        if open_bracket == self.OPEN_BRKT_YEAR:
            date_str.append(u'[')

        year = str(self.year)
        if self._date.minute == self.QSTN_2_YEAR:
            year = '%s??' % year[:2]
        elif self._date.minute == self.QSTN_1_YEAR:
            year = '%s?' % year[:3]
        elif self._date.minute == self.QSTN_0_YEAR:
            year = '%s?' % year
        date_str.append(year)

        if close_bracket == self.CLOSE_BRKT_YEAR:
            date_str.append(u']')
        if self._date.hour >= self.PRESC_MONTH:
            date_str.append(self.separator)
            if open_bracket == self.OPEN_BRKT_MONTH:
                date_str.append(u'[')

            month = '%02d' % self.month
            if self._date.minute == self.QSTN_1_MONTH:
                month = '%s?' % month[0]
            elif self._date.minute == self.QSTN_0_MONTH:
                month = '%s?' % month
            date_str.append(month)

            if close_bracket == self.CLOSE_BRKT_MONTH:
                date_str.append(u']')

            if self._date.hour == self.PRESC_DAY:
                date_str.append(self.separator)
                if open_bracket == self.OPEN_BRKT_DAY:
                    date_str.append(u'[')

                day = '%02d' % self.day
                if self._date.minute == self.QSTN_0_DAY:
                    day = '%s?' % day
                date_str.append(day)

                if close_bracket == self.CLOSE_BRKT_DAY:
                    date_str.append(u']')

        return u''.join(date_str)

    def __repr__(self):
        return "<%s('%s')>" % (self.__class__.__name__, self.__str__())

    def _prep_cmp(self, other):
        # try to convert string to FlexibleDate
        if isinstance(other, basestring):
            try:
                other = FlexibleDate(other)
            except ValueError:
                return None
        if isinstance(other, FlexibleDate):
            return other._date
        if isinstance(other, datetime.date):
            if isinstance(other, datetime.datetime):
                # If it’s a datetime, keep only date information, because where
                # comparing dates
                other = other.date()
            # Add time info to set the date without any particularities ([], ?, ...)
            other = datetime.datetime.combine(other, self.NORMAL_TIME)
            return other
        return None

    def __lt__(self, other):
        other = self._prep_cmp(other)
        if other is not None:
            return self._date < other
        raise TypeError

    def __le__(self, other):
        return not self.__gt__(other)

    def __eq__(self, other):
        date = self._date
        # Compare both date without square brackets info (because brackets
        # are about validation and not value and normal date don't have this)
        if isinstance(other, datetime.date):
            date = date.replace(second=self.NO_BRKT)
        other = self._prep_cmp(other)
        if other is not None:
            return date == other
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        other = self._prep_cmp(other)
        if other is not None:
            return self._date > other
        raise TypeError

    def __ge__(self, other):
        return not self.__lt__(other)

    def __hash__(self):
        return self._date.__hash__()

    @property
    def year(self):
        """
        Return the year.
        """
        return self._date.year

    @property
    def month(self):
        """
        Return the month or None if there's no month.
        """
        if self._date.hour < self.PRESC_MONTH:
            return None
        else:
            return self._date.month

    @property
    def day(self):
        """
        Return the day or None if there's no day.
        """
        if self._date.hour == self.PRESC_DAY:
            return self._date.day
        else:
            return None

    @property
    def precision(self):
        """
        Return the smallest resolution of the date. Could be *year*, *month* or *day*.
        """
        if self._date.hour == self.PRESC_DAY:
            return 'day'
        elif self._date.hour == self.PRESC_MONTH:
            return 'month'
        return 'year'

    def isoformat(self):
        """
        Return the partial date in a string formated to the ISO standard (YYYY-MM-DD).
        """
        month, day = self._month_day_to_int()
        return '%04d-%02d-%02d' % (self.year, month, day)

    def strftime(self, format):  # @ReservedAssignment
        """
        Convert the date to a string as specified by the format argument.
        Use with caution, result could be surprising when there's no month or day.
        In this case, month and day should be equal to 1, not 0 or None.
        """
        return time.strftime(format, self.timetuple())

    def timetuple(self):
        """
        Return a *struct_time* (as return by gmtime()) for the date.
        """
        month, day = self._month_day_to_int()
        date = self._date.date()
        return time.struct_time((self.year, month, day, 0, 0, 0, date.weekday(),
                                 date.toordinal() - datetime.date(self.year, 1, 1).toordinal() + 1, -1))

    def _month_day_to_int(self):
        """
        Return the tuple *(month, day)* where *None* is replace by 0.
        """
        return (0 if part is None else part for part in (self.month, self.day))


class FlexibleDateFormField(forms.Field):
    widget = forms.TextInput
    default_error_messages = {
        'invalid': _(u'Entrez une date valide (partielle ou complète, peut contenir : ?, [], ca)'),
    }

    def to_python(self, value):
        """
        Validates that the input can be converted to a flexible date.
        Returns a Python FlexibleDate object.
        """
        if value in validators.EMPTY_VALUES:
            return None

        if isinstance(value, FlexibleDate):
            return value

        if isinstance(value, datetime.date):
            return FlexibleDate(value)

        if isinstance(value, basestring):
            try:
                return FlexibleDate(value)
            except ValueError:
                raise exceptions.ValidationError(self.error_messages['invalid'])


class FlexibleDateField(models.DateTimeField):
    """
    A Date Field that permit to omit the day or the day and month.
    """
    __metaclass__ = models.SubfieldBase

    default_error_messages = {
        'invalid': _(u'Entrez une date valide (partielle ou complète, peut contenir : ?, [], ca)'),
    }
    description = _("Date (flexible)")

    def to_python(self, value):
        if value is None or value == '':
            return None

        if isinstance(value, FlexibleDate):
            return value

        # From deserialization
        if isinstance(value, basestring):
            value = super(FlexibleDateField, self).to_python(value)

        # From DB
        if isinstance(value, datetime.datetime):
            try:
                return FlexibleDate(value, raw=True)
            except ValueError:
                raise exceptions.ValidationError(self.error_messages['invalid'])

    def pre_save(self, model_instance, add):
        if self.auto_now or (self.auto_now_add and add):
            value = FlexibleDate(datetime.date.today())
            setattr(model_instance, self.attname, value)
            return value
        else:
            return super(FlexibleDateField, self).pre_save(model_instance, add)

    def get_prep_lookup(self, lookup_type, value):
        # For get_next/get_previous reconvert value to FlexibleDate
        if lookup_type in ('gt', 'lt', 'exact') and isinstance(value, basestring):
            value = FlexibleDate(value)
        return super(FlexibleDateField, self).get_prep_lookup(lookup_type, value)

    def get_db_prep_value(self, value, connection, prepared=False):
        # Casts dates into the format expected by the backend
        if not prepared:
            value = self.get_prep_value(value)
        if value is None:
            return None
        return connection.ops.value_to_db_datetime(value._date)

    def value_to_string(self, obj):
        val = self._get_val_from_obj(obj)
        if val is None:
            data = ''
        else:
            d = datetime_safe.new_datetime(val._date)
            data = d.strftime('%Y-%m-%d %H:%M:%S')
        return data

    def formfield(self, **kwargs):
        defaults = {'form_class': FlexibleDateFormField}
        kwargs.update(defaults)
        return super(FlexibleDateField, self).formfield(**kwargs)


# Monkeypatching to prevent Django admin to override form Class and widget for
# FlexibleDate (because it's inherit from DateTimeField) and HTMLField.
options.FORMFIELD_FOR_DBFIELD_DEFAULTS[FlexibleDateField] = {
    'form_class': FlexibleDateFormField,
    'widget': forms.TextInput
}

options.FORMFIELD_FOR_DBFIELD_DEFAULTS[HTMLField] = {
    'widget': forms.Textarea(attrs={'class': 'vLargeTextField vHTMLField'})
}

# Introspection for South
add_introspection_rules([], ["^mmac\.utils\.fields"])
