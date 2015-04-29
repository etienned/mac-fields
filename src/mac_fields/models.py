# -*- coding: utf-8 -*-

from django.db import models
from django.db.models.query import QuerySet
from django.http import Http404

from .filters import ligatures


class MMACQueryset(QuerySet):
    def _filter_or_exclude(self, negate, *args, **kwargs):
        def convert_quote(item):
            if not item or isinstance(item, str):
                return item
            if isinstance(item, unicode):
                if ('oe' or 'ae') in item.lower():
                    for old, new in ligatures:
                        item = item.replace(old, new)
                return item.replace(u"'", u"’")
            if isinstance(item, (list, tuple)):
                converted_item = [convert_quote(subitem) for subitem in item]
                if isinstance(item, tuple):
                    converted_item = tuple(converted_item)
                return converted_item
            if isinstance(item, models.Q):
                item.children = convert_quote(item.children)
                return item
            if isinstance(item, dict):
                for key, value in item.items():
                    item[key] = convert_quote(value)
                return item
            return item
        args = convert_quote(args)
        kwargs = convert_quote(kwargs)

        return super(MMACQueryset, self)._filter_or_exclude(negate, *args, **kwargs)

    def get_or_none(self, *args, **kwargs):
        """
        Get the object or return None if object does not exists or more then one
        object is return.
        """
        try:
            return self.get(*args, **kwargs)
        except (self.model.DoesNotExist, self.model.MultipleObjectsReturned):
            return None

    def get_or_404(self, *args, **kwargs):
        """
        Get the object or raise 404 if object does not exists or more then one
        object is return.
        """
        try:
            return self.get(*args, **kwargs)
        except (self.model.DoesNotExist, self.model.MultipleObjectsReturned):
            raise Http404


class MMACManager(models.Manager):
    def get_query_set(self):
        """
        Returns a new MMACQuerySet object.
        """
        return MMACQueryset(self.model, using=self._db)

    def get_or_none(self, *args, **kwargs):
        """
        Get the object or return None if object does not exists or more then one
        object is return.
        """
        return self.get_query_set().get_or_none(*args, **kwargs)

    def get_or_404(self, *args, **kwargs):
        """
        Get the object or raise 404 if object does not exists or more then one
        object is return.
        """
        return self.get_query_set().get_or_404(*args, **kwargs)


class MMACModel(models.Model):
    """
    Base Model that add some cleaning and adjustments on all fields.
    """
    # Add a custom manager that have a custom Queryset that replace straight
    # single quote by a curly one.
    objects = MMACManager()

    def __init__(self, *args, **kwargs):
        super(MMACModel, self).__init__(*args, **kwargs)
        self._state.fields_cleaned = False
        self._state.model_cleaned = False

    def save(self, *args, **kwargs):
        no_clean = kwargs.pop('no_clean', False)
        if not no_clean:
            if not self._state.fields_cleaned:
                self.clean_fields()
            if not self._state.model_cleaned:
                self.clean()
        self._state.fields_cleaned = False
        self._state.model_cleaned = False
        super(MMACModel, self).save(*args, **kwargs)

    def clean_fields(self, exclude=None):
        """
        Before fields validation, strip white space and replace straight single
        quote by curlies on all fields.
        Convert empty string to None for all CharField and TextField
        that are blank, null and unique to avoid database integrity errors.
        """
        self._state.fields_cleaned = True

        if exclude is None:
            exclude = []

        for field in self._meta.fields:
            if field.name in exclude:
                continue

            value = getattr(self, field.attname)
            # Strip whitespace and replace all straight single quote by a curly.
            if isinstance(value, basestring):
                value = value.strip().replace(u"'", u"’")
            # For CharField and TextField that are blank and null
            # change empty string to None to avoid database integrity errors
            # and unnecessary revision saving.
            if (isinstance(field, (models.CharField, models.TextField))
                    and field.blank is True
                    and field.null is True
                    and not value):
                value = None
            setattr(self, field.attname, value)
        super(MMACModel, self).clean_fields(exclude)

    def clean(self):
        self._state.model_cleaned = True
        super(MMACModel, self).clean()

    class Meta:
        abstract = True
