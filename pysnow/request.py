# -*- coding: utf-8 -*-

import json
import requests

from .response import Response
from .query import Query
from .report import Report

from .exceptions import InvalidUsage


class PreparedRequest(object):
    """Creates a new :class:`PreparedRequest` object.

    :param request_params: Request parameters to pass along with the request
    :param session: :class:`request.Session` object
    :param generator_size: Generator size / internal page size
    :param enable_reporting: Generate a resource-response report for this request
    :param generator_size: Sets the size of each yield, a higher value might increases performance some but
    will cause pysnow to consume more memory when serving big results.
    :param raise_on_empty: Whether or not to raise an exception on 404 (no matching records)
    :param base_url: Base URL to use for requests
    :param base_path: Base path to use for requests (e.g. /api/now)
    :param api_path: API path to use for requests (e.g. /table/incident)
    """

    def __init__(self,
                 request_params=None, session=None, generator_size=None,
                 enable_reporting=False, raise_on_empty=True, resource=None,
                 base_url=None, base_path=None, api_path=None):

        self._request_params = request_params
        self._session = session
        self._generator_size = generator_size
        self._enable_reporting = enable_reporting
        self._raise_on_empty = raise_on_empty
        self._resource = resource

        self._base_url = base_url
        self._base_path = base_path
        self._api_path = api_path

        self._url = self._get_url()

        if self._enable_reporting:
            self._report = Report(resource, generator_size, session)
        else:
            self._report = None

    def _get_url(self, sys_id=None):
        """Builds a full URL using base_url, base_path and api_path

        :param sys_id: (optional) Appends the provided sys_id to the URL
        :return: URL string
        """

        url_str = self._base_url + self._base_path + self._api_path

        if sys_id:
            return "%s/%s" % (url_str, sys_id)

        return url_str

    def _send(self, method, url=None, **kwargs):
        """Prepares and sends a new :class:`requests.Request` object, uses prepare() as it makes wrapping simpler.
        Also, sets request params in report, if reporting is enabled.

        :param method: Request method
        :param url: (optional) URL override (instead of :prop:`_url`)
        :param kwargs: kwargs to pass along to Request
        :return: :class:`requests.Response` object
        """

        url = url or self._url

        params = kwargs.pop('params', self._request_params)

        request = requests.Request(method, url, auth=self._session.auth, params=params, **kwargs)

        if self._enable_reporting:
            self._report.request_params = params

        prepared = request.prepare()
        response = self._session.send(prepared)

        return response

    def _get_response(self, method, **kwargs):
        """Response wrapper - creates a :class:`requests.Response` object and passes along to :class:`pysnow.Response`
        for validation and parsing.

        :param args: args to pass along to _send()
        :param kwargs: kwargs to pass along to _send()
        :return: :class:`pysnow.Response` object
        """

        return Response(self._send(method, **kwargs), request_callback=self._send,
                        raise_on_empty=self._raise_on_empty, report=self._report)

    def _get_request_params(self, query=None, fields=list(), limit=None, order_by=list(), offset=None):
        """Constructs request params dictionary to pass along with a :class:`requests.PreparedRequest` object

        :param query: Dictionary, string or :class:`QueryBuilder` object
        :param limit: Limits the number of records returned
        :param fields: List of fields to include in the response
        :param order_by: List of columns used in sorting. Example:
        ['category', '-created_on'] would sort the category field in ascending order, with a secondary sort by
        created_on in descending order.
        :param offset: Number of records to skip before returning records
        :return: :class:`pysnow.Query` dictionary-like object
        """

        query_params = Query(query, self._request_params)

        # Generator responses creates its "iterable chunks" using `sysparm_limit` and relies on the
        # use of link headers, which set_limit() disables, effectively disabling the use of generators.
        if not limit:
            query_params.set_generator_size(self._generator_size)
        else:
            query_params.set_limit(limit)

        query_params.set_fields(fields)
        query_params.set_offset(offset)
        query_params.set_sorting(order_by)

        return query_params.as_dict()

    def get(self, **kwargs):
        """Fetches one or more records, exposes a public API of :class:`pysnow.Response`

        :param kwargs: kwargs to pass along to :class:`requests.Request`
        :return: :class:`pysnow.Response` object
        """

        request_params = self._get_request_params(**kwargs)
        return self._get_response('GET', params=request_params)

    def custom(self, method, path_append=None, headers=None, **kwargs):
        """Creates a custom request

        :param method: HTTP method
        :param path_append: (optional) append path to resource.api_path
        :param headers: (optional) Dictionary of headers to add or override
        :param kwargs: kwargs to pass along to :class:`requests.Request`
        :return: :class:`pysnow.Response` object
        """

        if headers:
            self._session.headers.update(headers)

        if path_append is not None:
            if isinstance(path_append, str) and path_append.startswith('/'):
                self._url = "%s/%s" % (self._url, path_append)
            else:
                raise InvalidUsage("Argument 'path_append' must be a string in the following format: "
                                   "/path-to-append[/.../...]")

        return self._get_response(method, **kwargs)

    def insert(self, payload):
        """Creates a new record

        :param payload: Dictionary payload
        :return: Dictionary containing the inserted record
        """

        return self._get_response('POST', data=json.dumps(payload)).one()

    def update(self, query, payload):
        """Updates a record

        :param query: Dictionary, string or :class:`QueryBuilder` object
        :param payload: Dictionary payload
        :return: Dictionary containing the updated record
        """

        if not isinstance(payload, dict):
            raise InvalidUsage("Update payload must be of type dict")

        record = self.get(query=query).one()

        url = self._get_url(sys_id=record['sys_id'])
        return self._get_response('PUT', url=url, data=json.dumps(payload)).one()

    def delete(self, query):
        """Deletes a record

        :param query: Dictionary, string or :class:`QueryBuilder` object
        :return: Dictionary containing the result
        """
        record = self.get(query=query).one()

        url = self._get_url(sys_id=record['sys_id'])
        return self._get_response('DELETE', url=url).one()
