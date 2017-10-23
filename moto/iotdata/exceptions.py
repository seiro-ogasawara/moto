from __future__ import unicode_literals
from moto.core.exceptions import RESTError

class IoTDataPlaneClientError(RESTError):
    code = 400


class ResourceNotFoundException(IoTDataPlaneClientError):
    def __init__(self):
        self.code = 400
        super(ResourceNotFoundException, self).__init__(
            "ResourceNotFoundException",
            "The specified resource does not exist"
        )

class InvalidRequestException(IoTDataPlaneClientError):
    def __init__(self, message):
        self.code = 400
        super(InvalidRequestException, self).__init__(
            "InvalidRequestException", message
        )
