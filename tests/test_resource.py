# -*- coding: utf-8 -*-
import unittest
import httpretty
import json
from six.moves.urllib.parse import urlparse, unquote

from pysnow.response import Response
from pysnow.client import Client
from pysnow.attachment import Attachment

from requests.exceptions import HTTPError

from pysnow.exceptions import (
    ResponseError,
    NoResults,
    MultipleResults,
    InvalidUsage,
    MissingResult,
    EmptyContent,
)


def get_serialized_result(dict_mock):
    return json.dumps({"result": dict_mock})


def get_serialized_error(dict_mock):
    return json.dumps({"error": dict_mock})


def qs_as_dict(url):
    qs_str = urlparse(url).query
    return dict(
        (x[0], unquote(x[1])) for x in [x.split("=") for x in qs_str.split("&")]
    )


class TestResourceRequest(unittest.TestCase):
    """Performs resource-request tests"""

    def setUp(self):
        self.error_message_body = {"message": "test_message", "detail": "test_details"}

        self.record_response_get_dict = {
            "sys_id": "98ace1a537ea2a00cf5c9c9953990e19",
            "attr1": "foo",
            "attr2": "bar",
        }

        self.record_response_get_one = [
            {
                "sys_id": "98ace1a537ea2a00cf5c9c9953990e19",
                "attr1": "foo",
                "attr2": "bar",
            }
        ]

        self.record_response_get_three = [
            {
                "sys_id": "37ea2a00cf5c9c995399098ace1a5e19",
                "attr1": "foo1",
                "attr2": "bar1",
            },
            {
                "sys_id": "98ace1a537ea2a00cf5c9c9953990e19",
                "attr1": "foo2",
                "attr2": "bar2",
            },
            {
                "sys_id": "a00cf5c9c9953990e1998ace1a537ea2",
                "attr1": "foo3",
                "attr2": "bar3",
            },
        ]

        self.record_response_create = {
            "sys_id": "90e11a537ea2a00cf598ace9c99539c9",
            "attr1": "foo_create",
            "attr2": "bar_create",
        }

        self.record_response_update = {
            "sys_id": "2a00cf5c9c99539998ace1a537ea0e19",
            "attr1": "foo_updated",
            "attr2": "bar_updated",
        }

        self.record_response_delete = {"status": "record deleted"}

        self.client_kwargs = {
            "user": "mock_user",
            "password": "mock_password",
            "instance": "mock_instance",
        }

        self.attachment = {
            "sys_id": "attachment_sys_id",
            "size_bytes": "512",
            "file_name": "test1.txt",
        }

        self.attachment_path = "tests/data/attachment.txt"

        self.base_path = "/api/now"
        self.api_path = "/table/incident"

        self.client = Client(**self.client_kwargs)
        self.resource = self.client.resource(
            base_path=self.base_path, api_path=self.api_path
        )

        self.mock_url_builder = self.resource._url_builder

        self.attachment_upload_url = (
            self.resource._base_url + self.resource._base_path + "/attachment/file"
        )

        self.mock_url_builder_base = self.resource._url_builder.get_url()
        self.mock_url_builder_sys_id = self.mock_url_builder.get_appended_custom(
            "/{0}".format(self.record_response_get_one[0]["sys_id"])
        )

        self.dict_query = {"sys_id": self.record_response_get_one[0]["sys_id"]}
        self.get_fields = ["foo", "bar"]

    def test_create_resource(self):
        """:class:`Resource` object repr type should be string, and its path should be set to api_path + base_path """

        r = self.client.resource(base_path=self.base_path, api_path=self.api_path)

        resource_repr = type(repr(r))

        self.assertEquals(resource_repr, str)
        self.assertEquals(r._base_path, self.base_path)
        self.assertEquals(r._api_path, self.api_path)
        self.assertEquals(r.path, self.base_path + self.api_path)

    @httpretty.activate
    def test_resource_request_default_timeout(self):
        resource = self.client.resource(
            base_path=self.base_path, api_path=self.api_path
        )
        assert resource._request._timeout == 60

    @httpretty.activate
    def test_resource_request_custom_timeout(self):
        resource = self.client.resource(
            base_path=self.base_path, api_path=self.api_path, timeout=30
        )
        assert resource._request._timeout == 30

    @httpretty.activate
    def test_response_headers(self):
        """Request response headers should be available in Response.headers property"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            status=200,
            adding_headers={"x-test-1": "foo", "x-test-2": "bar"},
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query)

        self.assertEqual(response.headers["x-test-1"], "foo")
        self.assertEqual(response.headers["x-test-2"], "bar")

    @httpretty.activate
    def test_response_count(self):
        """:prop:`count` of :class:`pysnow.Response` should raise an exception if count is set to non-integer"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query)

        self.assertRaises(TypeError, setattr, response, "count", "foo")
        self.assertRaises(TypeError, setattr, response, "count", True)
        self.assertRaises(TypeError, setattr, response, "count", {"foo": "bar"})

    @httpretty.activate
    def test_response_error(self):
        """:class:`pysnow.Response` should raise an exception if an error is encountered in the response body"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_error(self.error_message_body),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query, stream=True)

        expected_str = "Error in response. Message: %s, Details: %s" % (
            self.error_message_body["message"],
            self.error_message_body["detail"],
        )

        try:
            response.first()
        except ResponseError as e:
            self.assertEquals(str(e), expected_str)

    @httpretty.activate
    def test_get_request_fields(self):
        """:meth:`get_request` should return a :class:`pysnow.Response` object"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query, fields=self.get_fields)
        qs = qs_as_dict(response._response.request.url)

        str_fields = ",".join(self.get_fields)

        # List of fields should end up as comma-separated string
        self.assertEquals(type(response), Response)
        self.assertEquals(qs["sysparm_fields"], str_fields)

    @httpretty.activate
    def test_get_offset(self):
        """offset passed to :meth:`get` should set sysparm_offset in query"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        offset = 5
        response = self.resource.get(self.dict_query, offset=offset)
        qs = qs_as_dict(response._response.request.url)

        self.assertEquals(int(qs["sysparm_offset"]), offset)

    @httpretty.activate
    def test_get_limit(self):
        """limit passed to :meth:`get` should set sysparm_limit in QS"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        limit = 2

        response = self.resource.get(self.dict_query, limit=limit)
        qs = qs_as_dict(response._response.request.url)

        self.assertEquals(int(qs["sysparm_limit"]), limit)

    @httpretty.activate
    def test_get_limit(self):
        """limit passed to :meth:`get` should set sysparm_limit in QS"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        limit = 2

        response = self.resource.get(self.dict_query, limit=limit)
        qs = qs_as_dict(response._response.request.url)

        self.assertEquals(int(qs["sysparm_limit"]), limit)

    @httpretty.activate
    def test_get_one(self):
        """:meth:`one` of :class:`pysnow.Response` should raise an exception if more than one match was found"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query)
        result = response.one()

        self.assertEquals(result["sys_id"], self.record_response_get_one[0]["sys_id"])

    @httpretty.activate
    def test_get_all_empty(self):
        """:meth:`all` generator of :class:`pysnow.Response` should return an empty list if there are no matches"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result([]),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query, stream=True)
        result = list(response.all())

        self.assertEquals(result, [])

    @httpretty.activate
    def test_get_nocontent(self):
        """Result.one should raise EmptyContent for GET 202"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=202,
            content_type="application/json",
        )

        result = self.resource.get(self.dict_query)

        self.assertRaises(EmptyContent, result.one)

    @httpretty.activate
    def test_get_all_single(self):
        """Single items with all() using the stream parser should return a list containing the item"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_dict),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query, stream=True)
        result = list(response.all())[0]

        self.assertEquals(result, self.record_response_get_dict)

    @httpretty.activate
    def test_get_buffer_missing_result_keys(self):
        """:meth:`one` of :class:`pysnow.Response` should raise an exception if none of the expected keys
        was found in the result"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=json.dumps({}),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query)

        self.assertRaises(MissingResult, response.one)

    @httpretty.activate
    def test_get_stream_missing_result_keys(self):
        """:meth:`one` of :class:`pysnow.Response` should raise an exception if none of the expected keys
        was found in the result"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=json.dumps({}),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query, stream=True)

        self.assertRaises(MissingResult, response.first)

    @httpretty.activate
    def test_http_error_get_one(self):
        """:meth:`one` of :class:`pysnow.Response` should raise an HTTPError exception if a
        non-200 response code was encountered"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            status=500,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query)
        self.assertRaises(HTTPError, response.one)

    @httpretty.activate
    def test_get_one_many(self):
        """:meth:`one` of :class:`pysnow.Response` should raise an exception if more than one match was found"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_three),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query)
        self.assertRaises(MultipleResults, response.one)

    @httpretty.activate
    def test_get_one_empty(self):
        """:meth:`one` of :class:`pysnow.Response` should raise an exception if no matches were found"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result([]),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query)
        self.assertRaises(NoResults, response.one)

    @httpretty.activate
    def test_get_one_or_none_empty(self):
        """:meth:`one_or_none` of :class:`pysnow.Response` should return `None` if no matches were found """

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result([]),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query)
        result = response.one_or_none()

        self.assertEquals(result, None)

    @httpretty.activate
    def test_get_first_or_none_empty(self):
        """:meth:`first_or_none` of :class:`pysnow.Response` should return None if no records were found"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result([]),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query, stream=True)
        result = response.first_or_none()

        self.assertEquals(result, None)

    @httpretty.activate
    def test_get_first_or_none(self):
        """:meth:`first_or_none` of :class:`pysnow.Response` should return first match if multiple records were found"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_three),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query, stream=True)
        result = response.first_or_none()

        self.assertEquals(result, self.record_response_get_three[0])

    @httpretty.activate
    def test_get_first(self):
        """:meth:`first` of :class:`pysnow.Response` should return first match if multiple records were found"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_three),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query, stream=True)
        result = response.first()

        self.assertEquals(result, self.record_response_get_three[0])

    @httpretty.activate
    def test_get_first_empty(self):
        """:meth:`first` of :class:`pysnow.Response` should raise an exception if matches were found"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result([]),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(self.dict_query, stream=True)

        self.assertRaises(NoResults, response.first)

    @httpretty.activate
    def test_create(self):
        """:meth:`create` should return a dictionary of the new record"""

        httpretty.register_uri(
            httpretty.POST,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_create),
            status=200,
            content_type="application/json",
        )

        response = self.resource.create(self.record_response_create)

        self.assertEquals(type(response.one()), dict)
        self.assertEquals(response.one(), self.record_response_create)

    @httpretty.activate
    def test_update_sysid(self):
        """:meth:`update` should return a dictionary of the updated record"""

        sys_id = self.record_response_get_one[0]["sys_id"]

        httpretty.register_uri(
            httpretty.PATCH,
            self.mock_url_builder_sys_id,
            body=get_serialized_result(self.record_response_update),
            status=200,
            content_type="application/json",
        )

        updated = self.resource.update(sys_id, self.record_response_update)
        self.assertEquals(self.record_response_update["attr1"], updated["attr1"])

    @httpretty.activate
    def test_update(self):
        """:meth:`update` should return a dictionary of the updated record"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        httpretty.register_uri(
            httpretty.PATCH,
            self.mock_url_builder_sys_id,
            body=get_serialized_result(self.record_response_update),
            status=200,
            content_type="application/json",
        )

        response = self.resource.update(self.dict_query, self.record_response_update)
        result = response.one()

        self.assertEquals(type(result), dict)
        self.assertEquals(self.record_response_update["attr1"], result["attr1"])

    @httpretty.activate
    def test_update_invalid_payload(self):
        """:meth:`update` should raise an exception if payload is of invalid type"""

        self.assertRaises(InvalidUsage, self.resource.update, self.dict_query, "foo")
        self.assertRaises(InvalidUsage, self.resource.update, self.dict_query, False)
        self.assertRaises(InvalidUsage, self.resource.update, self.dict_query, 1)
        self.assertRaises(
            InvalidUsage, self.resource.update, self.dict_query, ("foo", "bar")
        )
        self.assertRaises(
            InvalidUsage, self.resource.update, self.dict_query, ["foo", "bar"]
        )

    @httpretty.activate
    def test_delete(self):
        """:meth:`delete` should return a dictionary containing status"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        httpretty.register_uri(
            httpretty.DELETE,
            self.mock_url_builder_sys_id,
            body=get_serialized_result(self.record_response_delete),
            status=204,
            content_type="application/json",
        )

        result = self.resource.delete(self.dict_query)

        self.assertEquals(type(result), dict)
        self.assertEquals(result["status"], "record deleted")

    @httpretty.activate
    def test_delete_chained(self):
        """:meth:`Response.delete` should return a dictionary containing status"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        httpretty.register_uri(
            httpretty.DELETE,
            self.mock_url_builder_sys_id,
            body=get_serialized_result(self.record_response_delete),
            status=204,
            content_type="application/json",
        )

        result = self.resource.get(query={}).delete()

        self.assertEquals(type(result), dict)
        self.assertEquals(result["status"], "record deleted")

    @httpretty.activate
    def test_custom(self):
        """:meth:`custom` should return a :class:`pysnow.Response` object"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        method = "GET"

        response = self.resource.request(method)

        self.assertEquals(response._response.request.method, method)
        self.assertEquals(type(response), Response)

    @httpretty.activate
    def test_custom_with_headers(self):
        """Headers provided to :meth:`custom` should end up in the request"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        headers = {"foo": "bar"}

        response = self.resource.request("GET", headers=headers)

        self.assertEquals(response._response.request.headers["foo"], headers["foo"])

    @httpretty.activate
    def test_custom_with_path(self):
        """path_append passed to :meth:`custom` should get appended to the request path"""

        path_append = "/foo"

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base + path_append,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        response = self.resource.request("GET", path_append="/foo")

        self.assertEquals(response._response.status_code, 200)

    @httpretty.activate
    def test_custom_with_path_invalid(self):
        """:meth:`custom` should raise an exception if the provided path is invalid"""

        self.assertRaises(
            InvalidUsage, self.resource.request, "GET", path_append={"foo": "bar"}
        )
        self.assertRaises(
            InvalidUsage, self.resource.request, "GET", path_append="foo/"
        )
        self.assertRaises(InvalidUsage, self.resource.request, "GET", path_append=True)

    @httpretty.activate
    def test_response_repr(self):
        """:meth:`get` should result in response obj repr describing the response"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(query={})
        response_repr = repr(response)

        self.assertEquals(response_repr, "<Response [200 - GET]>")

    def test_attachment_non_table(self):
        """Accessing `Resource.attachments` from a non-table API should fail"""

        resource = self.client.resource(base_path=self.base_path, api_path="/invalid")

        self.assertRaises(InvalidUsage, getattr, resource, "attachments")

    def test_attachment_type(self):
        """`Resource.attachments` should be of type Attachment"""

        attachment_type = type(self.resource.attachments)

        self.assertEqual(attachment_type, Attachment)

    def test_get_record_link(self):
        """`Resource.get_record_link()` should return full URL to the record"""

        record_link = self.resource.get_record_link("98ace1a537ea2a00cf5c9c9953990e19")

        self.assertEqual(record_link, self.mock_url_builder_sys_id)

    @httpretty.activate
    def test_get_response_item(self):
        """Accessing the response as a dict should work"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(query={})

        self.assertEquals(
            response["sys_id"], self.record_response_get_one[0].get("sys_id")
        )

    @httpretty.activate
    def test_get_buffered_first(self):
        """Using Response.first() without stream=True should fail"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(query={})

        self.assertRaises(InvalidUsage, response.first)

    @httpretty.activate
    def test_response_update(self):
        """Using Response.update should update the queried record"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        httpretty.register_uri(
            httpretty.PATCH,
            self.mock_url_builder_sys_id,
            body=get_serialized_result(self.record_response_update),
            status=200,
            content_type="application/json",
        )

        response = self.resource.get(query={}).update(self.record_response_update)

        self.assertEqual(self.record_response_update["sys_id"], response["sys_id"])

    @httpretty.activate
    def test_response_upload(self):
        """Using Response.upload() should attach the file to the queried record and return metadata"""

        httpretty.register_uri(
            httpretty.GET,
            self.mock_url_builder_base,
            body=get_serialized_result(self.record_response_get_one),
            status=200,
            content_type="application/json",
        )

        httpretty.register_uri(
            httpretty.POST,
            self.attachment_upload_url,
            body=get_serialized_result(self.attachment),
            status=201,
            content_type="application/json",
        )

        response = self.resource.get(query={}).upload(file_path=self.attachment_path)

        self.assertEqual(self.attachment["file_name"], response["file_name"])
